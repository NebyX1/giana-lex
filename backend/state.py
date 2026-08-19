from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas import DynamicForm, ExampleCandidate, ExampleMatch


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Stage(str, Enum):
    NEW = "new"
    SEARCHING_EXAMPLES = "searching_examples"
    COLLECTING_INFO = "collecting_info"
    DRAFT_REVIEW = "draft_review"
    APPROVED = "approved"
    ERROR = "error"


ALLOWED_TRANSITIONS = {
    Stage.NEW: {Stage.SEARCHING_EXAMPLES},
    Stage.SEARCHING_EXAMPLES: {Stage.COLLECTING_INFO},
    Stage.COLLECTING_INFO: {Stage.COLLECTING_INFO, Stage.DRAFT_REVIEW},
    Stage.DRAFT_REVIEW: {Stage.DRAFT_REVIEW, Stage.APPROVED},
    Stage.APPROVED: {Stage.APPROVED},
    Stage.ERROR: set(),
}


class InvalidTransition(ValueError):
    pass


class ConversationState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    stage: Stage = Stage.NEW
    original_request: str
    example_candidates: list[ExampleCandidate] = Field(default_factory=list)
    selected_examples: list[ExampleMatch] = Field(default_factory=list)
    current_form: DynamicForm | None = None
    form_answers: dict[str, Any] = Field(default_factory=dict)
    draft: str | None = None
    revision_count: int = 0
    revision_notes: list[str] = Field(default_factory=list)
    approved: bool = False
    skill_results: dict[str, Any] = Field(default_factory=dict)
    skill_input_rounds: dict[str, int] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    last_debug: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

    def transition(self, target: Stage) -> None:
        if target not in ALLOWED_TRANSITIONS[self.stage]:
            raise InvalidTransition(f"No se puede pasar de {self.stage.value} a {target.value}")
        previous = self.stage
        self.stage = target
        self.add_event({"type": "transition", "from": previous.value, "to": target.value})

    def add_event(self, event: dict[str, Any]) -> None:
        self.events.append({**event, "timestamp": utc_now()})
        self.events = self.events[-50:]
        self.updated_at = utc_now()
