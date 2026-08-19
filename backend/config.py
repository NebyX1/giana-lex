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
    llm_max_output_tokens: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4000"))
    llm_temperature: float | None = _optional_float("LLM_TEMPERATURE")
    examples_top_k: int = int(os.getenv("EXAMPLES_TOP_K", "3"))

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


settings = Settings()
