from functools import wraps

from flask import current_app, jsonify
from flask_login import current_user

from .audit import record_event
from .extensions import db
from .models import Role, User, UserRole


def has_any_role(*roles):
    if current_app.config.get("TESTING_AUTH_BYPASS"):
        return True
    if not current_user.is_authenticated:
        return False
    user = db.session.get(User, current_user.id, populate_existing=True)
    if user is not None and user.is_active and user.is_superuser:
        return True
    return db.session.query(UserRole.id).join(Role, Role.id == UserRole.role_id).filter(
        UserRole.user_id == current_user.id, Role.name.in_(roles)
    ).first() is not None


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if has_any_role(*roles):
                return view(*args, **kwargs)
            record_event("authorization.denied", "denied", current_user.id if current_user.is_authenticated else None, subject_type="required_role", subject_id=",".join(roles), details={"endpoint": view.__name__})
            db.session.commit()
            return jsonify(error="forbidden", message="No tiene el rol requerido."), 403
        return wrapped
    return decorator
