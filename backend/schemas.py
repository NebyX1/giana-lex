from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


FieldType = Literal["text", "textarea", "number", "date", "select", "boolean"]


class ExampleCandidate(BaseModel):
    filename: str
    title: str
    score: float
    excerpt: str
    example_id: str | None = None
    revision_id: str | None = None
    match_class: str | None = None
    scope: str | None = None
    reasons: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    defects: list[str] = Field(default_factory=list)


class ExampleMatch(BaseModel):
    filename: str
    relevance: Literal["strong", "partial"]
    reason: str


class FormField(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    label: str = Field(min_length=1, max_length=160)
    field_type: FieldType
    required: bool = True
    help_text: str | None = None
    placeholder: str | None = None
    options: list[str] | None = None
    why_needed: str | None = None

    @model_validator(mode="after")
    def validate_options(self):
        if self.field_type == "select" and not self.options:
            raise ValueError("Los campos select deben incluir opciones")
        if self.field_type != "select" and self.options:
            raise ValueError("Solo los campos select pueden incluir opciones")
        return self


class DynamicForm(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    fields: list[FormField] = Field(min_length=1, max_length=30)

    @field_validator("fields")
    @classmethod
    def unique_ids(cls, fields: list[FormField]) -> list[FormField]:
        ids = [field.id for field in fields]
        if len(ids) != len(set(ids)):
            raise ValueError("Los identificadores de campos deben ser unicos")
        return fields


class IntakeOutput(BaseModel):
    match_status: Literal["similar", "partial", "none"]
    assistant_message: str
    matched_examples: list[ExampleMatch] = Field(default_factory=list, max_length=5)
    form: DynamicForm


class DraftOutput(BaseModel):
    status: Literal["draft_ready", "needs_more_info"]
    assistant_message: str
    draft_markdown: str | None = None
    additional_form: DynamicForm | None = None

    @model_validator(mode="after")
    def validate_status_payload(self):
        if self.status == "draft_ready" and not self.draft_markdown:
            raise ValueError("draft_ready requiere draft_markdown")
        if self.status == "needs_more_info" and not self.additional_form:
            raise ValueError("needs_more_info requiere additional_form")
        return self


class RevisionOutput(BaseModel):
    assistant_message: str
    draft_markdown: str = Field(min_length=1)


class RiskFinding(BaseModel):
    title: str
    risk_level: Literal["low", "medium", "high", "unknown"]
    explanation: str
    affected_actors: list[str] = Field(default_factory=list)
    mitigation: str | None = None


class SkillOutput(BaseModel):
    status: Literal["complete", "needs_input"]
    summary: str
    overall_risk: Literal["low", "medium", "high", "unknown"]
    findings: list[RiskFinding] = Field(default_factory=list)
    questions: DynamicForm | None = None

    @model_validator(mode="after")
    def validate_questions(self):
        if self.status == "needs_input" and not self.questions:
            raise ValueError("needs_input requiere questions")
        return self


class LLMRun(BaseModel):
    output: Any
    usage: dict[str, int]
    duration_ms: int


class ClassificationAlternative(BaseModel):
    taxonomy_node_id: str
    score: float = Field(ge=0, le=1)


class ResolutionClassification(BaseModel):
    taxonomy_node_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    alternatives: list[ClassificationAlternative] = Field(default_factory=list)
    rationale: str
    needs_clarification: bool = False


class ContextFinding(BaseModel):
    category: Literal["objeto", "competencia", "antecedentes", "motivacion", "procedimiento", "audiencia", "presupuesto", "efecto", "plazo", "notificacion", "congruencia"]
    severity: Literal["info", "warning", "critical"]
    draft_excerpt: str
    explanation: str
    action: str
    needs_document: bool = False


class ContextCheckOutput(BaseModel):
    summary: str
    findings: list[ContextFinding] = Field(default_factory=list, max_length=20)
    missing_facts: list[str] = Field(default_factory=list, max_length=20)
