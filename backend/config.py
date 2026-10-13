import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _optional_float(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def _llm_base_url() -> str:
    configured = os.getenv("LLM_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    return f"{ollama_url}/v1" if ollama_url else ""


def _llm_api_key() -> str:
    configured = os.getenv("LLM_API_KEY", "").strip()
    if configured:
        return configured
    return "ollama-local" if os.getenv("OLLAMA_BASE_URL", "").strip() else ""


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    database_path: Path = BASE_DIR / "data" / "giana_test.sqlite3"
    examples_dir: Path = BASE_DIR / "examples"
    molds_dir: Path = BASE_DIR / "molds"
    llm_base_url: str = _llm_base_url()
    llm_api_key: str = _llm_api_key()
    llm_model: str = (os.getenv("LLM_MODEL", "").strip() or os.getenv("OLLAMA_MODEL", "").strip())
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    intake_timeout_seconds: float = float(os.getenv("INTAKE_TIMEOUT_SECONDS", "8"))
    llm_max_output_tokens: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4000"))
    llm_temperature: float | None = _optional_float("LLM_TEMPERATURE")
    examples_top_k: int = int(os.getenv("EXAMPLES_TOP_K", "3"))
    legal_database_url: str = (
        os.getenv("DATABASE_URL", "").strip()
        or f"sqlite:///{(BASE_DIR / 'data' / 'giana_test.sqlite3').as_posix()}"
    )
    legal_storage_dir: Path = Path(
        os.getenv("LEGAL_STORAGE_DIR", str(BASE_DIR / "data" / "legal" / "idl" / "resolutions"))
    )
    legal_seed_path: Path = Path(
        os.getenv("LEGAL_SEED_PATH", str(BASE_DIR / "data" / "seeds" / "idl_resolution_taxonomy_v1.json"))
    )
    legal_report_dir: Path = Path(os.getenv("LEGAL_REPORT_DIR", str(BASE_DIR / "data" / "legal" / "reports")))
    legal_admin_key: str = os.getenv("LEGAL_ADMIN_KEY", "").strip()
    legal_allow_local_admin: bool = _bool_env("LEGAL_ALLOW_LOCAL_ADMIN", True)
    qdrant_url: str = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip().rstrip("/")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "").strip()
    qdrant_taxonomy_collection: str = os.getenv(
        "QDRANT_RESOLUTION_TAXONOMY_COLLECTION", "giana_resolution_taxonomy_v2"
    ).strip()
    qdrant_resolutions_collection: str = os.getenv(
        "QDRANT_RESOLUTION_EXAMPLES_COLLECTION", "giana_resolution_examples_v2"
    ).strip()
    legal_embedding_model: str = os.getenv(
        "LEGAL_EMBEDDING_MODEL", "jinaai/jina-embeddings-v2-base-es"
    ).strip()
    legal_embedding_dimension: int = int(os.getenv("LEGAL_EMBEDDING_DIMENSION", "768"))
    legal_embedding_cache_dir: Path = Path(
        os.getenv("LEGAL_EMBEDDING_CACHE_DIR", str(BASE_DIR / "data" / "models"))
    )
    legal_import_timeout_seconds: float = float(os.getenv("LEGAL_IMPORT_TIMEOUT_SECONDS", "20"))
    legal_import_rate_limit_seconds: float = float(os.getenv("LEGAL_IMPORT_RATE_LIMIT_SECONDS", "0.45"))
    legal_import_retries: int = int(os.getenv("LEGAL_IMPORT_RETRIES", "2"))
    secret_key: str = os.getenv("SECRET_KEY", "development-only-change-me")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    ratelimit_storage_uri: str = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    mail_server: str | None = os.getenv("MAIL_SERVER")
    mail_port: int = int(os.getenv("MAIL_PORT", "587"))
    mail_use_tls: bool = _bool_env("MAIL_USE_TLS", True)
    mail_use_ssl: bool = _bool_env("MAIL_USE_SSL", False)
    mail_username: str | None = os.getenv("MAIL_USERNAME")
    mail_password: str | None = os.getenv("MAIL_PASSWORD")
    mail_default_sender: str | None = os.getenv("MAIL_DEFAULT_SENDER")
    mail_suppress_send: bool = _bool_env("MAIL_SUPPRESS_SEND", False)
    otp_ttl_minutes: int = int(os.getenv("OTP_TTL_MINUTES", "10"))
    otp_max_attempts: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    session_cookie_secure: bool = _bool_env("SESSION_COOKIE_SECURE", False)
    force_https: bool = _bool_env("FORCE_HTTPS", False)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


settings = Settings()
