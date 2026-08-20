from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required

from ..audit import record_event
from ..extensions import db
from ..models import ProviderConnection
from ..services.provider_service import (
    build_authorize_url,
    create_connection,
    exchange_code,
    generate_pkce,
    generate_state,
    store_oauth_tokens,
)


providers_bp = Blueprint("providers", __name__, url_prefix="/api/providers")


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@providers_bp.get("")
@login_required
def list_providers():
    conns = ProviderConnection.query.filter_by(user_id=current_user.id).all()
    return jsonify(providers=[c.to_json() for c in conns])


@providers_bp.post("")
@login_required
def create_provider():
    data = _payload()
    provider = str(data.get("provider", "")).strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    base_url = str(data.get("base_url", "")).strip()
    default_model = str(data.get("default_model", "")).strip() or None
    api_key = str(data.get("api_key", "")).strip() or None

    if provider not in ("openai", "featherless", "ollama", "custom"):
        return jsonify(error="invalid_provider", message="Proveedor no soportado."), 400
    if not display_name:
        return jsonify(error="invalid_request", message="Nombre descriptivo requerido."), 400
    if provider != "ollama" and api_key is None:
        return jsonify(error="invalid_api_key", message="La API key no puede estar vacia."), 400

    try:
        conn = create_connection(
            user_id=current_user.id,
            provider=provider,
            display_name=display_name,
            base_url=base_url,
            default_model=default_model,
            api_key=api_key,
        )
    except ValueError as exc:
        return jsonify(error="invalid_url", message=str(exc)), 400

    db.session.add(conn)
    record_event("provider.create", "completed", current_user.id)
    db.session.commit()
    return jsonify(conn.to_json()), 201


@providers_bp.delete("/<int:conn_id>")
@login_required
def delete_provider(conn_id: int):
    conn = ProviderConnection.query.filter_by(id=conn_id, user_id=current_user.id).first()
    if not conn:
        return jsonify(error="not_found", message="Conexion no encontrada."), 404
    db.session.delete(conn)
    record_event("provider.delete", "completed", current_user.id)
    db.session.commit()
    return "", 204


@providers_bp.post("/openai/authorize")
@login_required
def openai_authorize():
    if not current_app.config["OPENAI_CLIENT_ID"]:
        return jsonify(error="oauth_not_configured", message="OPENAI_CLIENT_ID no esta configurado."), 503

    verifier, challenge = generate_pkce()
    state = generate_state()
    url = build_authorize_url(state, challenge)

    session["oauth_pkce_verifier"] = verifier
    session["oauth_state"] = state
    session["oauth_user_id"] = current_user.id
    session.permanent = True

    return jsonify(authorize_url=url)


@providers_bp.get("/openai/callback")
def openai_callback():
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error", "")

    if error:
        current_app.logger.warning("OpenAI OAuth returned an authorization error")
        return jsonify(error="oauth_error", message="OpenAI no autorizo la conexion."), 400

    saved_state = session.get("oauth_state")
    saved_verifier = session.get("oauth_pkce_verifier")
    saved_user_id = session.get("oauth_user_id")

    if not code or not state or state != saved_state or not saved_verifier or not saved_user_id:
        return jsonify(error="oauth_invalid", message="Estado o verificacion invalida."), 400

    try:
        token_data = exchange_code(code, saved_verifier)
    except Exception:
        current_app.logger.exception("OAuth token exchange failed")
        return jsonify(
            error="oauth_exchange_failed",
            message="No se pudo completar la conexion con OpenAI.",
        ), 502

    conn = ProviderConnection(
        user_id=saved_user_id,
        provider="openai",
        display_name="ChatGPT Plus/Pro",
        auth_mode="oauth",
        base_url=current_app.config["OPENAI_API_BASE_URL"],
    )
    store_oauth_tokens(conn, token_data)
    db.session.add(conn)
    record_event("provider.oauth", "completed", saved_user_id)
    db.session.commit()

    session.pop("oauth_pkce_verifier", None)
    session.pop("oauth_state", None)
    session.pop("oauth_user_id", None)

    return jsonify(status="connected", connection=conn.to_json())
