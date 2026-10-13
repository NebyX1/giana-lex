"""Explicit local testing entry point: use an existing account without logging in."""
from ipaddress import ip_address
from urllib.parse import urlsplit

from flask import current_app, jsonify, request

from identity.extensions import login_manager
from identity.models import User


def enable_local_testing(app):
    app.config["LOCAL_TESTING_NO_LOGIN"] = True

    @app.before_request
    def require_local_request():
        try:
            local_peer = ip_address(request.remote_addr or "").is_loopback
        except ValueError:
            local_peer = False
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        origin = request.headers.get("Origin")
        forwarded = any(request.headers.get(name) for name in ("Forwarded", "X-Forwarded-For", "X-Real-IP"))
        if (not local_peer or urlsplit(request.host_url).hostname not in local_hosts
                or (origin and urlsplit(origin).hostname not in local_hosts) or forwarded):
            return jsonify(error="local_testing_only", message="El modo de testing solo está disponible en este equipo."), 403

    @login_manager.request_loader
    def load_testing_user(_request):
        if not current_app.config.get("LOCAL_TESTING_NO_LOGIN"):
            return None
        return User.query.filter_by(is_active=True).order_by(User.is_superuser.desc(), User.id).first()

    app.logger.warning("Modo de testing local activo: acceso sin login en 127.0.0.1")
