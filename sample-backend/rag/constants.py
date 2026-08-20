import os


DEPARTMENTAL_COLLECTION = "giana_lex_departamental"
NATIONAL_COLLECTION = "giana_lex_nacional"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_VECTOR_SIZE = 384


def qdrant_url() -> str:
    return os.getenv("QDRANT_URL", "http://localhost:6333")


def qdrant_api_key() -> str | None:
    return os.getenv("QDRANT_API_KEY") or None


def embedding_model() -> str:
    return os.getenv("FASTEMBED_MODEL", DEFAULT_EMBEDDING_MODEL)
