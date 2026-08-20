from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import CaseEventType, LegalCaseState, RiskTier, TaskFamily


class LegalCase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_user_id: int
    title: str
    task_family: TaskFamily
    resolution_type: str | None = None
    jurisdiction: str
    risk_tier: RiskTier
    workflow_pack_id: str | None = None
    workflow_pack_version: int | None = None
    state: LegalCaseState
    state_version: int
    active_run_id: UUID | None = None
    corpus_snapshot_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


class CaseEventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    new_state: LegalCaseState | None = None
    previous_state: LegalCaseState | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CaseEvent(BaseModel):
    id: UUID
    case_id: UUID
    sequence_number: int = Field(ge=1)
    event_type: CaseEventType
    schema_version: int = Field(default=1, ge=1)
    command_id: UUID
    run_id: UUID | None = None
    actor_user_id: int | None = None
    payload: CaseEventPayload
    occurred_at: datetime


class CaseSnapshot(BaseModel):
    case_id: UUID
    state: LegalCaseState = LegalCaseState.NEW
    state_version: int = 0
    last_sequence_number: int = 0
    title: str = ""
    task_family: TaskFamily = TaskFamily.LEGAL_QUESTION
    resolution_type: str | None = None
    jurisdiction: str = "lavalleja"
    risk_tier: RiskTier = RiskTier.LOW
    workflow_pack_id: str | None = None
    workflow_pack_version: int | None = None
    active_run_id: UUID | None = None
    state_before_failure: LegalCaseState | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    updated_at: datetime | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class NodeResult(BaseModel):
    status: Literal["completed", "blocked", "needs_input", "failed"]
    artifact_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[UUID] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    proposed_next_state: LegalCaseState | None = None
    model_id: str | None = None
    provider_id: str | None = None
    prompt_version: str = "none"
    toolset_version: str = "none"
    duration_ms: int = 0
    token_usage: int | None = None


class ExampleSearchProfile(BaseModel):
    act_subtype: str
    jurisdiction: str
    keywords: list[str] = Field(default_factory=list)


class TaskIntent(BaseModel):
    task_family: TaskFamily
    resolution_type: str | None = None
    jurisdiction: str = "lavalleja"
    requested_artifact: str | None = None
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    missing_fact_keys: list[str] = Field(default_factory=list)
    risk_tier: RiskTier = RiskTier.MEDIUM
    workflow_pack_id: str | None = None
    example_search_profile: ExampleSearchProfile | None = None
    confidence: float = Field(ge=0, le=1)
    decision_summary: str = Field(max_length=500)


class WorkflowCandidate(BaseModel):
    workflow_id: str
    version: int = Field(ge=1)
    basis: str


class IntakeIntent(BaseModel):
    """Validated, persistable result of compiling one complete intake request."""

    task_family: TaskFamily
    act_type: str
    subtype: str
    jurisdiction: str = "lavalleja"
    requested_artifact: str | None = None
    known_facts: dict[str, Any] = Field(default_factory=dict)
    unresolved_terms: list[str] = Field(default_factory=list)
    workflow_candidates: list[WorkflowCandidate] = Field(default_factory=list)
    selected_workflow_id: str | None = None
    selected_workflow_version: int | None = Field(default=None, ge=1)
    classification_basis: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    classifier: Literal["deterministic", "model", "unavailable", "invalid_model_output"]
    classifier_version: str
    provider: str | None = None
    model: str | None = None
    error: str | None = None
    risk_tier: RiskTier = RiskTier.MEDIUM

    @property
    def resolution_type(self) -> str | None:
        return self.subtype if self.act_type == "resolution" else None

    @property
    def workflow_pack_id(self) -> str | None:
        return self.selected_workflow_id

    @property
    def workflow_pack_version(self) -> int | None:
        return self.selected_workflow_version

    @property
    def extracted_facts(self) -> dict[str, Any]:
        return self.known_facts


class FormFieldDefinition(BaseModel):
    key: str
    label: str
    field_type: Literal[
        "text", "textarea", "date", "number", "currency", "select", "multiselect",
        "boolean", "document_reference", "person_table", "budget_table",
        "budget_transfer_table",
    ]
    required: bool = False
    origin: Literal["workflow", "legal_requirement", "precedent", "model_suggestion"]
    reason: str
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    visible_when: dict[str, Any] | None = None
    prefilled_value: Any | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


DocumentType = Literal[
    "expediente", "informe_hacienda", "informe_contaduria", "oficio", "resolucion",
    "decreto", "anexo_presupuestal", "other", "oficio_contaduria", "contrato",
    "informe_presupuestal", "informe_tecnico", "procedimiento_contratacion", "anexo", "otro",
]


class DocumentReference(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_type: DocumentType
    number: str | None = Field(default=None, min_length=1, max_length=120)
    year: int | None = Field(default=None, ge=1800, le=2200)
    date: Date | None = None
    issuer: str | None = Field(default=None, max_length=300)
    upload_id: int | None = None
    source_document_id: int | None = None
    source_url: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_reference(self):
        if self.upload_id is not None and self.source_document_id is not None and self.upload_id != self.source_document_id:
            raise ValueError("upload_id y source_document_id deben identificar el mismo documento.")
        linked_id = self.upload_id if self.upload_id is not None else self.source_document_id
        self.upload_id = linked_id
        self.source_document_id = linked_id
        if not any((self.number, self.year, self.date, self.title, linked_id, self.source_url, self.notes)):
            raise ValueError("La referencia documental debe incluir un número, fecha, título, enlace o documento cargado.")
        return self


class BudgetAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    identifier: str | None = None
    program: str | None = None
    project: str | None = None
    object: str | None = None
    auxiliary: str | None = None
    financing: str | None = None
    unit: str | None = None

    @model_validator(mode="after")
    def require_component(self):
        if not any(getattr(self, key) for key in type(self).model_fields):
            raise ValueError("La asignación presupuestal debe incluir al menos un componente identificador.")
        return self

    def canonical_id(self) -> str:
        return "|".join(str(getattr(self, key) or "").strip().casefold() for key in type(self).model_fields)


class BudgetTransferLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: BudgetAllocation
    destination: BudgetAllocation
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value):
        return Decimal(normalize_decimal(value))

    @model_validator(mode="after")
    def validate_transfer(self):
        if self.amount <= 0:
            raise ValueError("El importe de la transferencia debe ser mayor que cero.")
        if self.origin.canonical_id() == self.destination.canonical_id():
            raise ValueError("La asignación de origen y la de destino deben ser diferentes.")
        return self


class FieldProvenance(BaseModel):
    field_key: str
    source_type: Literal[
        "workflow", "validated_precedent_structure", "user_message", "persisted_fact",
        "uploaded_document", "user_answer",
    ]
    source_ref: str | None = None
    reason: str
    requires_confirmation: bool = True
    value: Any | None = None


class IntakeQuestion(BaseModel):
    key: str
    label: str
    field_type: str
    required: bool
    reason: str
    provenance: FieldProvenance
    validation_rules: dict[str, Any] = Field(default_factory=dict)


class IntakeQuestionRequest(BaseModel):
    id: UUID | None = None
    status: Literal["pending", "partial", "answered", "cancelled"] = "pending"
    questions: list[IntakeQuestion]
    answers: dict[str, Any] = Field(default_factory=dict)
    errors: dict[str, Any] = Field(default_factory=dict)


class PrecedentCandidate(BaseModel):
    example_version_id: UUID
    stable_key: str
    title: str
    subtype: str
    validation_status: str
    components: dict[str, float] = Field(default_factory=dict)
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    source_url: str | None = None


class PrecedentSearchResult(BaseModel):
    status: Literal["completed", "unavailable", "failed"]
    match_label: Literal["exact", "strong", "partial", "none"]
    searched_count: int = Field(ge=0)
    candidates: list[PrecedentCandidate] = Field(default_factory=list)
    selected_id: UUID | None = None
    calibrated_confidence: float | None = Field(default=None, ge=0, le=1)
    errors: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None


class IntakeSummary(BaseModel):
    act_type: str
    subtype: str
    act_label: str | None = None
    workflow_id: str | None = None
    workflow_version: int | None = None
    search_status: str
    match_label: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    known_fact_keys: list[str] = Field(default_factory=list)
    missing_groups: list[str] = Field(default_factory=list)
    selected_precedent_number: str | None = None
    selected_precedent_title: str | None = None
    selected_precedent_source_url: str | None = None
    generic_fallback_count: int = Field(default=0, ge=0)
    next_action: str


class LegalIssue(BaseModel):
    issue_id: str
    category: str
    question: str
    relevant_fact_ids: list[UUID] = Field(default_factory=list)
    candidate_authority_ids: list[UUID] = Field(default_factory=list)
    required_source_classes: list[str] = Field(default_factory=list)
    risk_level: RiskTier
    status: Literal["pending", "researched", "verified", "unresolved", "conflict"] = "pending"


class AuthorityVerificationResult(BaseModel):
    authority_id: str | None = None
    authenticity: Literal["verified", "unverified", "failed"]
    temporal_status: Literal["current", "superseded", "not_yet_effective", "unknown"]
    applicability: Literal["applicable", "not_applicable", "partially_applicable", "unknown"]
    source_quality: Literal[
        "official_primary", "official_secondary", "institutional", "user_document", "web_untrusted"
    ]
    supports_issue: bool
    exact_supported_proposition: str | None = None
    limitations: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    evidence_span_ids: list[UUID] = Field(default_factory=list)
    decision_summary: str = Field(max_length=500)


class DraftParagraph(BaseModel):
    text: str
    fact_ids: list[UUID] = Field(default_factory=list)
    proposition_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)


class ResolutionDraft(BaseModel):
    title: str
    expediente: str | None = None
    issuing_body: str | None = None
    vistos: list[DraftParagraph]
    resultandos: list[DraftParagraph]
    considerandos: list[DraftParagraph]
    legal_basis: list[DraftParagraph]
    operative_articles: list[DraftParagraph]
    notifications: list[str]
    signature_block: str | None = None
    annexes: list[str] = Field(default_factory=list)
    unresolved_flags: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    severity: Literal["info", "warning", "high", "critical"]
    category: str
    location: str | None = None
    description: str
    fact_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    suggested_action: str
    blocks_output: bool


class VerifiedAuthorityInput(BaseModel):
    issue_id: str
    source_id: str
    source_version: str = "1"
    source_class: Literal["official_primary", "official_secondary", "institutional"]
    jurisdiction: str
    exact_text: str = Field(min_length=1)
    proposition: str = Field(min_length=1)
    norm_id: str | None = None
    article: str | None = None
    source_url: str | None = None
    effective_from: Date | None = None
    effective_to: Date | None = None
    authenticity_verified: bool
    applicability_verified: bool
    active: bool = True


def normalize_decimal(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not monetary amounts")
    raw = str(value).strip().replace(" ", "")
    if not raw:
        raise ValueError("Invalid decimal amount")
    if "," in raw and "." in raw:
        # The right-most separator is decimal; the other is grouping.
        decimal_separator = "," if raw.rfind(",") > raw.rfind(".") else "."
        grouping_separator = "." if decimal_separator == "," else ","
        raw = raw.replace(grouping_separator, "").replace(decimal_separator, ".")
    elif "," in raw:
        parts = raw.split(",")
        raw = "".join(parts) if len(parts) > 2 or len(parts[-1]) == 3 else ".".join(parts)
    elif "." in raw:
        parts = raw.split(".")
        raw = "".join(parts) if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3) else raw
    try:
        amount = Decimal(raw)
    except Exception as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not amount.is_finite():
        raise ValueError("Invalid decimal amount")
    return format(amount.quantize(Decimal("0.01")), "f")
