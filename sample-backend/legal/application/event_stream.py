import json
import time
from collections.abc import Iterator
from uuid import UUID

from flask import current_app

from legal.cases.repository import LegalCaseRepository


def format_sse(event) -> str:
    payload = event.model_dump(mode="json")
    return (
        f"id: {event.sequence_number}\n"
        f"event: {event.event_type.value}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


def stream_case_events(case_id: UUID, owner_user_id: int, after: int) -> Iterator[str]:
    repository = LegalCaseRepository()
    deadline = time.monotonic() + current_app.config["LEGAL_SSE_WAIT_SECONDS"]
    cursor = after
    while True:
        events = repository.list_events(case_id, owner_user_id, cursor, 500)
        for event in events:
            cursor = event.sequence_number
            yield format_sse(event)
        if current_app.config["LEGAL_SSE_WAIT_SECONDS"] <= 0 or time.monotonic() >= deadline:
            return
        yield ": keep-alive\n\n"
        time.sleep(current_app.config["LEGAL_SSE_POLL_INTERVAL"])
