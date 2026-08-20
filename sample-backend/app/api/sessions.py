from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..audit import record_event
from ..extensions import db
from ..models import AgentSession, Message, ProviderConnection


sessions_bp = Blueprint("sessions", __name__, url_prefix="/api/sessions")


def _owned_session(session_id: int) -> AgentSession | None:
    return AgentSession.query.filter_by(id=session_id, user_id=current_user.id).first()


@sessions_bp.post("")
@login_required
def create_session():
    data = request.get_json(silent=True) or {}
    provider_connection_id = data.get("provider_connection_id")
    provider = ProviderConnection.query.filter_by(
        id=provider_connection_id,
        user_id=current_user.id,
    ).first()
    if provider is None:
        return jsonify(error="invalid_provider", message="Conexion de proveedor no encontrada."), 400

    title = str(data.get("title") or "Nueva conversacion").strip()[:200]
    model = str(data.get("model") or provider.default_model or "").strip()[:200] or None
    session = AgentSession(
        user_id=current_user.id,
        provider_connection_id=provider.id,
        title=title,
        model=model,
    )
    db.session.add(session)
    record_event("session.create", "completed", current_user.id)
    db.session.commit()
    return jsonify(session.to_json()), 201


@sessions_bp.get("")
@login_required
def list_sessions():
    sessions = (
        AgentSession.query.filter_by(user_id=current_user.id, archived_at=None)
        .order_by(AgentSession.updated_at.desc())
        .all()
    )
    return jsonify(sessions=[session.to_json() for session in sessions])


@sessions_bp.get("/archived")
@login_required
def list_archived_sessions():
    sessions = (
        AgentSession.query.filter(
            AgentSession.user_id == current_user.id,
            AgentSession.archived_at.is_not(None),
        )
        .order_by(AgentSession.archived_at.desc())
        .all()
    )
    return jsonify(sessions=[session.to_json() for session in sessions])


@sessions_bp.get("/<int:session_id>")
@login_required
def get_session(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    return jsonify(session.to_json(include_messages=True))


@sessions_bp.delete("/<int:session_id>")
@login_required
def delete_session(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.status == "running":
        return jsonify(error="session_running", message="Espere a que termine la ejecucion antes de eliminar."), 409
    audit_details = {
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "was_archived": session.archived_at is not None,
    }
    db.session.delete(session)
    record_event(
        "session.delete",
        "completed",
        current_user.id,
        subject_type="agent_session",
        subject_id=session_id,
        details=audit_details,
    )
    db.session.commit()
    return "", 204


@sessions_bp.post("/<int:session_id>/archive")
@login_required
def archive_session(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.status == "running":
        return jsonify(error="session_running", message="Espere a que termine la ejecucion antes de archivar."), 409
    if session.archived_at is None:
        session.archived_at = datetime.utcnow()
        record_event(
            "session.archive",
            "completed",
            current_user.id,
            subject_type="agent_session",
            subject_id=session.id,
            details={"title": session.title},
        )
        db.session.commit()
    return jsonify(session.to_json())


@sessions_bp.post("/<int:session_id>/restore")
@login_required
def restore_session(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.archived_at is not None:
        session.archived_at = None
        session.updated_at = datetime.utcnow()
        record_event(
            "session.restore",
            "completed",
            current_user.id,
            subject_type="agent_session",
            subject_id=session.id,
            details={"title": session.title},
        )
        db.session.commit()
    return jsonify(session.to_json())


@sessions_bp.post("/<int:session_id>/messages")
@login_required
def create_message(session_id: int):
    session = _owned_session(session_id)
    if session is None:
        return jsonify(error="not_found", message="Sesion no encontrada."), 404
    if session.archived_at is not None:
        return jsonify(error="session_archived", message="Restaure la conversacion antes de continuar."), 409

    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "user")).strip()
    content = str(data.get("content", ""))
    if role != "user":
        return jsonify(error="invalid_role", message="Solo se aceptan mensajes externos de usuario."), 400
    if not content.strip():
        return jsonify(error="invalid_message", message="El contenido no puede estar vacio."), 400
    if len(content) > 50_000:
        return jsonify(error="invalid_message", message="El mensaje excede el limite."), 400

    message = Message(session_id=session.id, role=role, content=content)
    session.updated_at = datetime.utcnow()
    db.session.add(message)
    db.session.commit()
    return jsonify(message.to_json()), 201
