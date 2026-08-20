import pytest


def _create_user(app, email, display_name, password, superuser=False):
    from app.extensions import db
    from app.models import User
    with app.app_context():
        user = User(email=email, display_name=display_name, is_superuser=superuser)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, csrf_headers, email, password, code="123456"):
    client.get("/api/auth/captcha")
    with client.session_transaction() as session:
        captcha = str(session["login_captcha_result"])
    client.post(
        "/api/auth/login",
        json={"email": email, "password": password, "captcha": captcha},
        headers=csrf_headers,
    )
    return client.post("/api/auth/verify", json={"code": code}, headers=csrf_headers)


class TestAdminUsers:
    def test_list_requires_auth(self, client):
        assert client.get("/api/admin/users").status_code == 401

    def test_non_superuser_forbidden(self, authed_client):
        # conftest authed_client is a non-superuser
        assert authed_client.get("/api/admin/users").status_code == 403

    def test_superuser_can_create_and_list(self, app, client, csrf_headers, monkeypatch):
        monkeypatch.setattr("app.api.auth.secrets.randbelow", lambda _limit: 123456)
        _create_user(app, "admin@test.uy", "Admin", "correct-password-123", superuser=True)
        login = _login(client, csrf_headers, "admin@test.uy", "correct-password-123")
        assert login.status_code == 200

        # list
        r = client.get("/api/admin/users")
        assert r.status_code == 200
        body = r.get_json()
        assert any(u["email"] == "admin@test.uy" and u["is_superuser"] for u in body["users"])

        # create a new user
        r = client.post(
            "/api/admin/users",
            json={"email": "nuevo@test.uy", "display_name": "Nuevo", "password": "clave-segura-123"},
            headers=csrf_headers,
        )
        assert r.status_code == 201
        new_id = r.get_json()["user"]["id"]

        # duplicate email rejected
        r = client.post(
            "/api/admin/users",
            json={"email": "nuevo@test.uy", "display_name": "Otro", "password": "clave-segura-123"},
            headers=csrf_headers,
        )
        assert r.status_code == 409

        # short password rejected
        r = client.post(
            "/api/admin/users",
            json={"email": "corta@test.uy", "display_name": "Corta", "password": "short"},
            headers=csrf_headers,
        )
        assert r.status_code == 400

        # update (deactivate)
        r = client.patch(
            f"/api/admin/users/{new_id}",
            json={"is_active": False},
            headers=csrf_headers,
        )
        assert r.status_code == 200
        assert r.get_json()["user"]["is_active"] is False

        # self-deactivation forbidden: target the logged-in admin's own id
        my_id = next(u["id"] for u in client.get("/api/admin/users").get_json()["users"] if u["email"] == "admin@test.uy")
        r = client.patch(
            f"/api/admin/users/{my_id}",
            json={"is_active": False},
            headers=csrf_headers,
        )
        assert r.status_code == 400

        # delete
        r = client.delete(f"/api/admin/users/{new_id}", headers=csrf_headers)
        assert r.status_code == 204

    def test_superuser_cannot_delete_self(self, app, client, csrf_headers, monkeypatch):
        monkeypatch.setattr("app.api.auth.secrets.randbelow", lambda _limit: 123456)
        admin_id = _create_user(app, "admin2@test.uy", "Admin2", "correct-password-123", superuser=True)
        _login(client, csrf_headers, "admin2@test.uy", "correct-password-123")
        r = client.delete(f"/api/admin/users/{admin_id}", headers=csrf_headers)
        assert r.status_code == 400
