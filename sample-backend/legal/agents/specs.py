from typing import Literal

from pydantic import BaseModel, ConfigDict


class SpecialistSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    execution: Literal["deterministic", "model_optional", "provider"]
    tools: tuple[str, ...]
    output_schema: str


SPECIALIST_SPECS = {
    "manager": SpecialistSpec(
        role="manager", execution="deterministic", tools=(), output_schema="NodeResult",
    ),
    "intent_planner": SpecialistSpec(
        role="intent_planner", execution="model_optional", tools=(), output_schema="IntakeIntent",
    ),
    "precedent_explorer": SpecialistSpec(
        role="precedent_explorer", execution="model_optional",
        tools=("search_examples",), output_schema="PrecedentSearchResult",
    ),
    "analyzer": SpecialistSpec(
        role="analyzer", execution="model_optional", tools=(), output_schema="NodeResult",
    ),
    "question_planner": SpecialistSpec(
        role="question_planner", execution="deterministic", tools=(), output_schema="IntakeQuestionRequest",
    ),
    "form_compiler": SpecialistSpec(
        role="form_compiler", execution="deterministic", tools=(), output_schema="FormInstance",
    ),
    "researcher": SpecialistSpec(
        role="researcher", execution="provider",
        tools=("search_departmental_norms", "search_national_norms", "verify_legal_reference"),
        output_schema="VerifiedAuthorityInput[]",
    ),
}
