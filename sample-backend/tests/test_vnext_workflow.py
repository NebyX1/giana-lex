from hashlib import sha256
from uuid import uuid4

from app.extensions import db
from app.models import AgentSession, Message, ProviderConnection, User
from legal.domain.commands import CreateLegalCase
from legal.domain.enums import RiskTier, TaskFamily
from legal.domain.models import VerifiedAuthorityInput
from legal.application.command_service import LegalCommandService
from legal.evidence.service import citation_gate, verify_and_record
from legal.infrastructure.models import (
    CandidateAuthorityRecord, DraftVersionRecord, EvidenceSpanRecord, FactAssertionRecord,
    AgentRunRecord, FormInstanceRecord, LegalCaseRecord, LegalPropositionRecord, MemoryProposalRecord,
    OperationalMemoryRecord, PrecedentSelectionRecord, WorkflowPackVersionRecord,
)
from legal.research.service import plan_issues
from legal.workflows.loader import WorkflowPackRegistry
from pydantic import ValidationError
import pytest


def _csrf(client):
    return client.get("/api/auth/csrf").get_json()["csrf_token"]


def _post(client, path, key, json=None):
    return client.post(path, json=json, headers={"Idempotency-Key": key, "X-CSRFToken": _csrf(client)})


def _create_renewal(client, key="renewal-create"):
    response = _post(client, "/api/legal/cases", key, {
        "title": "Necesito una resolucion para renovar el contrato de mantenimiento del sistema X.",
        "task_family": "resolution_drafting", "jurisdiction": "lavalleja", "risk_tier": "high",
    })
    assert response.status_code == 201
    return response.get_json()["case"]["id"]


def _answers():
    return {
        "expediente": "2026-100", "contract_object": "Mantenimiento del sistema X",
        "contractor": "Proveedor de prueba, RUT TEST", "original_contract": {
            "document_type": "contrato", "number": "TEST-1",
        },
        "current_end_date": "2026-09-01", "proposed_end_date": "2027-09-01",
        "amount": "1234,50", "budget_report": {
            "document_type": "informe_presupuestal", "number": "TEST-PRESUPUESTO",
        },
        "technical_report": {
            "document_type": "informe_tecnico", "number": "TEST-TECNICO",
        },
    }


class FakeVerifiedProvider:
    def retrieve(self, case_id, issues, facts):
        return [VerifiedAuthorityInput(
            issue_id=issue.issue_id, source_id=f"FAKE-OFFICIAL-{issue.issue_id}",
            source_class="official_primary", jurisdiction="uruguay",
            exact_text=f"Texto oficial ficticio de prueba para {issue.category}.",
            proposition=f"Proposicion ficticia verificada para {issue.category}.",
            norm_id=f"TEST-{issue.issue_id}", authenticity_verified=True,
            applicability_verified=True, active=True,
        ) for issue in issues]


def test_contract_renewal_searches_precedent_before_persistent_form(authed_client, app):
    case_id = _create_renewal(authed_client)
    response = _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "renewal-start")
    assert response.status_code == 202
    case = authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]
    assert case["state"] == "awaiting_facts"
    assert case["workflow_pack_id"] == "resolution.contract_renewal"
    events = authed_client.get(f"/api/legal/cases/{case_id}/events").get_json()["events"]
    types = [item["event_type"] for item in events]
    assert types.index("precedent.search.started") < types.index("precedent.search.completed")
    assert types.index("precedent.search.completed") < types.index("precedent.not_found")
    assert types.index("precedent.search.completed") < types.index("precedent.fallback.selected")
    assert types.index("precedent.fallback.selected") < types.index("form.created")
    with app.app_context():
        selection = PrecedentSelectionRecord.query.filter_by(case_id=case_id).one()
        assert selection.match_type == "none"
        assert selection.confidence == 0
        assert selection.differences_json == []
        assert "comparabilidad material suficiente" in selection.fallback_reason
        assert FormInstanceRecord.query.filter_by(case_id=case_id).one().status == "open"
        assert WorkflowPackVersionRecord.query.filter_by(pack_id="resolution.contract_renewal").one().checksum
        assert all(item.verification_status == "unverified" for item in CandidateAuthorityRecord.query.filter_by(case_id=case_id))


def test_workspace_exposes_renderable_form_and_linked_conversation(authed_client, app):
    case_id = _create_renewal(authed_client, "workspace-create")
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "workspace-start")
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="Local",
            auth_mode="none", base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(provider)
        db.session.flush()
        session = AgentSession(user_id=1, case_id=case_id, title="Renovacion", provider_connection_id=provider.id)
        db.session.add(session)
        db.session.flush()
        db.session.add(Message(session_id=session.id, role="user", content="Necesito renovar el contrato."))
        db.session.commit()

    workspace = authed_client.get(f"/api/legal/cases/{case_id}/workspace")
    assert workspace.status_code == 200
    payload = workspace.get_json()
    assert payload["form"]["schema_json"]["sections"][0]["title"] == "Información requerida"
    assert payload["form"]["schema_json"]["sections"][0]["fields"]
    assert payload["messages"][0]["content"] == "Necesito renovar el contrato."
    assert "comparabilidad material suficiente" in payload["guidance"]

def test_progressive_form_persists_partial_and_normalizes_decimal(authed_client, app):
    case_id = _create_renewal(authed_client, "partial-create")
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "partial-start")
    form_id = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()["form"]["id"]
    partial = _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "partial-save", {
        "form_id": form_id, "answers": {"expediente": "2026-100"}, "partial": True,
    })
    assert partial.status_code == 202
    assert authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]["state"] == "awaiting_facts"
    complete = _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "full-save", {
        "form_id": form_id, "answers": _answers(), "partial": False,
    })
    assert complete.status_code == 202
    assert authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]["state"] == "validating_facts"
    with app.app_context():
        amount = FactAssertionRecord.query.filter_by(case_id=case_id, key="amount").one()
        assert amount.value_json == {"value": "1234.50"}
        assert amount.source_type == "user_answer"


def test_missing_verified_authority_blocks_without_draft(authed_client, app):
    case_id = _create_renewal(authed_client, "blocked-create")
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "blocked-start")
    form_id = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()["form"]["id"]
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "blocked-form", {
        "form_id": form_id, "answers": _answers(),
    })
    with app.app_context():
        fact_ids = [item.id for item in FactAssertionRecord.query.filter_by(case_id=case_id).all()]
    response = _post(authed_client, f"/api/legal/cases/{case_id}/commands/confirm-facts", "blocked-confirm", {
        "fact_ids": fact_ids,
    })
    assert response.status_code == 202
    assert authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]["state"] == "blocked"
    with app.app_context():
        assert DraftVersionRecord.query.filter_by(case_id=case_id).count() == 0
        assert LegalPropositionRecord.query.filter_by(case_id=case_id).count() == 0


def test_fake_verified_sources_reach_ready_for_human_review(authed_client, app):
    app.extensions["legal_authority_provider"] = FakeVerifiedProvider()
    case_id = _create_renewal(authed_client, "ready-create")
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/start", "ready-start")
    form_id = authed_client.get(f"/api/legal/cases/{case_id}/workspace").get_json()["form"]["id"]
    _post(authed_client, f"/api/legal/cases/{case_id}/commands/submit-form", "ready-form", {
        "form_id": form_id, "answers": _answers(),
    })
    with app.app_context():
        fact_ids = [item.id for item in FactAssertionRecord.query.filter_by(case_id=case_id).all()]
    confirmed = _post(authed_client, f"/api/legal/cases/{case_id}/commands/confirm-facts", "ready-confirm", {
        "fact_ids": fact_ids,
    })
    assert confirmed.status_code == 202
    assert authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]["state"] == "ready_for_human_review"
    with app.app_context():
        draft = DraftVersionRecord.query.filter_by(case_id=case_id).one()
        assert draft.status == "grounded_draft"
        assert draft.draft_json["title"].startswith("BORRADOR")
        assert draft.validation_json == {"errors": []}
        assert citation_gate(case_id) == []
        evidence_id = EvidenceSpanRecord.query.filter_by(case_id=case_id).first().id
        assert AgentRunRecord.query.filter_by(case_id=case_id, node_id="LEGAL_VERIFIER").one()
    evidence_response = authed_client.get(f"/api/legal/evidence/{evidence_id}")
    assert evidence_response.status_code == 200
    assert evidence_response.get_json()["proposition_ids"]
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="DOCX local", auth_mode="none",
            base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(provider)
        db.session.flush()
        session = AgentSession(user_id=1, case_id=case_id, provider_connection_id=provider.id)
        db.session.add(session)
        db.session.commit()
        session_id = session.id
    rendered = authed_client.post(
        f"/api/documents/sessions/{session_id}/generate-docx",
        json={"content": "este contenido libre debe ignorarse"},
        headers={"X-CSRFToken": _csrf(authed_client)},
    )
    assert rendered.status_code == 201
    assert rendered.get_json()["status"] == "BORRADOR"
    assert authed_client.get(rendered.get_json()["download_url"]).data.startswith(b"PK")
    reviewed = _post(authed_client, f"/api/legal/cases/{case_id}/review", "ready-review", {
        "draft_id": draft.id, "draft_version": draft.version,
        "approved": True, "findings": [],
    })
    assert reviewed.status_code == 202
    assert authed_client.get(f"/api/legal/cases/{case_id}").get_json()["case"]["state"] == "completed"


def test_source_policy_rejects_web_and_gate_detects_checksum(app):
    with app.app_context():
        command = CreateLegalCase(
            command_id=uuid4(), case_id=uuid4(), actor_user_id=1, idempotency_key="source-policy-case",
            title="Source policy", task_family=TaskFamily.RESOLUTION_DRAFTING,
            jurisdiction="lavalleja", risk_tier=RiskTier.HIGH,
        )
        LegalCommandService().create_case(command)
        case = db.session.get(LegalCaseRecord, str(command.case_id))
        pack = WorkflowPackRegistry().get("resolution.generic").pack
        issues = plan_issues(case.id, pack)
        with pytest.raises(ValidationError):
            VerifiedAuthorityInput(
                issue_id=issues[0].issue_id, source_id="web", source_class="web_untrusted",
                jurisdiction="lavalleja", exact_text="Texto web", proposition="Afirmacion web",
                authenticity_verified=True, applicability_verified=True,
            )
        official = VerifiedAuthorityInput(
            issue_id=issues[0].issue_id, source_id="official-test", source_class="official_primary",
            jurisdiction="uruguay", exact_text="Texto oficial ficticio.", proposition="Proposicion ficticia.",
            norm_id="ley:test:2026", source_version="test-checksum",
            source_url="https://www.impo.com.uy/bases/leyes/test-2026",
            authenticity_verified=True, applicability_verified=True,
        )
        accepted, _ = verify_and_record(case.id, issues, [official])
        assert len(accepted) == 1
        evidence = EvidenceSpanRecord.query.filter_by(case_id=case.id, source_id="official-test").one()
        evidence.checksum = sha256(b"different text").hexdigest()
        db.session.flush()
        assert f"checksum_mismatch:{evidence.id}" in citation_gate(case.id)


def test_memory_requires_reviewer_approval(authed_client, app):
    case_id = _create_renewal(authed_client, "memory-create")
    with app.app_context():
        proposal = MemoryProposalRecord(
            id=str(uuid4()), case_id=case_id, statement="Preferencia operativa de prueba.",
            scope="workflow", scope_ref="resolution.contract_renewal", sources_json={"case_ids": [case_id]},
            confidence="0.9", reason="Correccion humana de prueba", status="pending",
        )
        db.session.add(proposal)
        user = User.query.filter_by(email="funcionario@example.test").one()
        user.roles = [role for role in user.roles if role.name != "legal_reviewer"]
        db.session.commit()
        proposal_id = proposal.id
    denied = _post(authed_client, f"/api/legal/memory-proposals/{proposal_id}/approve", "memory-denied")
    assert denied.status_code == 403
    with app.app_context():
        user = User.query.filter_by(email="funcionario@example.test").one()
        from app.models import Role
        user.roles.append(Role.query.filter_by(name="legal_reviewer").one())
        db.session.commit()
    approved = _post(authed_client, f"/api/legal/memory-proposals/{proposal_id}/approve", "memory-approved")
    assert approved.status_code == 200
    with app.app_context():
        assert OperationalMemoryRecord.query.filter_by(proposal_id=proposal_id).one().active is True
