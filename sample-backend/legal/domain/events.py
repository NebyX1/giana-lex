from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .enums import CaseEventType, LegalCaseState, RiskTier, TaskFamily


class BaseEventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    new_state: LegalCaseState | None = None
    previous_state: LegalCaseState | None = None
    details: dict = Field(default_factory=dict)


class CaseCreatedPayload(BaseEventPayload):
    title: str
    task_family: TaskFamily
    resolution_type: str | None = None
    jurisdiction: str
    risk_tier: RiskTier
    workflow_pack_id: str | None = None
    workflow_pack_version: int | None = None
    new_state: LegalCaseState = LegalCaseState.NEW


class WorkflowRunPayload(BaseEventPayload):
    run_id: UUID


class WorkflowStepPayload(WorkflowRunPayload):
    step_run_id: UUID
    step_name: str
    attempt: int = Field(ge=1)


class CancelledPayload(BaseEventPayload):
    reason: str | None = None
    new_state: LegalCaseState = LegalCaseState.CANCELLED


class FailedPayload(BaseEventPayload):
    error: str
    new_state: LegalCaseState = LegalCaseState.FAILED


EVENT_PAYLOAD_TYPES: dict[CaseEventType, type[BaseEventPayload]] = {
    CaseEventType.CASE_CREATED: CaseCreatedPayload,
    CaseEventType.WORKFLOW_RUN_STARTED: WorkflowRunPayload,
    CaseEventType.WORKFLOW_RUN_COMPLETED: WorkflowRunPayload,
    CaseEventType.WORKFLOW_RUN_RETRIED: WorkflowRunPayload,
    CaseEventType.WORKFLOW_STEP_COMPLETED: WorkflowStepPayload,
    CaseEventType.CASE_CANCELLED: CancelledPayload,
    CaseEventType.CASE_FAILED: FailedPayload,
}


class NewCaseEvent(BaseModel):
    event_type: CaseEventType
    command_id: UUID
    run_id: UUID | None = None
    actor_user_id: int | None = None
    payload: dict = Field(default_factory=dict)
    occurred_at: datetime
    schema_version: int = Field(default=1, ge=1)

    def validated_payload(self) -> BaseEventPayload:
        payload_type = EVENT_PAYLOAD_TYPES.get(self.event_type, BaseEventPayload)
        return payload_type.model_validate(self.payload)
