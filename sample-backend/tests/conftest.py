import pytest

from app import create_app
from app.extensions import db
from app.models import RBAC_ROLES, Role, User


@pytest.fixture(autouse=True)
def _offline_ip_safety(monkeypatch):
    """Keep SSRF DNS resolution offline during tests so validation is deterministic."""
    monkeypatch.setattr("impo.url.check_impo_ip_safety", lambda hostname: None)
    monkeypatch.setattr("depto.url.check_depto_ip_safety", lambda hostname: None)


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        db.session.add_all(Role(name=name) for name in sorted(RBAC_ROLES))
        user = User(email="funcionario@example.test", display_name="Funcionario de prueba")
        user.set_password("correct-password-123")
        db.session.add(user)
        user.roles = Role.query.all()
        db.session.commit()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf_headers(client):
    token = client.get("/api/auth/csrf").get_json()["csrf_token"]
    return {"X-CSRFToken": token}


@pytest.fixture()
def authed_client(client, csrf_headers, monkeypatch):
    monkeypatch.setattr(
        "app.api.auth.secrets.randbelow",
        lambda limit: 123456 if limit == 1_000_000 else 0,
    )
    client.get("/api/auth/captcha")
    with client.session_transaction() as session:
        captcha = str(session["login_captcha_result"])
    client.post(
        "/api/auth/login",
        json={
            "email": "funcionario@example.test",
            "password": "correct-password-123",
            "captcha": captcha,
        },
        headers=csrf_headers,
    )
    client.post("/api/auth/verify", json={"code": "123456"}, headers=csrf_headers)
    return client
