import json
import time
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from config import Settings
from llm import create_model
from schemas import DraftOutput, IntakeOutput, LLMRun, ResolutionClassification, RevisionOutput, SkillOutput

try:
    from legal_knowledge.agent_tools import LegalKnowledgeDeps, legal_knowledge_tools
except ImportError:  # Permite ejecutar el MVP sin el módulo opcional durante migraciones.
    LegalKnowledgeDeps = None
    legal_knowledge_tools = None


OutputT = TypeVar("OutputT", bound=BaseModel)
GLOBAL_INSTRUCTIONS = (
    "Sos asistente de redaccion administrativa. Usa solo hechos proporcionados y no inventes datos ni normas. "
    "Los ejemplos solo aportan estructura y estilo, nunca hechos. El molde tiene prioridad estructural."
)


class PydanticAgents:
    def __init__(self, settings: Settings, model=None, legal_knowledge=None):
        self.settings = settings
        self.model = model or create_model(settings)
        model_settings = {"max_tokens": settings.llm_max_output_tokens}
        if settings.llm_temperature is not None:
            model_settings["temperature"] = settings.llm_temperature
        self.model_settings = ModelSettings(**model_settings)
        self.legal_knowledge = legal_knowledge

    def _run(self, operation: str, output_type: type[OutputT], instructions: str, context: dict) -> LLMRun:
        use_knowledge = self.legal_knowledge is not None and LegalKnowledgeDeps is not None
        agent = Agent(
            self.model,
            output_type=PromptedOutput(output_type),
            instructions=f"{GLOBAL_INSTRUCTIONS} {instructions}",
            retries={"output": 1},
            model_settings=self.model_settings,
            deps_type=LegalKnowledgeDeps if use_knowledge else object,
            tools=legal_knowledge_tools() if use_knowledge else (),
        )
        started = time.perf_counter()
        result = agent.run_sync(
            json.dumps(context, ensure_ascii=False),
            deps=LegalKnowledgeDeps(self.legal_knowledge) if use_knowledge else None,
            usage_limits=UsageLimits(request_limit=5 if use_knowledge else 2),
        )
        usage = result.usage
        return LLMRun(
            output=result.output,
            usage={
                "requests": usage.requests,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            },
            duration_ms=round((time.perf_counter() - started) * 1000),
        )

    def intake(self, context: dict) -> LLMRun:
        return self._run(
            "intake",
            IntakeOutput,
            "Compara con prudencia los candidatos. Solo selecciona un antecedente si comparte la operacion o el objeto juridico; "
            "la misma estructura, jurisdiccion o tipo resolucion no basta ni siquiera para partial. Genera un formulario breve "
            "con todos los datos genuinamente necesarios y siempre devuelvelo.",
            context,
        )

    def classify_resolution(self, context: dict) -> LLMRun:
        return self._run(
            "resolution_classification",
            ResolutionClassification,
            "Selecciona exclusivamente entre los taxonomy_node_id candidatos. No inventes IDs. "
            "Si la solicitud no alcanza para distinguirlos, devuelve taxonomy_node_id null y needs_clarification true. "
            "La confianza representa tu evaluación estructurada, no una probabilidad estadística para mostrar al usuario.",
            context,
        )

    def draft(self, context: dict) -> LLMRun:
        return self._run(
            "draft",
            DraftOutput,
            "Redacta segun el molde. Si falta un dato imprescindible, devuelve needs_more_info; usa [DATO PENDIENTE] solo para datos no imprescindibles.",
            context,
        )

    def revision(self, context: dict) -> LLMRun:
        return self._run(
            "revision",
            RevisionOutput,
            "Aplica exclusivamente las modificaciones pedidas y preserva lo demas.",
            context,
        )

    def skill(self, key: str, instructions: str, context: dict) -> LLMRun:
        return self._run(key, SkillOutput, instructions, context)
