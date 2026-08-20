import logging
import os
import uuid
from pathlib import Path

from flask import Flask, g, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .api import register_blueprints
from .commands import create_admin, create_user, examples_group
from .config import CONFIGS
from .errors import register_error_handlers
from .extensions import cors, csrf, db, limiter, login_manager, mail, migrate, talisman
from .models import User


def create_app(config_name: str | None = None) -> Flask:
    selected = config_name or os.getenv("FLASK_CONFIG", "development")
    config_class = CONFIGS.get(selected)
    if config_class is None:
        raise RuntimeError(f"Unknown FLASK_CONFIG: {selected}")
    if selected == "production":
        config_class.validate()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config["APP_ENV"] = selected
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if app.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    proxy_count = app.config["TRUSTED_PROXY_COUNT"]
    if proxy_count:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count, x_proto=proxy_count, x_host=proxy_count)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ALLOWED_ORIGINS"]}},
        supports_credentials=True,
    )
    limiter.init_app(app)
    talisman.init_app(
        app,
        force_https=app.config["FORCE_HTTPS"],
        content_security_policy={"default-src": "'none'", "frame-ancestors": "'none'"},
    )

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id)) if user_id.isdigit() else None

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(error="authentication_required", message="Autenticacion requerida."), 401

    @app.before_request
    def attach_request_id():
        candidate = request.headers.get("X-Request-ID", "")
        try:
            g.request_id = str(uuid.UUID(candidate)) if candidate else str(uuid.uuid4())
        except ValueError:
            g.request_id = str(uuid.uuid4())

    @app.after_request
    def security_response_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", str(uuid.uuid4()))
        response.headers["Cache-Control"] = "no-store"
        return response

    register_error_handlers(app)
    register_blueprints(app)
    from legal.bootstrap import initialize_authority_provider
    initialize_authority_provider(app)
    app.cli.add_command(create_admin)
    app.cli.add_command(create_user)
    app.cli.add_command(examples_group)
    return app
