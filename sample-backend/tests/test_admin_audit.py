from app.audit import record_event
from app.extensions import db
from app.models import User


def _login_admin(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr("app.api.auth.secrets.randbelow", lambda _limit: 123456)
    with app.app_context():
        admin = User(
            email="audit-admin@test.uy",
            display_name="Auditora",
            is_superuser=True,
        )
        admin.set_password("correct-password-123")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    client.get("/api/auth/captcha")
    with client.session_transaction() as flask_session:
        captcha = str(flask_session["login_captcha_result"])
    client.post(
        "/api/auth/login",
        json={"email": "audit-admin@test.uy", "password": "correct-password-123", "captcha": captcha},
        headers=csrf_headers,
    )
    assert client.post("/api/auth/verify", json={"code": "123456"}, headers=csrf_headers).status_code == 200
    return admin_id


def test_audit_events_require_auditor_role(authed_client, app):
    with app.app_context():
        user = User.query.filter_by(email="funcionario@example.test").one()
        user.roles = [role for role in user.roles if role.name != "auditor"]
        db.session.commit()
    assert authed_client.get("/api/admin/audit-events").status_code == 403


def test_superuser_can_read_actor_and_session_details(app, client, csrf_headers, monkeypatch):
    admin_id = _login_admin(app, client, csrf_headers, monkeypatch)
    with app.test_request_context("/test", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        record_event(
            "session.archive",
            "completed",
            admin_id,
            subject_type="agent_session",
            subject_id=42,
            details={"title": "Consulta de prueba"},
        )
        db.session.commit()

    response = client.get("/api/admin/audit-events?event=session.&limit=10")
    assert response.status_code == 200
    event = response.get_json()["events"][0]
    assert event["event"] == "session.archive"
    assert event["subject_id"] == "42"
    assert event["details"]["title"] == "Consulta de prueba"
    assert event["user"]["display_name"] == "Auditora"
