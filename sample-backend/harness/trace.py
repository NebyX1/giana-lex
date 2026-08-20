from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


class HarnessTrace:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.events: list[TraceEvent] = []
        self.metrics = {
            "llm_calls": 0,
            "tool_calls": 0,
            "retrieval_calls": 0,
            "retries": 0,
            "validation_failures": 0,
            "escalations": 0,
            "unsupported_claims_blocked": 0,
            "loops_prevented": 0,
            "missing_fields_detected": 0,
            "example_authority_blocks": 0,
        }

    def record(self, event_type: str, **metadata: Any) -> None:
        safe = {key: value for key, value in metadata.items() if key not in {"prompt", "content", "token", "secret"}}
        self.events.append(TraceEvent(event_type, datetime.now(timezone.utc).isoformat(), safe))

    def increment(self, metric: str, amount: int = 1) -> None:
        self.metrics[metric] = self.metrics.get(metric, 0) + amount

    def as_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "events": [asdict(event) for event in self.events], "metrics": dict(self.metrics)}
