from app.extensions import db
from app.models import AgentSession, AuditEvent, ProviderConnection, User


def _provider(app, user_id: int = 1) -> int:
    with app.app_context():
        conn = ProviderConnection(
            user_id=user_id,
            provider="ollama",
            display_name="Ollama",
            auth_mode="none",
            base_url="http://localhost:11434/v1",
            default_model="qwen3",
        )
        db.session.add(conn)
        db.session.commit()
        return conn.id


def test_sessions_require_auth(client):
    assert client.get("/api/sessions").status_code == 401


def test_create_list_open_and_delete_session(authed_client, csrf_headers, app):
    provider_id = _provider(app)
    response = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id, "title": "Consulta juridica"},
        headers=csrf_headers,
    )
    assert response.status_code == 201
    session_id = response.get_json()["id"]

    response = authed_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "user", "content": "Necesito preparar una resolucion."},
        headers=csrf_headers,
    )
    assert response.status_code == 201

    listed = authed_client.get("/api/sessions").get_json()["sessions"]
    assert listed[0]["id"] == session_id
    opened = authed_client.get(f"/api/sessions/{session_id}").get_json()
    assert opened["messages"][0]["content"] == "Necesito preparar una resolucion."

    assert authed_client.delete(f"/api/sessions/{session_id}", headers=csrf_headers).status_code == 204
    assert authed_client.get(f"/api/sessions/{session_id}").status_code == 404


def test_session_rejects_another_users_provider(authed_client, csrf_headers, app):
    with app.app_context():
        other = User(email="other-session@example.test", display_name="Other")
        other.set_password("other-password-123")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    provider_id = _provider(app, other_id)
    response = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id},
        headers=csrf_headers,
    )
    assert response.status_code == 400


def test_session_isolation_between_users(authed_client, csrf_headers, app):
    provider_id = _provider(app)
    response = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id},
        headers=csrf_headers,
    )
    session_id = response.get_json()["id"]

    with app.app_context():
        session = db.session.get(AgentSession, session_id)
        session.user_id = 999
        db.session.commit()

    assert authed_client.get(f"/api/sessions/{session_id}").status_code == 404
    assert authed_client.delete(f"/api/sessions/{session_id}", headers=csrf_headers).status_code == 404


def test_message_role_is_validated(authed_client, csrf_headers, app):
    provider_id = _provider(app)
    session_id = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id},
        headers=csrf_headers,
    ).get_json()["id"]
    response = authed_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "developer", "content": "invalid"},
        headers=csrf_headers,
    )
    assert response.status_code == 400


def test_archive_restore_and_delete_session_are_audited(authed_client, csrf_headers, app):
    provider_id = _provider(app)
    created = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id, "title": "Expediente reservado"},
        headers=csrf_headers,
    )
    session_id = created.get_json()["id"]

    archived = authed_client.post(f"/api/sessions/{session_id}/archive", headers=csrf_headers)
    assert archived.status_code == 200
    assert archived.get_json()["archived_at"] is not None
    assert authed_client.get("/api/sessions").get_json()["sessions"] == []
    archived_list = authed_client.get("/api/sessions/archived").get_json()["sessions"]
    assert archived_list[0]["id"] == session_id
    assert authed_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"role": "user", "content": "No debe modificarse."},
        headers=csrf_headers,
    ).status_code == 409

    restored = authed_client.post(f"/api/sessions/{session_id}/restore", headers=csrf_headers)
    assert restored.status_code == 200
    assert restored.get_json()["archived_at"] is None

    assert authed_client.delete(f"/api/sessions/{session_id}", headers=csrf_headers).status_code == 204
    with app.app_context():
        events = AuditEvent.query.filter(AuditEvent.event.in_([
            "session.archive", "session.restore", "session.delete",
        ])).order_by(AuditEvent.id).all()
        assert [event.event for event in events] == [
            "session.archive", "session.restore", "session.delete",
        ]
        assert all(event.user_id == 1 for event in events)
        assert all(event.subject_id == str(session_id) for event in events)
        assert "Expediente reservado" in events[-1].details


def test_session_archive_is_isolated_between_users(authed_client, csrf_headers, app):
    provider_id = _provider(app)
    session_id = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id},
        headers=csrf_headers,
    ).get_json()["id"]
    with app.app_context():
        db.session.get(AgentSession, session_id).user_id = 999
        db.session.commit()

    assert authed_client.post(f"/api/sessions/{session_id}/archive", headers=csrf_headers).status_code == 404
    assert authed_client.post(f"/api/sessions/{session_id}/restore", headers=csrf_headers).status_code == 404


def test_running_session_cannot_be_archived_or_deleted(authed_client, csrf_headers, app):
    provider_id = _provider(app)
    session_id = authed_client.post(
        "/api/sessions",
        json={"provider_connection_id": provider_id},
        headers=csrf_headers,
    ).get_json()["id"]
    with app.app_context():
        db.session.get(AgentSession, session_id).status = "running"
        db.session.commit()

    assert authed_client.post(f"/api/sessions/{session_id}/archive", headers=csrf_headers).status_code == 409
    assert authed_client.delete(f"/api/sessions/{session_id}", headers=csrf_headers).status_code == 409
