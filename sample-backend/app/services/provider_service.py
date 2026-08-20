import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from flask import current_app

from ..extensions import db
from ..models import ProviderConnection
from .credential_service import get_cipher
from .url_validation import validate_provider_url


PROVIDER_DEFAULTS = {
    "openai": {
        "base_url": "https://chatgpt.com/backend-api/codex",
        "auth_mode": "oauth",
    },
    "featherless": {
        "base_url": "https://api.featherless.ai/v1",
        "auth_mode": "api_key",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "auth_mode": "none",
    },
}


def provider_defaults(provider: str) -> dict:
    return PROVIDER_DEFAULTS.get(provider, {"base_url": "", "auth_mode": "api_key"})


def create_connection(
    user_id: int,
    provider: str,
    display_name: str,
    base_url: str = "",
    default_model: str | None = None,
    api_key: str | None = None,
) -> ProviderConnection:
    defaults = provider_defaults(provider)
    auth_mode = defaults["auth_mode"]
    url = base_url or defaults["base_url"]
    url = validate_provider_url(url)

    conn = ProviderConnection(
        user_id=user_id,
        provider=provider,
        display_name=display_name,
        auth_mode=auth_mode,
        base_url=url,
        default_model=default_model,
    )

    cipher = get_cipher()
    conn.encryption_key_id = cipher.active_key_id

    if auth_mode == "api_key" and api_key:
        conn.api_key_ciphertext = cipher.encrypt(api_key)
    elif auth_mode == "oauth":
        conn.access_token_ciphertext = None
        conn.refresh_token_ciphertext = None

    return conn


def resolve_connection(connection_id: int, user_id: int) -> ProviderConnection:
    conn = ProviderConnection.query.filter_by(id=connection_id, user_id=user_id).first()
    if conn is None:
        return None
    return conn


def get_auth_header(conn: ProviderConnection) -> dict:
    cipher = get_cipher()
    headers = {}
    if conn.auth_mode == "api_key" and conn.api_key_ciphertext:
        key = cipher.decrypt(conn.api_key_ciphertext, conn.encryption_key_id)
        headers["Authorization"] = f"Bearer {key}"
    elif conn.auth_mode == "oauth" and conn.access_token_ciphertext:
        token = cipher.decrypt(conn.access_token_ciphertext, conn.encryption_key_id)
        headers["Authorization"] = f"Bearer {token}"
        if conn.provider == "openai":
            headers["originator"] = current_app.config["OPENAI_ORIGINATOR"]
            account_id = _extract_chatgpt_account_id(token)
            if account_id:
                headers["ChatGPT-Account-Id"] = account_id
    return headers


def _extract_chatgpt_account_id(access_token: str) -> str | None:
    """Read the routing claim without treating it as verified identity."""
    try:
        payload_part = access_token.split(".")[1]
        padding = "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part + padding))
    except (IndexError, ValueError, json.JSONDecodeError):
        return None

    auth_claim = payload.get("https://api.openai.com/auth", {})
    candidates = (
        auth_claim.get("chatgpt_account_id") if isinstance(auth_claim, dict) else None,
        payload.get("chatgpt_account_id"),
        payload.get("account_id"),
    )
    return next((value for value in candidates if isinstance(value, str) and value), None)


def refresh_oauth_token(conn: ProviderConnection) -> bool:
    if conn.auth_mode != "oauth" or not conn.refresh_token_ciphertext:
        return False
    cipher = get_cipher()
    refresh_token = cipher.decrypt(conn.refresh_token_ciphertext, conn.encryption_key_id)

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": current_app.config["OPENAI_CLIENT_ID"],
    }
    client_secret = current_app.config.get("OPENAI_CLIENT_SECRET")
    if client_secret:
        data["client_secret"] = client_secret

    try:
        resp = httpx.post(
            current_app.config["OPENAI_TOKEN_URL"],
            data=data,
            timeout=current_app.config["PROVIDER_CONNECT_TIMEOUT"],
        )
        resp.raise_for_status()
    except Exception:
        return False

    token_data = resp.json()
    conn.access_token_ciphertext = cipher.encrypt(token_data["access_token"])
    if token_data.get("refresh_token"):
        conn.refresh_token_ciphertext = cipher.encrypt(token_data["refresh_token"])
    expires_in = token_data.get("expires_in", 3600)
    conn.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    conn.encryption_key_id = cipher.active_key_id
    conn.updated_at = datetime.utcnow()
    db.session.commit()
    return True


def ensure_valid_token(conn: ProviderConnection) -> bool:
    if conn.auth_mode != "oauth":
        return True
    if conn.token_expires_at and datetime.utcnow() >= conn.token_expires_at:
        return refresh_oauth_token(conn)
    return True


# --- OAuth PKCE flow ---


def generate_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorize_url(state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": current_app.config["OPENAI_CLIENT_ID"],
        "redirect_uri": current_app.config["OPENAI_REDIRECT_URI"],
        "scope": "openid profile email offline_access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": current_app.config["OPENAI_ORIGINATOR"],
    }
    return f"{current_app.config['OPENAI_AUTHORIZE_URL']}?{urlencode(params)}"


def exchange_code(code: str, verifier: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": current_app.config["OPENAI_REDIRECT_URI"],
        "client_id": current_app.config["OPENAI_CLIENT_ID"],
        "code_verifier": verifier,
    }
    client_secret = current_app.config.get("OPENAI_CLIENT_SECRET")
    if client_secret:
        data["client_secret"] = client_secret

    resp = httpx.post(
        current_app.config["OPENAI_TOKEN_URL"],
        data=data,
        timeout=current_app.config["PROVIDER_CONNECT_TIMEOUT"],
    )
    resp.raise_for_status()
    return resp.json()


def store_oauth_tokens(conn: ProviderConnection, token_data: dict) -> None:
    cipher = get_cipher()
    conn.access_token_ciphertext = cipher.encrypt(token_data["access_token"])
    if token_data.get("refresh_token"):
        conn.refresh_token_ciphertext = cipher.encrypt(token_data["refresh_token"])
    expires_in = token_data.get("expires_in", 3600)
    conn.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    conn.encryption_key_id = cipher.active_key_id
    conn.updated_at = datetime.utcnow()
