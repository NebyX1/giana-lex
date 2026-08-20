from legal.domain.enums import LegalCaseState
from legal.domain.errors import InvalidCaseTransitionError


_LINEAR_STATES = [
    LegalCaseState.NEW,
    LegalCaseState.INTENT_COMPILED,
    LegalCaseState.WORKFLOW_SELECTED,
    LegalCaseState.SEARCHING_PRECEDENTS,
    LegalCaseState.PRECEDENT_SELECTED,
    LegalCaseState.FORM_READY,
    LegalCaseState.AWAITING_FACTS,
    LegalCaseState.VALIDATING_FACTS,
    LegalCaseState.FACTS_COMPLETE,
    LegalCaseState.LEGAL_ISSUES_PLANNED,
    LegalCaseState.RESEARCHING,
    LegalCaseState.VERIFYING_EVIDENCE,
    LegalCaseState.EVIDENCE_READY,
    LegalCaseState.DRAFTING,
    LegalCaseState.DRAFT_READY,
    LegalCaseState.COMPLIANCE_REVIEW,
    LegalCaseState.CITATION_REVIEW,
    LegalCaseState.READY_FOR_HUMAN_REVIEW,
    LegalCaseState.COMPLETED,
]

ALLOWED_TRANSITIONS: dict[LegalCaseState, frozenset[LegalCaseState]] = {
    state: frozenset({next_state, LegalCaseState.BLOCKED, LegalCaseState.CANCELLED, LegalCaseState.FAILED})
    for state, next_state in zip(_LINEAR_STATES, _LINEAR_STATES[1:])
}
_RESUMABLE_STATES = frozenset(_LINEAR_STATES[:-1])
ALLOWED_TRANSITIONS[LegalCaseState.BLOCKED] = _RESUMABLE_STATES | {
    LegalCaseState.CANCELLED,
    LegalCaseState.FAILED,
}
ALLOWED_TRANSITIONS[LegalCaseState.FAILED] = _RESUMABLE_STATES | {
    LegalCaseState.BLOCKED,
    LegalCaseState.CANCELLED,
}
ALLOWED_TRANSITIONS[LegalCaseState.COMPLETED] = frozenset()
ALLOWED_TRANSITIONS[LegalCaseState.CANCELLED] = frozenset()


def require_transition(current: LegalCaseState, target: LegalCaseState) -> None:
    if target == current:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidCaseTransitionError(
            f"Transition from {current.value} to {target.value} is not allowed"
        )
