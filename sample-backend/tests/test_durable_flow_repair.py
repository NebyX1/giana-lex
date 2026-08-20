import json
from uuid import uuid4

from app.extensions import db
from app.models import AgentSession, AuditEvent, Message, ProviderConnection, ToolCall
from legal.agents.case_conversation_router import CaseConversationIntent, CaseConversationRouter
from legal.domain.models import VerifiedAuthorityInput
from legal.infrastructure.models import (
    AgentRunRecord, CaseCommandRecord, DraftVersionRecord, FactAssertionRecord,
    HumanTaskRecord, LegalCaseRecord, ReviewFindingRecord, WorkflowRunRecord,
)


class VerifiedProvider:
    def retrieve(self, case_id, issues, facts):
        return [VerifiedAuthorityInput(
            issue_id=issue.issue_id,
            source_id=f"REPAIR-OFFICIAL-{issue.issue_id}",
            source_class="official_primary",
            jurisdiction="uruguay",
            exact_text=f"Texto oficial de prueba para {issue.category}.",
            proposition=f"Proposición verificada para {issue.category}.",
            norm_id=f"REPAIR-{issue.issue_id}",
            authenticity_verified=True,
            applicability_verified=True,
        ) for issue in issues]


def _csrf(client):
    return client.get("/api/auth/csrf").get_json()["csrf_token"]


def _post(client, path, key, payload=None):
    return client.post(path, json=payload, headers={
        "Idempotency-Key": key,
        "X-CSRFToken": _csrf(client),
    })


def _create_case(client, key, task_family="legal_question"):
    title = (
        "Necesito una resolución para renovar el contrato de mantenimiento."
        if task_family == "resolution_drafting"
        else f"Expediente {key}"
    )
    response = _post(client, "/api/legal/cases", key, {
        "title": title,
        "task_family": task_family,
        "jurisdiction": "lavalleja",
        "risk_tier": "high",
    })
    assert response.status_code == 201
    return response.get_json()["case"]["id"]


def _ready_case(client, app, key):
    app.extensions["legal_authority_provider"] = VerifiedProvider()
    case_id = _create_case(client, f"{key}-create", "resolution_drafting")
    _post(client, f"/api/legal/cases/{case_id}/commands/start", f"{key}-start")
    form_id = client.get(f"/api/legal/cases/{case_id}/workspace").get_json()["form"]["id"]
    _post(client, f"/api/legal/cases/{case_id}/commands/submit-form", f"{key}-form", {
        "form_id": form_id,
        "answers": {
            "expediente": "2026-REPAIR",
            "contract_object": "Mantenimiento del sistema",
            "contractor": "Proveedor de prueba",
            "original_contract": {"document_type": "contrato", "number": "REPAIR-1"},
            "current_end_date": "2026-09-01",
            "proposed_end_date": "2027-09-01",
            "amount": "1500",
            "budget_report": {"document_type": "informe_presupuestal", "number": "REPAIR-PRES"},
            "technical_report": {"document_type": "informe_tecnico", "number": "REPAIR-TEC"},
        },
    })
    with app.app_context():
        fact_ids = [item.id for item in FactAssertionRecord.query.filter_by(case_id=case_id).all()]
    response = _post(client, f"/api/legal/cases/{case_id}/commands/confirm-facts", f"{key}-confirm", {
        "fact_ids": fact_ids,
    })
    assert response.status_code == 202
    workspace = client.get(f"/api/legal/cases/{case_id}/workspace").get_json()
    assert workspace["case"]["state"] == "ready_for_human_review"
    return case_id, workspace["draft"]


def _review_payload(draft, approved=True, findings=None):
    return {
        "draft_id": draft["id"],
        "draft_version": draft["version"],
        "approved": approved,
        "findings": findings or [],
    }


def test_case_conversation_router_normalizes_all_operational_intents():
    router = CaseConversationRouter()
    assert router.classify("¡Dame el resultado!") == CaseConversationIntent.SHOW_RESULT
    assert router.classify("Dame el resultado de tu trabajo") == CaseConversationIntent.SHOW_RESULT
    assert router.classify("¿Cómo va?") == CaseConversationIntent.SHOW_STATUS
    assert router.classify("¿Ya terminó?") == CaseConversationIntent.SHOW_STATUS
    assert router.classify("¿Qué está haciendo?") == CaseConversationIntent.SHOW_STATUS
    assert router.classify("Continúa") == CaseConversationIntent.CONTINUE
    assert router.classify("¿Qué queda pendiente?") == CaseConversationIntent.SHOW_PENDING_ACTION
    assert router.classify("Abrir revisión humana") == CaseConversationIntent.OPEN_REVIEW
    assert router.classify("Quiero revisar el borrador") == CaseConversationIntent.OPEN_REVIEW
    assert router.classify("Exportar el documento en DOCX") == CaseConversationIntent.EXPORT_REQUEST
    assert router.classify("Exportar a DOCX") == CaseConversationIntent.EXPORT_REQUEST
    assert router.classify("¿Qué antecedente encontraste y qué falta?") == CaseConversationIntent.GENERAL_LEGAL_CHAT


def test_workspace_is_typed_and_derives_capabilities_and_activity(authed_client, app):
    case_id, draft = _ready_case(authed_client, app, "workspace-repair")
    payload = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()

    assert payload["schema_version"] == 1
    assert payload["case"]["id"] == case_id
    assert payload["snapshot"]["case_id"] == case_id
    assert payload["draft"] == draft
    assert payload["issues"]
    assert payload["evidence"]
    assert payload["activity"]["kind"] == "waiting_human_review"
    assert payload["activity"]["last_event_sequence"] == payload["last_event"]["sequence_number"]
    assert payload["activity"]["last_event_type"] == payload["last_event"]["event_type"]
    assert payload["capabilities"] == {
        "can_cancel": True,
        "can_edit_draft": False,
        "can_export_docx": True,
        "can_reject": True,
        "can_request_second_opinion": True,
        "can_review": True,
        "can_view_draft": True,
    }
    assert payload["blocking_reasons"] == []

    with app.app_context():
        case = db.session.get(LegalCaseRecord, case_id)
        run = WorkflowRunRecord.query.filter_by(case_id=case_id).order_by(
            WorkflowRunRecord.started_at.desc()
        ).first()
        run.status = "running"
        run.current_step = "repair_check"
        case.active_run_id = run.id
        db.session.commit()
    activity = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()["activity"]
    assert activity["kind"] == "working"
    assert activity["active_run_id"]
    assert activity["current_step"] == "repair_check"
    assert activity["started_at"]


def test_workspace_reports_recoverable_consistency_blockers(authed_client, app):
    draft_case = _create_case(authed_client, "consistency-draft")
    ready_case = _create_case(authed_client, "consistency-ready")
    completed_case = _create_case(authed_client, "consistency-completed")
    active_case = _create_case(authed_client, "consistency-active")
    with app.app_context():
        db.session.get(LegalCaseRecord, draft_case).state = "draft_ready"
        db.session.get(LegalCaseRecord, ready_case).state = "ready_for_human_review"
        db.session.get(LegalCaseRecord, completed_case).state = "completed"
        db.session.add(HumanTaskRecord(
            id=str(uuid4()), case_id=completed_case, task_type="review_draft",
            status="open", payload_json={"draft_version_id": str(uuid4())},
        ))
        db.session.get(LegalCaseRecord, active_case).active_run_id = str(uuid4())
        db.session.commit()

    def codes(case_id):
        response = authed_client.get(f"/api/legal/cases/{case_id}/workspace")
        assert response.status_code == 200
        reasons = response.get_json()["blocking_reasons"]
        assert all(item["recoverable"] is True for item in reasons)
        return {item["code"] for item in reasons}

    assert "draft_missing" in codes(draft_case)
    assert {"draft_missing", "review_task_missing"} <= codes(ready_case)
    assert {"draft_missing", "completed_with_open_review_task"} <= codes(completed_case)
    assert "active_run_missing" in codes(active_case)


def test_review_approve_rejects_stale_and_replays_without_duplicate_effects(authed_client, app):
    case_id, draft = _ready_case(authed_client, app, "approve-repair")
    with app.app_context():
        task = HumanTaskRecord.query.filter_by(
            case_id=case_id, task_type="review_draft", status="open"
        ).one()
        current_task_payload = dict(task.payload_json)
        task.payload_json = {"draft_version_id": str(uuid4())}
        db.session.commit()
    stale_task = _post(
        authed_client,
        f"/api/legal/cases/{case_id}/review",
        "approve-stale-task",
        _review_payload(draft),
    )
    assert stale_task.status_code == 409
    assert stale_task.get_json()["error"] == "draft_version_mismatch"
    with app.app_context():
        task = HumanTaskRecord.query.filter_by(
            case_id=case_id, task_type="review_draft", status="open"
        ).one()
        task.payload_json = current_task_payload
        db.session.commit()

    stale = _review_payload({**draft, "version": draft["version"] + 1})
    response = _post(authed_client, f"/api/legal/cases/{case_id}/review", "approve-stale", stale)
    assert response.status_code == 409
    assert response.get_json()["error"] == "draft_version_mismatch"

    payload = _review_payload(draft)
    first = _post(authed_client, f"/api/legal/cases/{case_id}/review", "approve-current", payload)
    replay = _post(authed_client, f"/api/legal/cases/{case_id}/review", "approve-current", payload)
    assert first.status_code == replay.status_code == 202
    assert replay.get_json()["idempotent_replay"] is True

    with app.app_context():
        assert db.session.get(LegalCaseRecord, case_id).state == "completed"
        task = HumanTaskRecord.query.filter_by(case_id=case_id, task_type="review_draft").one()
        assert task.status == "completed"
        assert task.completed_at is not None
        assert DraftVersionRecord.query.filter_by(case_id=case_id).count() == 1
        assert CaseCommandRecord.query.filter_by(case_id=case_id, command_type="submit_human_review").count() == 1
        audits = AuditEvent.query.filter_by(event="legal_case.review.approve", subject_id=case_id).all()
        assert len(audits) == 1
        details = json.loads(audits[-1].details)
        assert details["case_id"] == case_id
        assert details["draft_id"] == draft["id"]
        assert details["draft_version"] == draft["version"]
        assert "content" not in details and "findings" not in details
    event_types = [item["event_type"] for item in authed_client.get(
        f"/api/legal/cases/{case_id}/events"
    ).get_json()["events"]]
    assert "human_review.completed" in event_types


def test_review_reject_closes_task_and_persists_finding_without_replacing_draft(authed_client, app):
    case_id, draft = _ready_case(authed_client, app, "reject-repair")
    payload = _review_payload(draft, approved=False, findings=[{
        "severity": "high",
        "category": "competence",
        "description": "Debe verificarse la competencia del órgano.",
        "suggested_action": "Corregir la fundamentación.",
        "blocks_output": True,
    }])
    first = _post(authed_client, f"/api/legal/cases/{case_id}/review", "reject-current", payload)
    replay = _post(authed_client, f"/api/legal/cases/{case_id}/review", "reject-current", payload)
    assert first.status_code == replay.status_code == 202
    assert replay.get_json()["idempotent_replay"] is True

    with app.app_context():
        assert db.session.get(LegalCaseRecord, case_id).state == "blocked"
        task = HumanTaskRecord.query.filter_by(case_id=case_id, task_type="review_draft").one()
        assert task.status == "completed"
        assert DraftVersionRecord.query.filter_by(case_id=case_id).one().id == draft["id"]
        finding = ReviewFindingRecord.query.filter_by(
            case_id=case_id, draft_version_id=draft["id"], reviewer_type="human"
        ).one()
        assert finding.category == "competence"
        assert finding.blocks_output is True
        assert finding.finding_json["description"].startswith("Debe verificarse")
    events = authed_client.get(f"/api/legal/cases/{case_id}/events").get_json()["events"]
    rejection = next(item for item in events if item["event_type"] == "case.blocked" and
                     item["payload"].get("reason") == "human_review_rejected")
    assert rejection["payload"]["draft_id"] == draft["id"]
    assert rejection["payload"]["finding_count"] == 1
    assert "findings" not in rejection["payload"]


def test_show_result_is_deterministic_and_has_no_operational_side_effects(authed_client, csrf_headers, app):
    case_id, draft = _ready_case(authed_client, app, "chat-repair")
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="No call", auth_mode="none",
            base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(provider)
        db.session.flush()
        session = AgentSession(user_id=1, case_id=case_id, provider_connection_id=provider.id)
        db.session.add(session)
        db.session.commit()
        session_id = session.id
        before = {
            "commands": CaseCommandRecord.query.filter_by(case_id=case_id).count(),
            "runs": WorkflowRunRecord.query.filter_by(case_id=case_id).count(),
            "drafts": DraftVersionRecord.query.filter_by(case_id=case_id).count(),
            "agent_runs": AgentRunRecord.query.filter_by(case_id=case_id).count(),
            "tools": ToolCall.query.filter_by(session_id=session_id).count(),
        }

    app.extensions["llm_provider_factory"] = lambda _connection: (_ for _ in ()).throw(
        AssertionError("operational case chat must not create a provider")
    )
    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Dame el resultado de tu trabajo"},
        headers=csrf_headers,
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "event: case.ui.action" in body
    assert '"action": "focus_draft"' in body
    assert "event: assistant.completed" in body
    assert "event: agent.completed" in body
    assert body.index("case.ui.action") < body.index("assistant.completed") < body.index("agent.completed")
    assert "El borrador ya está generado y se encuentra disponible en el panel derecho." in body
    assert f"Versión: {draft['version']}." in body

    with app.app_context():
        session = db.session.get(AgentSession, session_id)
        after = {
            "commands": CaseCommandRecord.query.filter_by(case_id=case_id).count(),
            "runs": WorkflowRunRecord.query.filter_by(case_id=case_id).count(),
            "drafts": DraftVersionRecord.query.filter_by(case_id=case_id).count(),
            "agent_runs": AgentRunRecord.query.filter_by(case_id=case_id).count(),
            "tools": ToolCall.query.filter_by(session_id=session_id).count(),
        }
        assert after == before
        assert session.status == "completed"
        assert [(item.role, item.content) for item in Message.query.filter_by(
            session_id=session_id
        ).order_by(Message.id.asc())] == [
            ("user", "Dame el resultado de tu trabajo"),
            ("assistant", f"El borrador ya está generado y se encuentra disponible en el panel derecho. Versión: {draft['version']}. Estado: listo para revisión humana."),
        ]
        assert db.session.get(DraftVersionRecord, draft["id"]) is not None
