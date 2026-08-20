import json

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..audit import record_event
from ..authorization import has_any_role
from ..extensions import db
from ..models import AuditEvent, User


admin_audit_bp = Blueprint("admin_audit", __name__, url_prefix="/api/admin/audit-events")


def _details(event: AuditEvent) -> dict:
    try:
        value = json.loads(event.details) if event.details else {}
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


@admin_audit_bp.get("")
@login_required
def list_audit_events():
    if not has_any_role("auditor"):
        record_event("admin.audit", "denied", current_user.id)
        db.session.commit()
        return jsonify(error="forbidden", message="Requiere privilegios de administrador."), 403

    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    event_prefix = str(request.args.get("event", "")).strip()
    query = AuditEvent.query
    if event_prefix:
        query = query.filter(AuditEvent.event.startswith(event_prefix))
    events = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit).all()
    user_ids = {event.user_id for event in events if event.user_id is not None}
    users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return jsonify(events=[{
        "id": event.id,
        "event": event.event,
        "status": event.status,
        "subject_type": event.subject_type,
        "subject_id": event.subject_id,
        "details": _details(event),
        "ip_address": event.ip_address,
        "created_at": event.created_at.isoformat(),
        "user": {
            "id": event.user_id,
            "display_name": users[event.user_id].display_name if event.user_id in users else None,
            "email": users[event.user_id].email if event.user_id in users else None,
        } if event.user_id is not None else None,
    } for event in events])
