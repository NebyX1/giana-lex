from app.extensions import db
from app.models import AuditEvent, EmailOtpCode


def _captcha_answer(client) -> str:
    response = client.get("/api/auth/captcha")
    assert response.status_code == 200
    assert "+" in response.get_json()["captcha"]["question"]
    with client.session_transaction() as session:
        return str(session["login_captcha_result"])


def test_login_requires_csrf(client):
    response = client.post("/api/auth/login", json={"email": "x", "password": "x"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "csrf_failed"


def test_password_and_email_otp_login(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.auth.secrets.randbelow",
        lambda limit: 123456 if limit == 1_000_000 else 0,
    )
    captcha = _captcha_answer(client)
    response = client.post(
        "/api/auth/login",
        json={
            "email": "funcionario@example.test",
            "password": "correct-password-123",
            "captcha": captcha,
        },
        headers=csrf_headers,
    )
    assert response.status_code == 202
    assert response.get_json()["method"] == "email_otp"

    response = client.post("/api/auth/verify", json={"code": "123456"}, headers=csrf_headers)
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "funcionario@example.test"
    assert client.get("/api/auth/me").status_code == 200

    with app.app_context():
        assert EmailOtpCode.query.one().consumed_at is not None
        assert AuditEvent.query.filter_by(event="auth.email_otp", status="accepted").count() == 1


def test_invalid_password_is_generic(client, csrf_headers):
    captcha = _captcha_answer(client)
    response = client.post(
        "/api/auth/login",
        json={
            "email": "funcionario@example.test",
            "password": "wrong",
            "captcha": captcha,
        },
        headers=csrf_headers,
    )
    assert response.status_code == 401
    assert response.get_json()["error"] == "invalid_credentials"


def test_otp_attempt_limit(app, client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.auth.secrets.randbelow",
        lambda limit: 123456 if limit == 1_000_000 else 0,
    )
    captcha = _captcha_answer(client)
    client.post(
        "/api/auth/login",
        json={
            "email": "funcionario@example.test",
            "password": "correct-password-123",
            "captcha": captcha,
        },
        headers=csrf_headers,
    )
    for _ in range(app.config["OTP_MAX_ATTEMPTS"]):
        response = client.post("/api/auth/verify", json={"code": "000000"}, headers=csrf_headers)
        assert response.status_code == 401
    response = client.post("/api/auth/verify", json={"code": "123456"}, headers=csrf_headers)
    assert response.status_code == 401

    with app.app_context():
        assert db.session.query(EmailOtpCode).one().attempts == app.config["OTP_MAX_ATTEMPTS"]


def test_login_rejects_missing_or_incorrect_captcha(client, csrf_headers):
    response = client.post(
        "/api/auth/login",
        json={"email": "funcionario@example.test", "password": "correct-password-123"},
        headers=csrf_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_captcha"

    _captcha_answer(client)
    response = client.post(
        "/api/auth/login",
        json={
            "email": "funcionario@example.test",
            "password": "correct-password-123",
            "captcha": "99",
        },
        headers=csrf_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_captcha"


def test_captcha_is_single_use(client, csrf_headers):
    captcha = _captcha_answer(client)
    credentials = {
        "email": "funcionario@example.test",
        "password": "wrong",
        "captcha": captcha,
    }
    response = client.post("/api/auth/login", json=credentials, headers=csrf_headers)
    assert response.status_code == 401

    response = client.post("/api/auth/login", json=credentials, headers=csrf_headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_captcha"
