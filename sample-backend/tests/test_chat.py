from app.models import ProviderConnection


def test_chat_requires_auth(client, csrf_headers):
    resp = client.post(
        "/api/chat",
        json={"connection_id": 1, "messages": [{"role": "user", "content": "hi"}]},
        headers=csrf_headers,
    )
    assert resp.status_code == 401


def test_chat_requires_csrf(authed_client):
    resp = authed_client.post(
        "/api/chat",
        json={"connection_id": 1, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "csrf_failed"


def test_chat_rejects_missing_connection_id(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=csrf_headers,
    )
    assert resp.status_code == 400


def test_chat_rejects_unknown_connection(authed_client, csrf_headers):
    resp = authed_client.post(
        "/api/chat",
        json={"connection_id": 9999, "messages": [{"role": "user", "content": "hi"}]},
        headers=csrf_headers,
    )
    assert resp.status_code == 404


def test_chat_streams_from_provider(authed_client, csrf_headers, app, monkeypatch):
    with app.app_context():
        from app.extensions import db
        from app.services.credential_service import get_cipher
        cipher = get_cipher()
        conn = ProviderConnection(
            user_id=1,
            provider="featherless",
            display_name="Test",
            auth_mode="api_key",
            base_url="https://api.featherless.ai/v1",
            api_key_ciphertext=cipher.encrypt("test-key"),
            encryption_key_id=cipher.active_key_id,
            default_model="test-model",
        )
        db.session.add(conn)
        db.session.commit()
        conn_id = conn.id

    fake_lines = [
        'data: {"choices":[{"delta":{"content":"Hola"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":" mundo"}}]}',
        "",
        'data: [DONE]',
        "",
    ]

    class FakeResponse:
        status_code = 200
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def iter_lines(self):
            yield from fake_lines

    def fake_stream(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("httpx.stream", fake_stream)

    resp = authed_client.post(
        "/api/chat",
        json={"connection_id": conn_id, "messages": [{"role": "user", "content": "test"}]},
        headers=csrf_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["Deprecation"] == "true"
    body = resp.get_data(as_text=True)
    assert 'event: delta' in body
    assert "Hola" in body
    assert "mundo" in body
    assert "event: done" in body
