import time
from datetime import date
from threading import Lock
from typing import Any

from pydantic import ValidationError

from config import Settings
from schemas import DynamicForm, LLMRun, SkillOutput
from skills.registry import discover_skills
from state import ConversationState, InvalidTransition, Stage
from storage import Storage
from tools.load_mold import load_mold
from tools.search_examples import has_lexical_support, load_selected_examples, search_examples


class NotFoundError(ValueError):
    pass


class OperationError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def validate_form_answers(form: DynamicForm, answers: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, str] = {}
    validated: dict[str, Any] = {}
    for field in form.fields:
        value = answers.get(field.id)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if field.required:
                errors[field.id] = "Este campo es obligatorio"
            continue
        if field.field_type in {"text", "textarea"}:
            if not isinstance(value, str):
                errors[field.id] = "Debe ser texto"
            else:
                validated[field.id] = value.strip()
        elif field.field_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors[field.id] = "Debe ser un numero"
            else:
                validated[field.id] = value
        elif field.field_type == "boolean":
            if not isinstance(value, bool):
                errors[field.id] = "Debe ser verdadero o falso"
            else:
                validated[field.id] = value
        elif field.field_type == "select":
            if not isinstance(value, str) or value not in (field.options or []):
                errors[field.id] = "Debe elegir una opcion valida"
            else:
                validated[field.id] = value
        elif field.field_type == "date":
            try:
                validated[field.id] = date.fromisoformat(value).isoformat() if isinstance(value, str) else None
                if validated[field.id] is None:
                    raise ValueError
            except ValueError:
                errors[field.id] = "Debe ser una fecha ISO valida (AAAA-MM-DD)"
    if errors:
        detail = "; ".join(f"{field}: {message}" for field, message in errors.items())
        raise OperationError("validation_error", f"Hay campos invalidos o incompletos: {detail}", False)
    return validated


class Orchestrator:
    def __init__(self, settings: Settings, storage: Storage, agents: Any):
        self.settings = settings
        self.storage = storage
        self.agents = agents
        self.skills = discover_skills()
        self._lock = Lock()

    def _get(self, conversation_id: str) -> ConversationState:
        state = self.storage.get(conversation_id)
        if not state:
            raise NotFoundError("Conversacion no encontrada")
        return state

    def _tool(self, state: ConversationState, name: str, function, *args):
        started = time.perf_counter()
        try:
            result = function(*args)
        except Exception as exc:
            raise OperationError(f"{name}_error", f"Fallo tecnico en {name}: {exc}", True) from exc
        state.add_event(
            {"type": "tool", "name": name, "duration_ms": round((time.perf_counter() - started) * 1000)}
        )
        return result

    def _record_llm(self, state: ConversationState, operation: str, run: LLMRun) -> None:
        state.add_event(
            {
                "type": "llm",
                "operation": operation,
                **run.usage,
                "duration_ms": run.duration_ms,
            }
        )

    def _set_debug(self, state: ConversationState, before: Stage, tools: list[str]) -> None:
        latest_llm = next((event for event in reversed(state.events) if event.get("type") == "llm"), {})
        state.last_debug = {
            "stage_before": before.value,
            "stage_after": state.stage.value,
            "tools_executed": tools,
            "example_candidates": [candidate.model_dump() for candidate in state.example_candidates],
            "examples_selected": [match.model_dump() for match in state.selected_examples],
            "llm": {key: latest_llm.get(key, 0) for key in (
                "requests", "input_tokens", "output_tokens", "total_tokens", "duration_ms"
            )},
        }

    def create_conversation(self, message: str) -> ConversationState:
        if not isinstance(message, str) or not message.strip():
            raise OperationError("validation_error", "El mensaje es obligatorio")
        state = ConversationState(original_request=message.strip())
        self.storage.save(state)
        before = state.stage
        state.transition(Stage.SEARCHING_EXAMPLES)
        self.storage.save(state)
        try:
            candidates = self._tool(
                state, "search_examples", search_examples, state.original_request, self.settings.examples_dir,
                self.settings.examples_top_k,
            )
            mold = self._tool(state, "load_mold", load_mold, self.settings.molds_dir)
            run = self.agents.intake(
                {
                    "solicitud": state.original_request,
                    "candidatos": [candidate.model_dump() for candidate in candidates],
                    "molde": mold,
                }
            )
            self._record_llm(state, "intake", run)
            output = run.output
            available = {candidate.filename: candidate for candidate in candidates}
            output.matched_examples = [
                match
                for match in output.matched_examples
                if match.filename in available and has_lexical_support(state.original_request, available[match.filename])
            ][:2]
            if output.match_status == "none":
                output.matched_examples = []
            state.example_candidates = candidates
            state.selected_examples = output.matched_examples
            state.current_form = output.form
            state.transition(Stage.COLLECTING_INFO)
            self._set_debug(state, before, ["search_examples", "load_mold"])
            state.last_debug["message"] = output.assistant_message
            self.storage.save(state)
            return state
        except OperationError:
            raise
        except Exception as exc:
            self.storage.save(state)
            raise OperationError("llm_provider_error", str(exc), True) from exc

    def submit_form(self, conversation_id: str, answers: dict[str, Any]) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.COLLECTING_INFO or not state.current_form:
                raise InvalidTransition("El formulario solo puede enviarse al recopilar informacion")
            before = state.stage
            validated = validate_form_answers(state.current_form, answers)
            merged_answers = {**state.form_answers, **validated}
            try:
                mold = self._tool(state, "load_mold", load_mold, self.settings.molds_dir)
                examples = self._tool(
                    state,
                    "load_selected_examples",
                    load_selected_examples,
                    [match.filename for match in state.selected_examples],
                    self.settings.examples_dir,
                )
                run = self.agents.draft(
                    {
                        "solicitud": state.original_request,
                        "datos_formulario": merged_answers,
                        "molde": mold,
                        "ejemplos_relevantes": examples,
                    }
                )
                self._record_llm(state, "draft", run)
                output = run.output
                state.form_answers = merged_answers
                if output.status == "needs_more_info":
                    state.current_form = output.additional_form
                    state.transition(Stage.COLLECTING_INFO)
                else:
                    state.draft = output.draft_markdown
                    state.current_form = None
                    state.transition(Stage.DRAFT_REVIEW)
                self._set_debug(state, before, ["load_mold", "load_selected_examples"])
                state.last_debug["message"] = output.assistant_message
                self.storage.save(state)
                return state
            except OperationError:
                raise
            except Exception as exc:
                self.storage.save(state)
                raise OperationError("llm_provider_error", str(exc), True) from exc

    def revise(self, conversation_id: str, instructions: str) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.DRAFT_REVIEW or not state.draft:
                raise InvalidTransition("Solo se puede revisar un borrador pendiente")
            if not isinstance(instructions, str) or not instructions.strip():
                raise OperationError("validation_error", "Las instrucciones son obligatorias")
            before = state.stage
            try:
                run = self.agents.revision(
                    {
                        "borrador_vigente": state.draft,
                        "modificaciones": instructions.strip(),
                        "datos_esenciales": state.form_answers,
                    }
                )
                self._record_llm(state, "revision", run)
                state.draft = run.output.draft_markdown
                state.revision_count += 1
                state.revision_notes.append(instructions.strip())
                state.revision_notes = state.revision_notes[-10:]
                state.transition(Stage.DRAFT_REVIEW)
                self._set_debug(state, before, [])
                state.last_debug["message"] = run.output.assistant_message
                self.storage.save(state)
                return state
            except Exception as exc:
                self.storage.save(state)
                raise OperationError("llm_provider_error", str(exc), True) from exc

    def approve(self, conversation_id: str) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.DRAFT_REVIEW or not state.draft:
                raise InvalidTransition("No hay un borrador listo para aprobar")
            before = state.stage
            state.approved = True
            state.transition(Stage.APPROVED)
            self._set_debug(state, before, [])
            state.last_debug["message"] = "Borrador aprobado. ¿Queres realizar algun analisis adicional?"
            self.storage.save(state)
            return state

    def run_skill(self, conversation_id: str, key: str, answers: dict[str, Any] | None = None) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.APPROVED or not state.approved or not state.draft:
                raise InvalidTransition("Las skills solo pueden ejecutarse tras aprobar el borrador")
            skill = self.skills.get(key)
            if not skill:
                raise NotFoundError("Skill no encontrada")
            rounds = state.skill_input_rounds.get(key, 0)
            existing = state.skill_results.get(key)
            additional = None
            if answers is not None:
                if rounds != 1 or not existing or existing.get("status") != "needs_input":
                    raise InvalidTransition("Esta skill no espera respuestas")
                additional = validate_form_answers(DynamicForm.model_validate(existing["questions"]), answers)
            elif rounds >= 1 and existing and existing.get("status") == "needs_input":
                raise OperationError("validation_error", "La skill requiere responder su formulario")
            before = state.stage
            try:
                run = skill.run(
                    self.agents,
                    {
                        "borrador_aprobado": state.draft,
                        "datos_relevantes": state.form_answers,
                        "revisiones_aplicadas": state.revision_notes,
                        "regla_de_precedencia": (
                            "El borrador aprobado ya incorpora las revisiones y prevalece ante cualquier dato anterior contradictorio."
                        ),
                        "respuestas_adicionales": additional,
                    },
                )
                self._record_llm(state, key, run)
                output: SkillOutput = run.output
                if output.status == "needs_input":
                    if rounds >= 1:
                        output = output.model_copy(
                            update={
                                "status": "complete",
                                "summary": (
                                    f"{output.summary} Analisis finalizado tras la unica ronda adicional; "
                                    "las incertidumbres restantes requieren revision humana."
                                ),
                                "questions": None,
                            }
                        )
                    else:
                        state.skill_input_rounds[key] = 1
                state.skill_results[key] = output.model_dump()
                self._set_debug(state, before, [])
                state.last_debug["message"] = output.summary
                self.storage.save(state)
                return state
            except OperationError:
                self.storage.save(state)
                raise
            except Exception as exc:
                self.storage.save(state)
                raise OperationError("llm_provider_error", str(exc), True) from exc

    def get(self, conversation_id: str) -> ConversationState:
        return self._get(conversation_id)

    def skill_metadata(self) -> list[dict[str, str]]:
        return [skill.metadata() for skill in self.skills.values()]
