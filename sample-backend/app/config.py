import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _origins_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BACKEND_ROOT / 'instance' / 'giana_lex.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    CORS_ALLOWED_ORIGINS = _origins()
    REDIS_URL = os.getenv("REDIS_URL", "")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI") or REDIS_URL or "memory://"

    # Durable legal case execution. MariaDB remains the source of truth.
    LEGAL_DISPATCHER = os.getenv("LEGAL_DISPATCHER", "inline")
    LEGAL_REDIS_STREAM = os.getenv("LEGAL_REDIS_STREAM", "giana:legal:commands")
    LEGAL_REDIS_CONSUMER_GROUP = os.getenv("LEGAL_REDIS_CONSUMER_GROUP", "legal-workers")
    LEGAL_REDIS_CONSUMER_NAME = os.getenv("LEGAL_REDIS_CONSUMER_NAME", "legal-worker-1")
    LEGAL_OUTBOX_MAX_ATTEMPTS = int(os.getenv("LEGAL_OUTBOX_MAX_ATTEMPTS", "5"))
    LEGAL_WORKER_MAX_RETRIES = int(os.getenv("LEGAL_WORKER_MAX_RETRIES", "5"))
    LEGAL_WORKER_CLAIM_IDLE_MS = int(os.getenv("LEGAL_WORKER_CLAIM_IDLE_MS", "30000"))
    LEGAL_WORKER_HEARTBEAT_KEY = os.getenv("LEGAL_WORKER_HEARTBEAT_KEY", "giana:legal:worker:heartbeat")
    LEGAL_WORKER_HEARTBEAT_TTL_SECONDS = int(os.getenv("LEGAL_WORKER_HEARTBEAT_TTL_SECONDS", "15"))
    LEGAL_CASE_LOCK_TTL_SECONDS = int(os.getenv("LEGAL_CASE_LOCK_TTL_SECONDS", "120"))
    LEGAL_SSE_WAIT_SECONDS = float(os.getenv("LEGAL_SSE_WAIT_SECONDS", "15"))
    LEGAL_SSE_POLL_INTERVAL = float(os.getenv("LEGAL_SSE_POLL_INTERVAL", "0.5"))

    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _as_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _as_bool("MAIL_USE_SSL")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
    OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "10"))
    OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))
    FORCE_HTTPS = _as_bool("FORCE_HTTPS")

    # Credential encryption (Fernet). Comma-separated: active_key_id:key_hex[,old_id:key_hex...]
    CREDENTIAL_ENCRYPTION_KEYS = os.getenv("CREDENTIAL_ENCRYPTION_KEYS", "")
    CREDENTIAL_ACTIVE_KEY_ID = os.getenv("CREDENTIAL_ACTIVE_KEY_ID", "")

    # ChatGPT Plus/Pro OAuth (same flow as OpenAI Codex / OpenCode)
    OPENAI_CLIENT_ID = os.getenv("OPENAI_CLIENT_ID", "")
    OPENAI_CLIENT_SECRET = os.getenv("OPENAI_CLIENT_SECRET", "")  # empty for public PKCE clients
    OPENAI_AUTHORIZE_URL = os.getenv("OPENAI_AUTHORIZE_URL", "https://auth.openai.com/oauth/authorize")
    OPENAI_TOKEN_URL = os.getenv("OPENAI_TOKEN_URL", "https://auth.openai.com/oauth/token")
    OPENAI_REDIRECT_URI = os.getenv("OPENAI_REDIRECT_URI", "http://localhost:1455/auth/callback")
    OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://chatgpt.com/backend-api/codex")
    OPENAI_ORIGINATOR = os.getenv("OPENAI_ORIGINATOR", "giana-lex")

    # Provider HTTP settings
    PROVIDER_CONNECT_TIMEOUT = float(os.getenv("PROVIDER_CONNECT_TIMEOUT", "10"))
    PROVIDER_READ_TIMEOUT = float(os.getenv("PROVIDER_READ_TIMEOUT", "120"))
    PROVIDER_ALLOWED_PRIVATE_HOSTS = _origins_list("PROVIDER_ALLOWED_PRIVATE_HOSTS")

    # Chat limits
    CHAT_MAX_MESSAGES = int(os.getenv("CHAT_MAX_MESSAGES", "50"))
    CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "12000"))
    AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "16"))
    AGENT_RUNS_PER_MINUTE = os.getenv("AGENT_RUNS_PER_MINUTE", "10 per minute")

    # Optional governance layer around the existing agent runtime.
    HARNESS_ENABLED = _as_bool("HARNESS_ENABLED", False)
    HARNESS_MODE = os.getenv("HARNESS_MODE", "adaptive")
    HARNESS_MAX_ITERATIONS = int(os.getenv("HARNESS_MAX_ITERATIONS", "16"))
    HARNESS_MAX_RETRIES = int(os.getenv("HARNESS_MAX_RETRIES", "2"))
    HARNESS_MAX_TOOL_CALLS = int(os.getenv("HARNESS_MAX_TOOL_CALLS", "15"))
    HARNESS_MAX_LLM_CALLS = int(os.getenv("HARNESS_MAX_LLM_CALLS", "10"))
    HARNESS_RETRY_BACKOFF_SECONDS = float(os.getenv("HARNESS_RETRY_BACKOFF_SECONDS", "0.75"))
    HARNESS_CONTEXT_MAX_CHARS = int(os.getenv("HARNESS_CONTEXT_MAX_CHARS", "24000"))
    HARNESS_DEBUG = _as_bool("HARNESS_DEBUG", False)
    LLM_CAPABILITY_PROFILE = os.getenv("LLM_CAPABILITY_PROFILE", "balanced")
    LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "")
    LLM_STRONG_MODEL = os.getenv("LLM_STRONG_MODEL", "")
    LLM_FALLBACK_MODELS = os.getenv("LLM_FALLBACK_MODELS", "")

    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
    FASTEMBED_MODEL = os.getenv(
        "FASTEMBED_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    DOCUMENT_MAX_BYTES = int(os.getenv("DOCUMENT_MAX_BYTES", str(20 * 1024 * 1024)))
    WEB_SEARCH_URL = os.getenv("WEB_SEARCH_URL", "")
    WEB_SEARCH_API_KEY = os.getenv("WEB_SEARCH_API_KEY", "")
    WEB_ALLOWED_HOSTS = _origins_list("WEB_ALLOWED_HOSTS")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"

    @classmethod
    def validate(cls) -> None:
        missing = []
        if not os.getenv("SECRET_KEY"):
            missing.append("SECRET_KEY")
        if not os.getenv("DATABASE_URL"):
            missing.append("DATABASE_URL")
        if not os.getenv("CREDENTIAL_ENCRYPTION_KEYS"):
            missing.append("CREDENTIAL_ENCRYPTION_KEYS")
        if not os.getenv("CREDENTIAL_ACTIVE_KEY_ID"):
            missing.append("CREDENTIAL_ACTIVE_KEY_ID")
        if os.getenv("LEGAL_DISPATCHER", "redis") != "redis":
            missing.append("LEGAL_DISPATCHER=redis")
        if not os.getenv("REDIS_URL"):
            missing.append("REDIS_URL")
        if missing:
            raise RuntimeError(f"Missing production configuration: {', '.join(missing)}")


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = True
    RATELIMIT_ENABLED = False
    LEGAL_DISPATCHER = "inline"
    LEGAL_SSE_WAIT_SECONDS = 0
    MAIL_SUPPRESS_SEND = True
    MAIL_DEFAULT_SENDER = "tests@giana-lex.invalid"
    CREDENTIAL_ENCRYPTION_KEYS = "test-key:" + "a" * 64
    CREDENTIAL_ACTIVE_KEY_ID = "test-key"
    OPENAI_CLIENT_ID = "test-client-id"
    OPENAI_REDIRECT_URI = "http://localhost:1455/auth/callback"
    PROVIDER_ALLOWED_PRIVATE_HOSTS = ["localhost", "127.0.0.1"]
    # Tests of the agent flow assume the legacy (no-harness) runtime, so the
    # harness must be off regardless of any .env value.
    HARNESS_ENABLED = False


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
