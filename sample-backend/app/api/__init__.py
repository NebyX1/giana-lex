from .admin_audit import admin_audit_bp
from .admin_users import admin_users_bp
from .auth import auth_bp
from .agent import agent_bp
from .chat import chat_bp
from .departmental_norms import departmental_bp
from .documents import documents_bp
from .health import health_bp
from .national_norms import national_bp
from .legal_cases import legal_cases_bp
from .providers import providers_bp
from .sessions import sessions_bp


def register_blueprints(app) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(providers_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(national_bp)
    app.register_blueprint(legal_cases_bp)
    app.register_blueprint(departmental_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(admin_audit_bp)
