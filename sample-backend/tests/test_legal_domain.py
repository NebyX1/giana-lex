from datetime import datetime
from uuid import uuid4

import pytest

from legal.cases.reducer import reduce_case_event
from legal.cases.transitions import ALLOWED_TRANSITIONS
from legal.domain.enums import CaseEventType, LegalCaseState
from legal.domain.errors import InvalidCaseTransitionError
from legal.domain.models import CaseEvent, CaseEventPayload, CaseSnapshot


def event(case_id, sequence, event_type, payload):
    return CaseEvent(
        id=uuid4(),
        case_id=case_id,
        sequence_number=sequence,
        event_type=event_type,
        command_id=uuid4(),
        payload=CaseEventPayload.model_validate(payload),
        occurred_at=datetime(2026, 8, 17, 12, 0, sequence),
    )


def test_reducer_is_pure_and_applies_explicit_transition():
    case_id = uuid4()
    original = CaseSnapshot(case_id=case_id)
    changed = reduce_case_event(
        original,
        event(
            case_id,
            1,
            CaseEventType.INTENT_COMPILED,
            {"new_state": LegalCaseState.INTENT_COMPILED.value},
        ),
    )

    assert original.state == LegalCaseState.NEW
    assert original.state_version == 0
    assert changed.state == LegalCaseState.INTENT_COMPILED
    assert changed.state_version == 1
    assert changed.last_sequence_number == 1
    assert LegalCaseState.INTENT_COMPILED in ALLOWED_TRANSITIONS[LegalCaseState.NEW]


def test_reducer_rejects_skipped_state():
    case_id = uuid4()
    with pytest.raises(InvalidCaseTransitionError):
        reduce_case_event(
            CaseSnapshot(case_id=case_id),
            event(
                case_id,
                1,
                CaseEventType.DRAFT_CREATED,
                {"new_state": LegalCaseState.DRAFT_READY.value},
            ),
        )
