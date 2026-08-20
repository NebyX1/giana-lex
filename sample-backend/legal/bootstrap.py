from flask import current_app

from legal.infrastructure.inline_dispatcher import InlineWorkflowDispatcher
from legal.infrastructure.outbox import OutboxPublisher
from legal.infrastructure.redis_dispatcher import RedisStreamWorkflowDispatcher
from legal.workflows.engine import DurableWorkflowEngine


def initialize_authority_provider(app) -> None:
    """Use local Qdrant when reachable; startup remains usable without external services."""
    if app.config.get("TESTING") or not app.config.get("QDRANT_URL"):
        return
    try:
        from rag.embeddings import FastEmbedder
        from rag.store import QdrantStore
        from rag.retriever import LegalRetriever
        from legal.research.service import RetrieverAuthorityProvider

        store = QdrantStore(url=app.config["QDRANT_URL"], api_key=app.config.get("QDRANT_API_KEY"))
        store.client.get_collections()
        app.extensions["legal_authority_provider"] = RetrieverAuthorityProvider(
            LegalRetriever(FastEmbedder(), store)
        )
    except Exception as exc:
        app.logger.warning("Qdrant legal authority provider unavailable: %s", exc)


def build_outbox_publisher() -> OutboxPublisher:
    backend = current_app.config["LEGAL_DISPATCHER"]
    if backend == "inline":
        provider = current_app.extensions.get("legal_authority_provider")
        dispatcher = InlineWorkflowDispatcher(
            DurableWorkflowEngine(authority_provider=provider).process_command
        )
    elif backend == "redis":
        dispatcher = RedisStreamWorkflowDispatcher(
            current_app.config["REDIS_URL"], current_app.config["LEGAL_REDIS_STREAM"]
        )
    else:
        raise RuntimeError(f"Unknown LEGAL_DISPATCHER: {backend}")
    return OutboxPublisher(dispatcher, current_app.config["LEGAL_OUTBOX_MAX_ATTEMPTS"])
