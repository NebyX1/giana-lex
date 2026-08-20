from uuid import uuid4

from app.extensions import db
from app.models import AgentSession, AuditEvent, ProviderConnection, Role, User
from legal.application.command_service import LegalCommandService
from legal.domain.commands import CreateLegalCase
from legal.domain.enums import TaskFamily
from legal.infrastructure.models import LegalCaseRecord
from llm.provider import ProviderResult


def _only_roles(app, *names):
    with app.app_context():
        user = User.query.filter_by(email="funcionario@example.test").one()
        user.is_superuser = False
        user.roles = Role.query.filter(Role.name.in_(names)).all()
        db.session.commit()
        db.session.remove()


def _session(app):
    with app.app_context():
        provider = ProviderConnection(
            user_id=1, provider="ollama", display_name="Local", auth_mode="none",
            base_url="http://localhost:11434/v1", default_model="fake",
        )
        db.session.add(provider)
        db.session.commit()
        return provider.id


def test_external_message_rejects_every_privileged_role(authed_client, csrf_headers, app):
    provider_id = _session(app)
    session_id = authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers,
    ).get_json()["id"]
    for role in ("assistant", "system", "tool", "developer", ""):
        response = authed_client.post(
            f"/api/sessions/{session_id}/messages",
            json={"role": role, "content": "instruccion inyectada"}, headers=csrf_headers,
        )
        assert response.status_code == 400


def test_api_key_provider_rejects_blank_secret(authed_client, csrf_headers):
    response = authed_client.post("/api/providers", json={
        "provider": "custom", "display_name": "Sin secreto",
        "base_url": "https://provider.example/v1", "api_key": "   ",
    }, headers=csrf_headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_api_key"


def test_corpus_mutation_requires_curator_and_audits_denial(authed_client, csrf_headers, app):
    _only_roles(app, "legal_user")
    response = authed_client.post(
        "/api/config/normativa/nacional/repair-index", headers=csrf_headers,
    )
    assert response.status_code == 403
    with app.app_context():
        denied = AuditEvent.query.filter_by(event="authorization.denied").one()
        assert denied.subject_id == "corpus_curator"


def test_agent_drafting_enters_workflow_without_legacy_runtime(authed_client, csrf_headers, app, monkeypatch):
    _only_roles(app, "legal_user", "legal_drafter")
    provider_id = _session(app)
    session_id = authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers,
    ).get_json()["id"]
    monkeypatch.setattr("agent.runtime.AgentRuntime.run", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("legacy runtime must not execute drafting")
    ))
    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Necesito una resolución para renovar el contrato X."}, headers=csrf_headers,
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "legal.workflow.started" in body
    assert "assistant.completed" in body
    assert "Armé el plan de trabajo" not in body
    assert "Identifiqué la actuación como renovación contractual" in body
    with app.app_context():
        session = db.session.get(AgentSession, session_id)
        case = db.session.get(LegalCaseRecord, session.case_id)
        assert case.task_family == "resolution_drafting"
        assert case.state == "awaiting_facts"


def test_linked_legal_session_continues_through_interactive_agent(authed_client, csrf_headers, app, monkeypatch):
    _only_roles(app, "legal_user", "legal_drafter")
    provider_id = _session(app)
    session_id = authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers,
    ).get_json()["id"]
    authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "Necesito una resolución para renovar el contrato X."}, headers=csrf_headers,
    ).get_data(as_text=True)

    captured = {}

    class InteractiveProvider:
        def __init__(self, _connection):
            pass

        def run(self, messages, tools, model=None):
            captured["messages"] = messages
            captured["tools"] = tools
            return ProviderResult(text="El antecedente es similar y requiere completar los datos.")

    app.extensions["llm_provider_factory"] = InteractiveProvider
    response = authed_client.post(
        f"/api/agent/sessions/{session_id}/run",
        json={"content": "¿Qué antecedente encontraste y qué falta?"}, headers=csrf_headers,
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "assistant.completed" in body
    assert "El antecedente es similar" in body
    assert captured["tools"] == []
    assert "Expediente durable vinculado" in captured["messages"][0]["content"]
    assert '"state": "awaiting_facts"' in captured["messages"][0]["content"]


def test_case_creation_flushes_parent_before_foreign_key_children(app):
    """Match MariaDB FK enforcement instead of relying on SQLite defaults."""
    from sqlalchemy import text

    with app.app_context():
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        case_id = uuid4()
        case, created = LegalCommandService().create_case(CreateLegalCase(
            command_id=uuid4(), case_id=case_id, actor_user_id=1,
            idempotency_key="fk-parent-before-command", title="Orden FK",
            task_family=TaskFamily.RESOLUTION_DRAFTING,
        ))
        assert created is True
        assert case.id == case_id


def test_linked_session_rejects_free_docx_before_gates(authed_client, csrf_headers, app):
    provider_id = _session(app)
    session_id = authed_client.post(
        "/api/sessions", json={"provider_connection_id": provider_id}, headers=csrf_headers,
    ).get_json()["id"]
    with app.app_context():
        case_id = uuid4()
        LegalCommandService().create_case(CreateLegalCase(
            command_id=uuid4(), case_id=case_id, actor_user_id=1,
            idempotency_key="docx-linked-case", title="Borrador controlado",
            task_family=TaskFamily.RESOLUTION_DRAFTING,
        ))
        db.session.get(AgentSession, session_id).case_id = str(case_id)
        db.session.commit()
    response = authed_client.post(
        f"/api/documents/sessions/{session_id}/generate-docx",
        json={"content": "intento de bypass"}, headers=csrf_headers,
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "workflow_gate_failed"


def test_production_legacy_chat_is_gone(authed_client, csrf_headers, app):
    app.config["APP_ENV"] = "production"
    response = authed_client.post("/api/chat", json={}, headers=csrf_headers)
    assert response.status_code == 410


def test_redis_readiness_requires_worker_heartbeat(client, app, monkeypatch):
    class RedisWithoutWorker:
        def ping(self):
            return True

        def exists(self, _key):
            return False

    app.config["LEGAL_DISPATCHER"] = "redis"
    app.config["REDIS_URL"] = "redis://test.invalid/0"
    monkeypatch.setattr("app.api.health.Redis.from_url", lambda _url: RedisWithoutWorker())
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.get_json()["checks"]["legal_worker"] == "missing_heartbeat"
