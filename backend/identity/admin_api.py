from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from .audit import record_event
from .extensions import db
from .models import RBAC_ROLES, Role, User


admin_users_bp = Blueprint(
    "admin_users", __name__, url_prefix="/api/admin/users"
)


def _require_superuser():
    if not current_user.is_superuser:
        record_event("admin.users", "denied", current_user.id)
        db.session.commit()
        return jsonify(
            error="forbidden", message="Requiere privilegios de administrador."
        ), 403
    return None


def _user_json(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "roles": sorted(user.role_names),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": (
            user.last_login_at.isoformat() if user.last_login_at else None
        ),
    }


@admin_users_bp.post("")
@login_required
def create_user():
    denied = _require_superuser()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    password = str(data.get("password", ""))
    is_superuser = bool(data.get("is_superuser", False))
    requested_roles = data.get("roles", ["legal_user"])

    if not email or not display_name:
        return jsonify(
            error="invalid_request",
            message="email y display_name son requeridos.",
        ), 400
    if len(password) < 12:
        return jsonify(
            error="invalid_password",
            message="La contraseña debe tener al menos 12 caracteres.",
        ), 400
    if User.query.filter_by(email=email).first():
        return jsonify(
            error="duplicate_email",
            message="Ya existe un usuario con ese correo.",
        ), 409
    if (
        not isinstance(requested_roles, list)
        or not set(requested_roles) <= RBAC_ROLES
    ):
        return jsonify(error="invalid_roles", message="Roles invalidos."), 400

    user = User(
        email=email, display_name=display_name, is_superuser=is_superuser
    )
    user.set_password(password)
    db.session.add(user)
    role_names = RBAC_ROLES if is_superuser else requested_roles
    user.roles = Role.query.filter(Role.name.in_(role_names)).all()
    record_event("admin.users.create", "completed", current_user.id)
    db.session.commit()
    return jsonify(user=_user_json(user)), 201
