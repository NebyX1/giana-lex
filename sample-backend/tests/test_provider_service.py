import base64
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import ProviderConnection
from app.services.credential_service import get_cipher
from app.services.provider_service import get_auth_header, refresh_oauth_token


def _jwt(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{encoded}.signature"


def test_openai_account_header_is_omitted_when_claim_is_absent(app):
    with app.app_context():
        cipher = get_cipher()
        conn = ProviderConnection(
            user_id=1,
            provider="openai",
            display_name="OpenAI",
            auth_mode="oauth",
            base_url="https://chatgpt.com/backend-api/codex",
            access_token_ciphertext=cipher.encrypt("not-a-jwt"),
            encryption_key_id=cipher.active_key_id,
        )
        headers = get_auth_header(conn)
        assert "ChatGPT-Account-Id" not in headers


def test_openai_account_header_uses_routing_claim(app):
    with app.app_context():
        cipher = get_cipher()
        token = _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct-123"}})
        conn = ProviderConnection(
            user_id=1,
            provider="openai",
            display_name="OpenAI",
            auth_mode="oauth",
            base_url="https://chatgpt.com/backend-api/codex",
            access_token_ciphertext=cipher.encrypt(token),
            encryption_key_id=cipher.active_key_id,
        )
        assert get_auth_header(conn)["ChatGPT-Account-Id"] == "acct-123"


def test_refresh_oauth_token_is_persisted(app, monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 600}

    monkeypatch.setattr("app.services.provider_service.httpx.post", lambda *args, **kwargs: Response())

    with app.app_context():
        cipher = get_cipher()
        conn = ProviderConnection(
            user_id=1,
            provider="openai",
            display_name="OpenAI",
            auth_mode="oauth",
            base_url="https://chatgpt.com/backend-api/codex",
            access_token_ciphertext=cipher.encrypt("old-access"),
            refresh_token_ciphertext=cipher.encrypt("old-refresh"),
            token_expires_at=datetime.utcnow() - timedelta(minutes=1),
            encryption_key_id=cipher.active_key_id,
        )
        db.session.add(conn)
        db.session.commit()
        conn_id = conn.id
        old_updated_at = conn.updated_at

        assert refresh_oauth_token(conn) is True
        db.session.expire_all()
        stored = db.session.get(ProviderConnection, conn_id)
        assert cipher.decrypt(stored.access_token_ciphertext, stored.encryption_key_id) == "new-access"
        assert cipher.decrypt(stored.refresh_token_ciphertext, stored.encryption_key_id) == "new-refresh"
        assert stored.updated_at >= old_updated_at
