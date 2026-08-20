from legal.cases.transitions import require_transition
from legal.domain.enums import CaseEventType, LegalCaseState
from legal.domain.models import CaseEvent, CaseSnapshot


def reduce_case_event(current: CaseSnapshot, event: CaseEvent) -> CaseSnapshot:
    """Apply one validated event without I/O or nondeterministic behavior."""
    if event.case_id != current.case_id:
        raise ValueError("Event belongs to a different case")
    if event.sequence_number != current.last_sequence_number + 1:
        raise ValueError("Event sequence is not contiguous")

    payload = event.payload
    updates = {
        "state_version": current.state_version + 1,
        "last_sequence_number": event.sequence_number,
        "updated_at": event.occurred_at,
    }
    data = dict(current.data)

    if event.event_type == CaseEventType.CASE_CREATED:
        updates.update(
            title=str(payload.model_extra.get("title", "")),
            task_family=payload.model_extra.get("task_family", current.task_family),
            resolution_type=payload.model_extra.get("resolution_type"),
            jurisdiction=str(payload.model_extra.get("jurisdiction", current.jurisdiction)),
            risk_tier=payload.model_extra.get("risk_tier", current.risk_tier),
            workflow_pack_id=payload.model_extra.get("workflow_pack_id"),
            workflow_pack_version=payload.model_extra.get("workflow_pack_version"),
        )
    elif event.event_type == CaseEventType.WORKFLOW_SELECTED:
        updates["workflow_pack_id"] = payload.model_extra.get("workflow_pack_id")
        updates["workflow_pack_version"] = payload.model_extra.get("workflow_pack_version")

    target = payload.new_state
    if target is not None:
        require_transition(current.state, target)
        if target == LegalCaseState.FAILED:
            updates["state_before_failure"] = current.state
        updates["state"] = target
        if target == LegalCaseState.COMPLETED:
            updates["completed_at"] = event.occurred_at
        if target == LegalCaseState.CANCELLED:
            updates["cancelled_at"] = event.occurred_at

    run_id = payload.model_extra.get("run_id")
    if event.event_type == CaseEventType.WORKFLOW_RUN_STARTED and run_id:
        updates["active_run_id"] = run_id
    elif event.event_type in {
        CaseEventType.WORKFLOW_RUN_COMPLETED,
        CaseEventType.CASE_CANCELLED,
        CaseEventType.CASE_FAILED,
    }:
        updates["active_run_id"] = None

    data["last_event_type"] = event.event_type.value
    data["last_event_payload"] = event.payload.model_dump(mode="json")
    updates["data"] = data
    return current.model_copy(update=updates)
