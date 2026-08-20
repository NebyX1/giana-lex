from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from legal.domain.models import CaseSnapshot, IntakeIntent, IntakeSummary, LegalCase


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FormArtifact(WorkspaceModel):
    id: UUID
    version: int
    workflow_pack_id: str
    workflow_pack_version: int
    status: str
    schema_data: dict[str, Any] = Field(
        validation_alias="schema_json", serialization_alias="schema_json"
    )
    answers_json: dict[str, Any]
    errors_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None


class PrecedentArtifact(WorkspaceModel):
    id: UUID
    primary_example_version_id: UUID | None = None
    match_type: str
    confidence: float
    alternatives_json: list[Any]
    differences_json: list[Any]
    fallback_reason: str | None = None
    created_at: datetime


class PrecedentSearchArtifact(WorkspaceModel):
    id: UUID
    status: str
    query: dict[str, Any] = Field(validation_alias="query_json", serialization_alias="query")
    collections: list[Any] = Field(validation_alias="collections_json", serialization_alias="collections")
    index_status: dict[str, Any] = Field(validation_alias="index_status_json", serialization_alias="index_status")
    searched_count: int
    candidates: list[Any] = Field(validation_alias="candidates_json", serialization_alias="candidates")
    selected_example_version_id: UUID | None = None
    match_label: str
    calibrated_confidence: float | None = None
    similarities: list[Any] = Field(validation_alias="similarities_json", serialization_alias="similarities")
    differences: list[Any] = Field(validation_alias="differences_json", serialization_alias="differences")
    errors: list[Any] = Field(validation_alias="errors_json", serialization_alias="errors")
    fallback_reason: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ResolvedPrecedentSummary(BaseModel):
    title: str | None = None
    number: str | None = None
    date: str | None = None
    document_type: str | None = None
    source_url: str | None = None
    match_label: str
    similarities: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    warning: str = "Antecedente estructural; sus referencias jurídicas permanecen sin verificar."


class QuestionRequestArtifact(WorkspaceModel):
    id: UUID
    status: str
    form_id: UUID | None = None
    human_task_id: UUID | None = None
    questions: list[Any] = Field(validation_alias="questions_json", serialization_alias="questions")
    answers: dict[str, Any] = Field(validation_alias="answers_json", serialization_alias="answers")
    errors: dict[str, Any] = Field(validation_alias="errors_json", serialization_alias="errors")
    created_at: datetime
    updated_at: datetime
    answered_at: datetime | None = None


class FieldProvenanceArtifact(WorkspaceModel):
    id: UUID
    field_key: str
    source_type: str
    source_ref: str | None = None
    reason: str
    value_json: dict[str, Any] | None = None
    requires_confirmation: bool


class DocumentArtifact(WorkspaceModel):
    id: int
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class FactArtifact(WorkspaceModel):
    id: UUID
    key: str
    value_json: dict[str, Any]
    value_type: str
    source_type: str
    source_ref: str | None = None
    confidence: float
    verification_status: str
    recorded_at: datetime
    supersedes_id: UUID | None = None


class IssueArtifact(BaseModel):
    issue_id: str
    category: str
    question: str
    relevant_fact_ids: list[UUID] = Field(default_factory=list)
    candidate_authority_ids: list[UUID] = Field(default_factory=list)
    required_source_classes: list[str] = Field(default_factory=list)
    risk_level: str
    status: str


class EvidenceArtifact(WorkspaceModel):
    id: UUID
    source_id: str
    source_version: str
    source_class: str
    jurisdiction: str
    norm_id: str | None = None
    article: str | None = None
    exact_text: str
    source_url: str | None = None
    checksum: str
    effective_from: date | None = None
    effective_to: date | None = None
    active: bool
    verified_at: datetime
    verification_method: str


class DraftArtifact(WorkspaceModel):
    id: UUID
    case_id: UUID
    version: int
    corpus_snapshot_id: UUID
    status: str
    draft_json: dict[str, Any]
    validation_json: dict[str, Any]
    created_at: datetime


class HumanTaskArtifact(WorkspaceModel):
    id: UUID
    case_id: UUID
    task_type: str
    status: str
    payload_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class FindingArtifact(WorkspaceModel):
    id: UUID
    case_id: UUID
    draft_version_id: UUID
    reviewer_type: str
    severity: str
    category: str
    finding_json: dict[str, Any]
    blocks_output: bool
    created_at: datetime


class WorkspaceMessage(WorkspaceModel):
    id: int
    role: str
    content: str
    tool_call_id: str | None = None
    created_at: datetime


class WorkspaceSession(WorkspaceModel):
    id: int
    status: str


class CaseEventMetadata(BaseModel):
    id: UUID
    sequence_number: int
    event_type: str
    run_id: UUID | None = None
    occurred_at: datetime


class CaseActivity(BaseModel):
    kind: Literal[
        "working", "waiting_user", "waiting_human_review", "blocked",
        "failed", "completed", "idle",
    ]
    active_run_id: UUID | None = None
    current_step: str | None = None
    started_at: datetime | None = None
    task_type: str | None = None
    task_id: UUID | None = None
    draft_version: int | None = None
    last_event_sequence: int | None = None
    last_event_type: str | None = None
    updated_at: datetime | None = None
    message: str | None = None


class CaseCapabilities(BaseModel):
    can_view_draft: bool
    can_edit_draft: bool
    can_export_docx: bool
    can_review: bool
    can_reject: bool
    can_request_second_opinion: bool
    can_cancel: bool


class BlockingReason(BaseModel):
    code: str
    message: str
    category: Literal["consistency", "workflow", "capability"] = "workflow"
    recoverable: bool = True


class CaseWorkspace(BaseModel):
    schema_version: int = 1
    case: LegalCase
    snapshot: CaseSnapshot
    activity: CaseActivity
    form: FormArtifact | None = None
    precedent: PrecedentArtifact | None = None
    intake_intent: IntakeIntent | None = None
    precedent_search: PrecedentSearchArtifact | None = None
    resolved_precedent: ResolvedPrecedentSummary | None = None
    question_request: QuestionRequestArtifact | None = None
    field_provenance: list[FieldProvenanceArtifact] = Field(default_factory=list)
    documents: list[DocumentArtifact] = Field(default_factory=list)
    intake_summary: IntakeSummary | None = None
    facts: list[FactArtifact]
    issues: list[IssueArtifact]
    evidence: list[EvidenceArtifact]
    draft: DraftArtifact | None = None
    findings: list[FindingArtifact]
    human_tasks: list[HumanTaskArtifact]
    session: WorkspaceSession | None = None
    messages: list[WorkspaceMessage]
    guidance: str
    capabilities: CaseCapabilities
    blocking_reasons: list[BlockingReason]
    last_event: CaseEventMetadata | None = None
