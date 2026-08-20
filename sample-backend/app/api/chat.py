from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from ..extensions import db, limiter
from ..services.chat_service import stream_chat
from ..services.provider_service import resolve_connection


chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@chat_bp.post("")
@login_required
@limiter.limit("20 per minute")
def chat():
    if current_app.config.get("APP_ENV") == "production":
        return jsonify(
            error="legacy_endpoint_gone",
            message="Use /api/agent o /api/legal/cases; este endpoint no admite controles juridicos.",
        ), 410
    data = _payload()
    connection_id = data.get("connection_id")
    model = str(data.get("model", "")).strip() or None
    messages = data.get("messages", [])

    if not connection_id:
        return jsonify(error="invalid_request", message="connection_id es requerido."), 400

    if not isinstance(messages, list) or len(messages) == 0:
        return jsonify(error="invalid_request", message="messages es requerido."), 400

    if len(messages) > current_app.config["CHAT_MAX_MESSAGES"]:
        return jsonify(error="invalid_request", message="Demasiados mensajes."), 400

    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    if total_chars > current_app.config["CHAT_MAX_MESSAGE_CHARS"]:
        return jsonify(error="invalid_request", message="Contenido excede el limite."), 400

    conn = resolve_connection(int(connection_id), current_user.id)
    if conn is None:
        return jsonify(error="not_found", message="Conexion no encontrada."), 404

    def generate():
        try:
            yield from stream_chat(conn, messages, model)
        finally:
            db.session.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Deprecation": "true",
            "Sunset": "Thu, 31 Dec 2026 23:59:59 GMT",
            "Link": '</api/agent>; rel="successor-version"',
        },
    )
