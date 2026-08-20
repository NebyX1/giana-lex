from dataclasses import replace

import pytest

from app import create_app
from config import settings
from identity.extensions import db, mail
from identity.mail_service import send_login_code
from identity.models import AuditEvent, EmailOtpCode, Role, User


@pytest.fixture
def auth_app(tmp_path):
    test_settings = replace(
        settings,
        database_path=tmp_path / "auth.sqlite3",
        legal_database_url=f"sqlite:///{(tmp_path / 'auth.sqlite3').as_posix()}",
        legal_storage_dir=tmp_path / "documents",
        mail_default_sender="tests@giana-lex.invalid",
        mail_suppress_send=True,
        secret_key="test-secret",
    )
    app = create_app(test_settings, database_path=test_settings.database_path, auth_test=True)
    app.testing = True
    with app.app_context():
        user = User(email="funcionario@example.test", display_name="Persona Jurídica")
        user.set_password("correct-password-123")
        user.roles.append(Role.query.filter_by(name="legal_user").one())
        db.session.add(user)
        db.session.commit()
    return app


@pytest.fixture
def auth_client(auth_app):
    return auth_app.test_client()


def csrf(client):
    return {"X-CSRFToken": client.get("/api/auth/csrf").get_json()["csrf_token"]}


def captcha(client):
    client.get("/api/auth/captcha")
    with client.session_transaction() as session:
        return str(session["login_captcha_result"])


def test_password_email_otp_and_logout(auth_app, auth_client, monkeypatch):
    monkeypatch.setattr("identity.api.secrets.randbelow", lambda limit: 123456 if limit == 1_000_000 else 0)
    headers = csrf(auth_client)
    response = auth_client.post("/api/auth/login", json={
        "email": "funcionario@example.test", "password": "correct-password-123", "captcha": captcha(auth_client),
    }, headers=headers)
    assert response.status_code == 202
    response = auth_client.post("/api/auth/verify", json={"code": "123456"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["user"]["roles"] == ["legal_user"]
    assert auth_client.get("/api/auth/me").status_code == 200
    assert auth_client.post("/api/auth/logout", headers=headers).status_code == 204
    assert auth_client.get("/api/auth/me").status_code == 401
    with auth_app.app_context():
        assert EmailOtpCode.query.one().consumed_at is not None
        assert AuditEvent.query.filter_by(event="auth.email_otp", status="accepted").count() == 1


def test_login_requires_csrf_and_captcha_is_single_use(auth_client):
    assert auth_client.post("/api/auth/login", json={"email": "x", "password": "x"}).get_json()["error"] == "csrf_failed"
    headers = csrf(auth_client)
    answer = captcha(auth_client)
    payload = {"email": "funcionario@example.test", "password": "wrong", "captcha": answer}
    assert auth_client.post("/api/auth/login", json=payload, headers=headers).status_code == 401
    response = auth_client.post("/api/auth/login", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_captcha"


def test_login_mail_has_plain_html_and_escapes_name(auth_app):
    with auth_app.app_context(), mail.record_messages() as outbox:
        send_login_code("persona@example.test", "<script>alert(1)</script>", "558190")
    assert len(outbox) == 1
    assert "Tu código de acceso es: 558190" in outbox[0].body
    assert "Código de un solo uso" in outbox[0].html
    assert "&lt;script&gt;" in outbox[0].html
