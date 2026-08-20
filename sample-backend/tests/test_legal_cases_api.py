from app.extensions import db
from app.models import User
from legal.infrastructure.models import (
    CaseCommandRecord,
    CaseEventRecord,
    CaseSnapshotRecord,
    LegalCaseRecord,
    OutboxEventRecord,
    WorkflowRunRecord,
    WorkflowStepRunRecord,
)
from legal.cases.repository import LegalCaseRepository
from legal.domain.enums import CaseEventType
from legal.domain.errors import ConcurrentCaseUpdateError
from legal.domain.events import NewCaseEvent
from datetime import datetime
from uuid import UUID, uuid4
import pytest


def create_case(client, key="case-create-1", title="Consulta juridica"):
    csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
    return client.post(
        "/api/legal/cases",
        json={"title": title, "task_family": "legal_question", "jurisdiction": "lavalleja"},
        headers={"Idempotency-Key": key, "X-CSRFToken": csrf},
    )


def test_create_is_idempotent_and_snapshot_is_transactional(authed_client, app):
    first = create_case(authed_client)
    second = create_case(authed_client)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["case"]["id"] == second.get_json()["case"]["id"]
    assert second.get_json()["idempotent_replay"] is True
    case_id = first.get_json()["case"]["id"]

    snapshot = authed_client.get(f"/api/legal/cases/{case_id}/snapshot").get_json()["snapshot"]
    events = authed_client.get(f"/api/legal/cases/{case_id}/events").get_json()["events"]
    assert snapshot["state"] == "new"
    assert snapshot["state_version"] == 1
    assert snapshot["last_sequence_number"] == 1
    assert [item["event_type"] for item in events] == ["case.created"]

    with app.app_context():
        assert LegalCaseRecord.query.count() == 1
        assert CaseCommandRecord.query.count() == 1
        assert CaseEventRecord.query.count() == 1
        assert CaseSnapshotRecord.query.count() == 1
        assert OutboxEventRecord.query.count() == 0


def test_repository_rejects_stale_expected_version(authed_client, app):
    case_id = create_case(authed_client, "locking-case").get_json()["case"]["id"]
    with app.app_context(), pytest.raises(ConcurrentCaseUpdateError):
        LegalCaseRepository().append_event(
            UUID(case_id),
            0,
            NewCaseEvent(
                event_type=CaseEventType.WORKFLOW_RUN_COMPLETED,
                command_id=uuid4(),
                payload={"run_id": str(uuid4())},
                occurred_at=datetime.utcnow(),
            ),
        )


def test_inline_workflow_persists_run_steps_events_and_outbox(authed_client, app):
    case_id = create_case(authed_client, "case-workflow").get_json()["case"]["id"]
    csrf = authed_client.get("/api/auth/csrf").get_json()["csrf_token"]
    response = authed_client.post(
        f"/api/legal/cases/{case_id}/start",
        headers={"Idempotency-Key": "workflow-start-1", "X-CSRFToken": csrf},
    )

    assert response.status_code == 202
    assert response.get_json()["status"] == "completed"
    replay = authed_client.post(
        f"/api/legal/cases/{case_id}/start",
        headers={"Idempotency-Key": "workflow-start-1", "X-CSRFToken": csrf},
    )
    assert replay.get_json()["idempotent_replay"] is True

    events = authed_client.get(f"/api/legal/cases/{case_id}/events").get_json()["events"]
    assert [item["sequence_number"] for item in events] == [1, 2, 3, 4]
    assert [item["event_type"] for item in events] == [
        "case.created",
        "workflow.run.started",
        "workflow.step.completed",
        "workflow.run.completed",
    ]
    with app.app_context():
        run = WorkflowRunRecord.query.filter_by(case_id=case_id).one()
        step = WorkflowStepRunRecord.query.filter_by(run_id=run.id).one()
        assert run.status == "completed"
        assert step.status == "completed"
        assert step.output_json["checkpoint"] == "persisted"
        assert CaseCommandRecord.query.count() == 2
        assert OutboxEventRecord.query.filter_by(topic="legal.workflow.command").one().status == "published"


def test_sse_replays_after_last_event_id(authed_client):
    case_id = create_case(authed_client, "case-sse").get_json()["case"]["id"]
    csrf = authed_client.get("/api/auth/csrf").get_json()["csrf_token"]
    authed_client.post(
        f"/api/legal/cases/{case_id}/start",
        headers={"Idempotency-Key": "workflow-sse", "X-CSRFToken": csrf},
    )

    response = authed_client.get(
        f"/api/legal/cases/{case_id}/events/stream",
        headers={"Last-Event-ID": "2"},
    )
    body = response.get_data(as_text=True)
    assert response.mimetype == "text/event-stream"
    assert "id: 1\n" not in body
    assert "id: 2\n" not in body
    assert "id: 3\n" in body
    assert "id: 4\n" in body


def test_case_ownership_hides_resources(authed_client, app):
    case_id = create_case(authed_client, "owned-case").get_json()["case"]["id"]
    with app.app_context():
        other = User(email="otro@example.test", display_name="Otro")
        other.set_password("some-password-123")
        db.session.add(other)
        db.session.commit()
        LegalCaseRecord.query.filter_by(id=case_id).update({"owner_user_id": other.id})
        db.session.commit()

    assert authed_client.get(f"/api/legal/cases/{case_id}").status_code == 404
    assert authed_client.get(f"/api/legal/cases/{case_id}/snapshot").status_code == 404
    assert authed_client.get(f"/api/legal/cases/{case_id}/events").status_code == 404


def test_cancel_is_persisted_and_idempotent(authed_client):
    case_id = create_case(authed_client, "case-cancel").get_json()["case"]["id"]
    csrf = authed_client.get("/api/auth/csrf").get_json()["csrf_token"]
    response = authed_client.post(
        f"/api/legal/cases/{case_id}/cancel",
        json={"reason": "Solicitud del usuario"},
        headers={"Idempotency-Key": "cancel-1", "X-CSRFToken": csrf},
    )
    assert response.status_code == 202
    case = authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]
    assert case["state"] == "cancelled"
    assert case["cancelled_at"] is not None


def test_failed_step_can_be_retried(authed_client, app):
    case_id = create_case(authed_client, "retry-case").get_json()["case"]["id"]
    csrf = authed_client.get("/api/auth/csrf").get_json()["csrf_token"]
    authed_client.post(
        f"/api/legal/cases/{case_id}/start",
        headers={"Idempotency-Key": "retry-start", "X-CSRFToken": csrf},
    )
    with app.app_context():
        run = WorkflowRunRecord.query.filter_by(case_id=case_id).one()
        step = WorkflowStepRunRecord.query.filter_by(run_id=run.id).one()
        run.status = "failed"
        run.failed_at = datetime.utcnow()
        step.status = "failed"
        step.error = "transient"
        db.session.commit()
        step_id = step.id

    response = authed_client.post(
        f"/api/legal/cases/{case_id}/retry",
        json={"step_run_id": step_id},
        headers={"Idempotency-Key": "retry-command", "X-CSRFToken": csrf},
    )
    assert response.status_code == 202
    assert response.get_json()["status"] == "completed"
    with app.app_context():
        assert db.session.get(WorkflowStepRunRecord, step_id).status == "completed"
