from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from typing import Any, Protocol

from .constants import qdrant_api_key, qdrant_url


class VectorStore(Protocol):
    def ensure_collection(self, collection: str, vector_size: int, rebuild: bool = False) -> None: ...

    def upsert(self, collection: str, points: Sequence[dict[str, Any]]) -> int: ...

    def delete_source(self, collection: str, source_file: str) -> None: ...

    def list_sources(self, collection: str, corpus: str | None = None) -> set[str]: ...

    def set_payload(self, collection: str, *, filter_key: str, filter_value: Any, payload: dict[str, Any]) -> int: ...

    def search(
        self,
        collection: str,
        vector: Sequence[float],
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def retrieve_candidates(
        self,
        collection: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


def stable_point_id(source_hash: str, chunk_index: int) -> str:
    digest = hashlib.sha256(f"{source_hash}:{chunk_index}".encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))


class QdrantStore:
    """Qdrant adapter with all optional imports isolated from testable core code."""

    def __init__(self, client=None, url: str | None = None, api_key: str | None = None):
        if client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise RuntimeError(
                    "Qdrant support requires the 'qdrant-client' package."
                ) from exc
            client = QdrantClient(url=url or qdrant_url(), api_key=api_key or qdrant_api_key())
        self.client = client

    @staticmethod
    def _models():
        try:
            from qdrant_client import models
        except ImportError as exc:
            raise RuntimeError("Qdrant support requires the 'qdrant-client' package.") from exc
        return models

    def ensure_collection(self, collection: str, vector_size: int, rebuild: bool = False) -> None:
        exists = self.client.collection_exists(collection)
        if rebuild and exists:
            self.client.delete_collection(collection_name=collection)
            exists = False
        if not exists:
            models = self._models()
            self.client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )

    def upsert(self, collection: str, points: Sequence[dict[str, Any]]) -> int:
        if not points:
            return 0
        models = self._models()
        qdrant_points = [
            models.PointStruct(id=point["id"], vector=point["vector"], payload=point["payload"])
            for point in points
        ]
        self.client.upsert(collection_name=collection, points=qdrant_points, wait=True)
        return len(qdrant_points)

    def _filter(self, values: dict[str, Any] | None):
        if not values:
            return None
        models = self._models()
        return models.Filter(
            must=[
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
                for key, value in sorted(values.items())
                if value is not None
            ]
        )

    def delete_source(self, collection: str, source_file: str) -> None:
        models = self._models()
        self.client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(filter=self._filter({"source_file": source_file})),
            wait=True,
        )

    def set_payload(self, collection: str, *, filter_key: str, filter_value: Any, payload: dict[str, Any]) -> int:
        if not self.client.collection_exists(collection):
            return 0
        models = self._models()
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key=filter_key, match=models.MatchValue(value=filter_value))]
            )
        )
        self.client.set_payload(
            collection_name=collection,
            payload=payload,
            points=selector,
            wait=True,
        )
        return 1

    def list_sources(self, collection: str, corpus: str | None = None) -> set[str]:
        if not self.client.collection_exists(collection):
            return set()
        sources: set[str] = set()
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=collection,
                scroll_filter=self._filter({"corpus": corpus}) if corpus else None,
                limit=1024,
                offset=offset,
                with_payload=["source_file"],
                with_vectors=False,
            )
            sources.update(
                point.payload["source_file"]
                for point in points
                if point.payload and point.payload.get("source_file")
            )
            if offset is None:
                break
        return sources

    def search(
        self,
        collection: str,
        vector: Sequence[float],
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.client.collection_exists(collection):
            return []
        response = self.client.query_points(
            collection_name=collection,
            query=list(vector),
            query_filter=self._filter(filters),
            limit=limit,
            with_payload=True,
        )
        return [
            {"id": str(hit.id), "score": float(hit.score), "payload": dict(hit.payload or {})}
            for hit in response.points
        ]

    def retrieve_candidates(
        self,
        collection: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return a filtered pool for local sparse scoring.

        Qdrant scroll order is not a sparse relevance index, so BM25 recall is
        limited to this pool. This avoids incompatible collection migrations or
        pretending that the existing collections have global sparse indexes.
        """
        if limit <= 0 or not self.client.collection_exists(collection):
            return []
        points, _offset = self.client.scroll(
            collection_name=collection,
            scroll_filter=self._filter(filters),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [
            {"id": str(point.id), "score": 0.0, "payload": dict(point.payload or {})}
            for point in points
        ]
