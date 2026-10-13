from dataclasses import replace

import pytest

from app import create_app
from config import settings
from identity.extensions import db, mail
from identity.mail_service import send_login_code
from identity.models import AuditEvent, EmailOtpCode, Role, User
from local_testing import enable_local_testing


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


def test_local_testing_enters_without_password_or_email_code(auth_app):
    enable_local_testing(auth_app)
    client = auth_app.test_client()
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "funcionario@example.test"
    assert client.get("/api/conversations").status_code == 200
    assert client.get("/api/settings/examples").status_code == 200
    with auth_app.app_context():
        assert EmailOtpCode.query.count() == 0
    # Automatic testing access must not create a reusable authenticated cookie.
    with client.session_transaction() as session:
        assert "_user_id" not in session
    auth_app.config["LOCAL_TESTING_NO_LOGIN"] = False
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("headers,peer", [
    ({}, "203.0.113.10"),
    ({"Host": "example.test"}, "127.0.0.1"),
    ({"Origin": "https://example.test"}, "127.0.0.1"),
    ({"X-Forwarded-For": "203.0.113.10"}, "127.0.0.1"),
    ({"Forwarded": "for=203.0.113.10"}, "127.0.0.1"),
    ({}, ""),
])
def test_local_testing_rejects_remote_or_forwarded_access(auth_app, headers, peer):
    enable_local_testing(auth_app)
    response = auth_app.test_client().get("/api/auth/me", headers=headers, environ_overrides={"REMOTE_ADDR": peer})
    assert response.status_code == 403
    assert response.get_json()["error"] == "local_testing_only"


def test_mail_authentication_failure_invalidates_otp(auth_app, auth_client, monkeypatch):
    from smtplib import SMTPAuthenticationError

    def reject_mail(*_args):
        raise SMTPAuthenticationError(535, b"Incorrect authentication data")

    monkeypatch.setattr("identity.api.send_login_code", reject_mail)
    response = auth_client.post("/api/auth/login", json={
        "email": "funcionario@example.test", "password": "correct-password-123", "captcha": captcha(auth_client),
    }, headers=csrf(auth_client))
    assert response.status_code == 503
    assert "credenciales" in response.get_json()["message"]
    assert auth_client.get("/api/auth/me").status_code == 401
    with auth_app.app_context():
        assert EmailOtpCode.query.one().consumed_at is not None
