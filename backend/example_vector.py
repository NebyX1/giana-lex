"""Optional Qdrant ranking over the editorial catalog; SQLite remains authoritative."""
from __future__ import annotations

import time
import socket
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from legal_knowledge.indexing import EmbeddingService


class ExampleVector:
    collection = "giana_editorial_examples_v1"

    def __init__(self, settings):
        self.url = settings.qdrant_url
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None,
                                   timeout=0.5, check_compatibility=False)
        self.embedding = EmbeddingService(settings.legal_embedding_model, settings.legal_embedding_dimension,
                                          settings.legal_embedding_cache_dir)
        self.dimension = settings.legal_embedding_dimension
        self.last_failure = 0.0

    def search(self, query: str, limit: int = 40) -> list[dict]:
        if time.monotonic() - self.last_failure < 30:
            raise ConnectionError("Índice vectorial temporalmente no disponible")
        try:
            parsed = urlparse(self.url)
            with socket.create_connection((parsed.hostname or "localhost", parsed.port or 6333), timeout=0.2):
                pass
            if not self.client.collection_exists(self.collection):
                raise ConnectionError("La colección editorial aún no fue indexada")
            vector = self.embedding.embed([query])[0]
            response = self.client.query_points(self.collection, query=vector, limit=limit, with_payload=True)
            return [{"id": p.payload.get("id"), "revision_id": p.payload.get("revision_id"),
                     "score": float(p.score)} for p in response.points if p.payload]
        except Exception:
            self.last_failure = time.monotonic()
            raise

    def rebuild(self, rows: list[tuple[dict, str, str]]) -> int:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(self.collection,
                                      vectors_config=models.VectorParams(size=self.dimension, distance=models.Distance.COSINE))
        count = 0
        for start in range(0, len(rows), 32):
            batch = rows[start:start + 32]
            vectors = self.embedding.embed([weighted[:2500] for _, weighted, _ in batch])
            points = [models.PointStruct(id=str(uuid5(NAMESPACE_URL, "giana-example:" + info["id"])), vector=vector,
                                         payload={"id": info["id"], "revision_id": info["revision_id"], "scope": info["scope"]})
                      for (info, _, _), vector in zip(batch, vectors, strict=True)]
            self.client.upsert(self.collection, points=points, wait=True)
            count += len(points)
        self.last_failure = 0
        return count
