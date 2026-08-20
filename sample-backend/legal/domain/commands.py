from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .enums import RiskTier, TaskFamily


class BaseCaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID
    actor_user_id: int
    idempotency_key: str = Field(min_length=1, max_length=255)


class CreateLegalCase(BaseCaseCommand):
    command_type: Literal["create_legal_case"] = "create_legal_case"
    case_id: UUID
    title: str = Field(min_length=1, max_length=300)
    task_family: TaskFamily = TaskFamily.LEGAL_QUESTION
    resolution_type: str | None = Field(default=None, max_length=120)
    jurisdiction: str = Field(default="lavalleja", min_length=1, max_length=120)
    risk_tier: RiskTier = RiskTier.LOW
    workflow_pack_id: str | None = Field(default=None, max_length=160)
    workflow_pack_version: int | None = Field(default=None, ge=1)


class CaseScopedCommand(BaseCaseCommand):
    case_id: UUID


class StartLegalWorkflow(CaseScopedCommand):
    command_type: Literal["start_legal_workflow"] = "start_legal_workflow"


class SubmitInitialRequest(CaseScopedCommand):
    command_type: Literal["submit_initial_request"] = "submit_initial_request"
    request_text: str = Field(min_length=1)


class SubmitFormAnswers(CaseScopedCommand):
    command_type: Literal["submit_form_answers"] = "submit_form_answers"
    form_id: UUID
    answers: dict[str, Any]
    partial: bool = False


class ConfirmFacts(CaseScopedCommand):
    command_type: Literal["confirm_facts"] = "confirm_facts"
    fact_ids: list[UUID]


class RetryWorkflowStep(CaseScopedCommand):
    command_type: Literal["retry_workflow_step"] = "retry_workflow_step"
    step_run_id: UUID | None = None


class CancelWorkflow(CaseScopedCommand):
    command_type: Literal["cancel_workflow"] = "cancel_workflow"
    reason: str | None = Field(default=None, max_length=500)


class ResumeBlockedCase(CaseScopedCommand):
    command_type: Literal["resume_blocked_case"] = "resume_blocked_case"
    resolution: dict[str, Any]


class RequestDraft(CaseScopedCommand):
    command_type: Literal["request_draft"] = "request_draft"


class SubmitHumanReview(CaseScopedCommand):
    command_type: Literal["submit_human_review"] = "submit_human_review"
    draft_id: UUID
    draft_version: int = Field(ge=1)
    approved: bool
    findings: list[dict[str, Any]] = Field(default_factory=list)


class ApproveMemoryProposal(CaseScopedCommand):
    command_type: Literal["approve_memory_proposal"] = "approve_memory_proposal"
    proposal_id: UUID


class RejectMemoryProposal(CaseScopedCommand):
    command_type: Literal["reject_memory_proposal"] = "reject_memory_proposal"
    proposal_id: UUID
    reason: str = Field(min_length=1, max_length=500)


CaseCommand = (
    CreateLegalCase
    | StartLegalWorkflow
    | SubmitInitialRequest
    | SubmitFormAnswers
    | ConfirmFacts
    | RetryWorkflowStep
    | CancelWorkflow
    | ResumeBlockedCase
    | RequestDraft
    | SubmitHumanReview
    | ApproveMemoryProposal
    | RejectMemoryProposal
)
