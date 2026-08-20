from app.models import ProviderConnection


def test_list_providers_requires_auth(client):
    assert client.get("/api/providers").status_code == 401


def test_create_and_list_api_key_provider(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/providers",
        json={
            "provider": "featherless",
            "display_name": "Featherless",
            "base_url": "https://api.featherless.ai/v1",
            "api_key": "fl-test-key-123",
            "default_model": "Qwen/Qwen3-Embedding-0.6B",
        },
        headers=csrf_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["provider"] == "featherless"
    assert data["auth_mode"] == "api_key"
    assert data["has_credentials"] is True
    conn_id = data["id"]

    resp = authed_client.get("/api/providers")
    assert resp.status_code == 200
    providers = resp.get_json()["providers"]
    assert len(providers) == 1
    assert providers[0]["id"] == conn_id
    assert "api_key" not in providers[0]
    assert "api_key_ciphertext" not in providers[0]


def test_create_ollama_no_key_provider(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/providers",
        json={
            "provider": "ollama",
            "display_name": "Ollama local",
            "base_url": "http://localhost:11434/v1",
        },
        headers=csrf_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["auth_mode"] == "none"
    assert data["has_credentials"] is False


def test_delete_provider(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/providers",
        json={
            "provider": "featherless",
            "display_name": "Test",
            "base_url": "https://api.featherless.ai/v1",
            "api_key": "key123",
        },
        headers=csrf_headers,
    )
    conn_id = resp.get_json()["id"]

    resp = authed_client.delete(f"/api/providers/{conn_id}", headers=csrf_headers)
    assert resp.status_code == 204

    resp = authed_client.get("/api/providers")
    assert len(resp.get_json()["providers"]) == 0


def test_cannot_see_other_users_providers(authed_client, csrf_headers, app):
    with app.app_context():
        from app.extensions import db
        from app.models import User
        other = User(email="other@example.test", display_name="Other")
        other.set_password("other-password-123")
        db.session.add(other)
        db.session.commit()
        conn = ProviderConnection(
            user_id=other.id,
            provider="featherless",
            display_name="Other's conn",
            auth_mode="api_key",
            base_url="https://api.featherless.ai/v1",
            api_key_ciphertext="encrypted",
        )
        db.session.add(conn)
        db.session.commit()
        other_conn_id = conn.id

    resp = authed_client.get("/api/providers")
    assert len(resp.get_json()["providers"]) == 0

    resp = authed_client.delete(f"/api/providers/{other_conn_id}", headers=csrf_headers)
    assert resp.status_code == 404


def test_reject_invalid_provider(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/providers",
        json={"provider": "unknown", "display_name": "X", "base_url": "https://x.com"},
        headers=csrf_headers,
    )
    assert resp.status_code == 400


def test_reject_ssrf_url(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/providers",
        json={
            "provider": "custom",
            "display_name": "Metadata",
            "base_url": "http://169.254.169.254/v1",
            "api_key": "x",
        },
        headers=csrf_headers,
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_url"


def test_oauth_authorize_requires_client_id(authed_client, csrf_headers, app):
    original = app.config["OPENAI_CLIENT_ID"]
    app.config["OPENAI_CLIENT_ID"] = ""
    resp = authed_client.post("/api/providers/openai/authorize", headers=csrf_headers)
    assert resp.status_code == 503
    app.config["OPENAI_CLIENT_ID"] = original


def test_oauth_authorize_returns_url(authed_client, csrf_headers):
    resp = authed_client.post("/api/providers/openai/authorize", headers=csrf_headers)
    assert resp.status_code == 200
    url = resp.get_json()["authorize_url"]
    assert "auth.openai.com" in url
    assert "client_id=test-client-id" in url
    assert "code_challenge_method=S256" in url