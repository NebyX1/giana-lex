from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .schemas import Claim, ExecutionBudget, MissingField


class TaskStage(StrEnum):
    RECEIVED = "RECEIVED"
    CLASSIFIED = "CLASSIFIED"
    CONTEXT_READY = "CONTEXT_READY"
    RESEARCHING = "RESEARCHING"
    EVIDENCE_READY = "EVIDENCE_READY"
    ANALYZING = "ANALYZING"
    DRAFTING = "DRAFTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    WAITING_USER = "WAITING_USER"
    RETRYING = "RETRYING"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


@dataclass
class TaskState:
    user_request: str
    task_id: str = field(default_factory=lambda: str(uuid4()))
    intent: str | None = None
    task_type: str | None = None
    document_type: str | None = None
    subtype: str | None = None
    stage: TaskStage = TaskStage.RECEIVED
    selected_skills: list[str] = field(default_factory=list)
    selected_template: str | None = None
    selected_variant: str | None = None
    facts: list[str] = field(default_factory=list)
    legal_questions: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    missing_fields: list[MissingField] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    draft: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_count: int = 0
    iteration_count: int = 0
    llm_call_count: int = 0
    confidence: str | None = None
    status: str = "active"
    effective_mode: str = "standard"
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    snapshots: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, stage: TaskStage) -> None:
        self.stage = stage
        self.status = {
            TaskStage.COMPLETED: "completed",
            TaskStage.WAITING_USER: "waiting_user",
            TaskStage.ESCALATED: "escalated",
            TaskStage.FAILED: "failed",
        }.get(stage, "active")

    def snapshot(self, label: str) -> None:
        self.snapshots.append({
            "label": label,
            "stage": self.stage.value,
            "evidence_ids": list(self.evidence_ids),
            "validation_errors": list(self.validation_errors),
            "tool_call_count": len(self.tool_calls),
        })

    def summary(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("user_request", None)
        data.pop("draft", None)
        data.pop("snapshots", None)
        return data
