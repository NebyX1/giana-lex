import pytest

from state import ConversationState, InvalidTransition, Stage


def test_explicit_state_transitions():
    state = ConversationState(original_request="Solicitud")
    with pytest.raises(InvalidTransition):
        state.transition(Stage.DRAFT_REVIEW)

    state.transition(Stage.SEARCHING_EXAMPLES)
    state.transition(Stage.COLLECTING_INFO)
    state.transition(Stage.DRAFT_REVIEW)
    state.transition(Stage.APPROVED)
    assert state.approved is False


def test_approved_cannot_return_to_review():
    state = ConversationState(original_request="Solicitud", stage=Stage.APPROVED, approved=True, draft="Texto")
    with pytest.raises(InvalidTransition):
        state.transition(Stage.DRAFT_REVIEW)
