import logging
import uuid
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_file
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from agents import PydanticAgents
from config import Settings, settings as default_settings
from llm import LLMNotConfigured
from legal_knowledge import LegalKnowledgeService
from legal_knowledge.api import blueprint as legal_knowledge_blueprint
from legal_knowledge.cli import legal_cli
from legal_knowledge.database import LegalKnowledgeDatabase
from orchestrator import NotFoundError, OperationError, Orchestrator
from state import InvalidTransition, Stage
from storage import Storage
from tools.export_docx import export_markdown_docx
from identity.api import auth_bp
from identity.admin_api import admin_users_bp
from identity.commands import create_admin, create_user
from identity.extensions import cors, csrf, db, limiter, login_manager, mail, talisman
from identity.models import RBAC_ROLES, Role, User


def create_app(settings: Settings = default_settings, agents=None, database_path: Path | None = None, auth_test=False) -> Flask:
    app = Flask(__name__, template_folder="identity/templates")
    database_url = f"sqlite:///{Path(database_path).as_posix()}" if database_path is not None else settings.legal_database_url
    if database_url.startswith("sqlite:"):
        sqlite_path = make_url(database_url).database
        if sqlite_path and sqlite_path != ":memory:":
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    testing_bypass = database_path is not None and agents is not None and not auth_test
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        WTF_CSRF_ENABLED=not testing_bypass,
        TESTING_AUTH_BYPASS=testing_bypass,
        RATELIMIT_STORAGE_URI=settings.ratelimit_storage_uri,
        RATELIMIT_ENABLED=not testing_bypass,
        MAIL_SERVER=settings.mail_server,
        MAIL_PORT=settings.mail_port,
        MAIL_USE_TLS=settings.mail_use_tls,
        MAIL_USE_SSL=settings.mail_use_ssl,
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_DEFAULT_SENDER=settings.mail_default_sender,
        MAIL_SUPPRESS_SEND=settings.mail_suppress_send or auth_test,
        OTP_TTL_MINUTES=settings.otp_ttl_minutes,
        OTP_MAX_ATTEMPTS=settings.otp_max_attempts,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": [item.strip() for item in settings.cors_origins.split(",") if item.strip()]}}, supports_credentials=True)
    talisman.init_app(app, force_https=settings.force_https, content_security_policy={"default-src": "'none'", "frame-ancestors": "'none'"})
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_users_bp)
    app.cli.add_command(create_user)
    app.cli.add_command(create_admin)

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id)) if user_id.isdigit() else None
        return user if user and user.is_active else None

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
    def security_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", str(uuid.uuid4()))
        response.headers["Cache-Control"] = "no-store"
        return response

    if auth_test:
        with app.app_context():
            db.create_all()
            for name in RBAC_ROLES:
                if not Role.query.filter_by(name=name).first():
                    db.session.add(Role(name=name))
            db.session.commit()
    storage = Storage(database_path or settings.database_path)
    legal_database = None
    if database_path is not None:
        legal_database = LegalKnowledgeDatabase(f"sqlite:///{Path(database_path).as_posix()}")
    legal_knowledge = LegalKnowledgeService(settings, database=legal_database)
    if agents is None:
        agents = PydanticAgents(settings, legal_knowledge=legal_knowledge) if settings.llm_configured else None
    orchestrator = Orchestrator(settings, storage, agents, legal_knowledge=legal_knowledge)
    app.config["ORCHESTRATOR"] = orchestrator
    app.config["LEGAL_KNOWLEDGE"] = legal_knowledge
    app.config["SETTINGS"] = settings
    app.register_blueprint(legal_knowledge_blueprint)
    app.cli.add_command(legal_cli)

    def authenticated(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if app.config["TESTING_AUTH_BYPASS"]:
                return view(*args, **kwargs)
            return login_required(view)(*args, **kwargs)
        return wrapped

    def authorize_conversation(conversation_id):
        state = orchestrator.get(conversation_id)
        if app.config["TESTING_AUTH_BYPASS"]:
            return state
        if state.owner_user_id != current_user.id and not current_user.is_superuser:
            raise NotFoundError("Conversacion no encontrada")
        return state

    def response_for(state, message: str | None = None):
        return {
            "ok": True,
            "conversation_id": state.id,
            "stage": state.stage.value,
            "message": message or state.last_debug.get("message", ""),
            "examples": [match.model_dump() for match in state.selected_examples],
            "taxonomy_candidates": state.taxonomy_candidates,
            "selected_taxonomy_id": state.selected_taxonomy_id,
            "official_references": state.official_references,
            "form": state.current_form.model_dump() if state.current_form else None,
            "draft": state.draft,
            "approved": state.approved,
            "skills": orchestrator.skill_metadata() if state.approved else [],
            "skill_results": state.skill_results,
            "revision_count": state.revision_count,
            "debug": state.last_debug,
        }

    @app.errorhandler(OperationError)
    def operation_error(error):
        return jsonify({"ok": False, "error": error.code, "message": str(error), "retryable": error.retryable}), 400

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        return jsonify(error="csrf_failed", message="La solicitud segura venció o no es válida."), 400

    @app.errorhandler(InvalidTransition)
    def transition_error(error):
        return jsonify({"ok": False, "error": "invalid_stage", "message": str(error), "retryable": False}), 409

    @app.errorhandler(NotFoundError)
    def not_found(error):
        return jsonify({"ok": False, "error": "not_found", "message": str(error), "retryable": False}), 404

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.exception("Error no controlado")
        return jsonify({"ok": False, "error": "internal_error", "message": "Ocurrio un error interno", "retryable": False}), 500

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "llm_configured": settings.llm_configured,
                "model": settings.llm_model or None,
                "examples_count": len(list(settings.examples_dir.glob("*.md"))),
                "mold_available": (settings.molds_dir / "resolucion_basica.md").is_file(),
                "skills": list(orchestrator.skills),
                "legal_knowledge": legal_knowledge.index_status(),
            }
        )

    @app.post("/api/conversations")
    @authenticated
    def create_conversation():
        if orchestrator.agents is None:
            raise OperationError("llm_not_configured", "El proveedor LLM no esta configurado", False)
        data = request.get_json(silent=True) or {}
        owner_id = None if app.config["TESTING_AUTH_BYPASS"] else current_user.id
        return jsonify(response_for(orchestrator.create_conversation(data.get("message"), owner_id)))

    @app.get("/api/conversations")
    @authenticated
    def list_conversations():
        owner_id = None if app.config["TESTING_AUTH_BYPASS"] else current_user.id
        conversations = storage.list_for_owner(owner_id)
        return jsonify(conversations=[
            {
                "conversation_id": state.id,
                "title": state.original_request,
                "stage": state.stage.value,
                "updated_at": state.updated_at,
            }
            for state in conversations
        ])

    @app.get("/api/conversations/<conversation_id>")
    @authenticated
    def get_conversation(conversation_id):
        authorize_conversation(conversation_id)
        return jsonify(response_for(orchestrator.get(conversation_id)))

    @app.post("/api/conversations/<conversation_id>/form")
    @authenticated
    def submit_form(conversation_id):
        authorize_conversation(conversation_id)
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.submit_form(conversation_id, data.get("answers") or {})))

    @app.post("/api/conversations/<conversation_id>/revise")
    @authenticated
    def revise(conversation_id):
        authorize_conversation(conversation_id)
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.revise(conversation_id, data.get("instructions"))))

    @app.post("/api/conversations/<conversation_id>/approve")
    @authenticated
    def approve(conversation_id):
        authorize_conversation(conversation_id)
        return jsonify(response_for(orchestrator.approve(conversation_id)))

    @app.get("/api/skills")
    @authenticated
    def skills():
        return jsonify({"ok": True, "skills": orchestrator.skill_metadata()})

    @app.post("/api/conversations/<conversation_id>/skills/<key>")
    @authenticated
    def run_skill(conversation_id, key):
        authorize_conversation(conversation_id)
        data = request.get_json(silent=True) or {}
        return jsonify(response_for(orchestrator.run_skill(conversation_id, key, data.get("answers"))))

    @app.get("/api/conversations/<conversation_id>/export")
    @authenticated
    def export(conversation_id):
        state = authorize_conversation(conversation_id)
        if state.stage != Stage.APPROVED or not state.draft:
            raise InvalidTransition("Solo se puede exportar un borrador aprobado")
        return send_file(
            export_markdown_docx(state.draft),
            as_attachment=True,
            download_name=f"giana-lex-{state.id}.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
