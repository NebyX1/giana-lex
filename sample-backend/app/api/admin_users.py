from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..audit import record_event
from ..extensions import db
from ..models import RBAC_ROLES, Role, User


admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/api/admin/users")


def _require_superuser() -> tuple[dict, int] | None:
    if not current_user.is_superuser:
        record_event("admin.users", "denied", current_user.id)
        db.session.commit()
        return jsonify(error="forbidden", message="Requiere privilegios de administrador."), 403
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
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _payload() -> dict:
    return request.get_json(silent=True) or {}


@admin_users_bp.get("")
@login_required
def list_users():
    denied = _require_superuser()
    if denied:
        return denied
    users = User.query.order_by(User.is_active.desc(), User.is_superuser.desc(), User.created_at.desc()).all()
    return jsonify(users=[_user_json(user) for user in users])


@admin_users_bp.post("")
@login_required
def create_user():
    denied = _require_superuser()
    if denied:
        return denied
    data = _payload()
    email = str(data.get("email", "")).strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    password = str(data.get("password", ""))
    is_superuser = bool(data.get("is_superuser", False))
    requested_roles = data.get("roles", ["legal_user"])

    if not email or not display_name:
        return jsonify(error="invalid_request", message="email y display_name son requeridos."), 400
    if len(password) < 12:
        return jsonify(error="invalid_password", message="La contraseña debe tener al menos 12 caracteres."), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="duplicate_email", message="Ya existe un usuario con ese correo."), 409
    if not isinstance(requested_roles, list) or not set(requested_roles) <= RBAC_ROLES:
        return jsonify(error="invalid_roles", message="Roles invalidos."), 400

    user = User(email=email, display_name=display_name, is_superuser=is_superuser)
    user.set_password(password)
    db.session.add(user)
    user.roles = Role.query.filter(Role.name.in_(RBAC_ROLES if is_superuser else requested_roles)).all()
    record_event("admin.users.create", "completed", current_user.id)
    db.session.commit()
    return jsonify(user=_user_json(user)), 201


@admin_users_bp.patch("/<int:user_id>")
@login_required
def update_user(user_id: int):
    denied = _require_superuser()
    if denied:
        return denied
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(error="not_found", message="Usuario no encontrado."), 404
    data = _payload()

    if "display_name" in data:
        user.display_name = str(data["display_name"]).strip()
    if "email" in data:
        email = str(data["email"]).strip().lower()
        dup = User.query.filter(User.email == email, User.id != user.id).first()
        if dup:
            return jsonify(error="duplicate_email", message="Ya existe un usuario con ese correo."), 409
        user.email = email
    if "is_superuser" in data:
        new_super = bool(data["is_superuser"])
        if user.is_superuser and not new_super:
            from sqlalchemy import func
            active_super = User.query.filter_by(is_superuser=True, is_active=True).count()
            if active_super <= 1:
                return jsonify(error="last_superuser", message="No puedes quitar el último superadmin activo."), 400
        user.is_superuser = new_super
        if new_super:
            user.roles = Role.query.filter(Role.name.in_(RBAC_ROLES)).all()
    if "roles" in data:
        requested_roles = data["roles"]
        if not isinstance(requested_roles, list) or not set(requested_roles) <= RBAC_ROLES:
            return jsonify(error="invalid_roles", message="Roles invalidos."), 400
        user.roles = Role.query.filter(Role.name.in_(requested_roles)).all()
    if "is_active" in data:
        new_active = bool(data["is_active"])
        if not new_active and user.id == current_user.id:
            return jsonify(error="self_deactivate", message="No puedes desactivar tu propio usuario."), 400
        if not new_active and user.is_superuser:
            from sqlalchemy import func
            active_super = User.query.filter_by(is_superuser=True, is_active=True).count()
            if active_super <= 1:
                return jsonify(error="last_superuser", message="No puedes desactivar al último superadmin activo."), 400
        user.is_active = new_active
    if "password" in data and data.get("password"):
        user.set_password(str(data["password"]))

    record_event("admin.users.update", "completed", current_user.id)
    db.session.commit()
    return jsonify(user=_user_json(user))


@admin_users_bp.delete("/<int:user_id>")
@login_required
def delete_user(user_id: int):
    denied = _require_superuser()
    if denied:
        return denied
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(error="not_found", message="Usuario no encontrado."), 404
    if user.id == current_user.id:
        return jsonify(error="self_delete", message="No puedes eliminar tu propio usuario."), 400
    if user.is_superuser:
        from sqlalchemy import func
        active_super = User.query.filter_by(is_superuser=True, is_active=True).count()
        if active_super <= 1:
            return jsonify(error="last_superuser", message="No puedes eliminar al último superadmin activo."), 400
    # Preserve audit by soft-deactivating if the user has related history.
    from ..models import AgentSession, EmailOtpCode
    has_history = (
        EmailOtpCode.query.filter_by(user_id=user.id).first() is not None
        or AgentSession.query.filter_by(user_id=user.id).first() is not None
    )
    if has_history:
        user.is_active = False
        db.session.commit()
        record_event("admin.users.deactivate", "completed", current_user.id)
        db.session.commit()
        return jsonify(message="Usuario desactivado por historial asociado.", user=_user_json(user))
    db.session.delete(user)
    record_event("admin.users.delete", "completed", current_user.id)
    db.session.commit()
    return "", 204
