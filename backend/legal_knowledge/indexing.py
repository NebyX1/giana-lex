from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models


LOGGER = logging.getLogger(__name__)


def deterministic_point_id(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "giana-lex:" + ":".join(parts)))


def semantic_chunks(resolution: dict, revision: dict) -> list[tuple[str, int, str]]:
    header = "\n".join(filter(None, [
        f"Resolución {resolution['resolution_number']}",
        resolution.get("title", ""),
        resolution.get("official_summary", ""),
    ]))
    chunks: list[tuple[str, int, str]] = [("METADATA", 0, header)]
    sections = [
        ("VISTO", [revision.get("visto", "")]),
        ("RESULTANDO", revision.get("resultandos", [])),
        ("CONSIDERANDO", revision.get("considerandos", [])),
        ("ATENTO", [revision.get("atento", "")]),
        ("RESUELVE", revision.get("resuelve", [])),
    ]
    for section, values in sections:
        index = 0
        for value in values:
            value = (value or "").strip()
            if not value:
                continue
            paragraphs = [value[pos:pos + 1400] for pos in range(0, len(value), 1400)]
            for paragraph in paragraphs:
                context = f"{header}\nSección: {section}\n{paragraph}"
                chunks.append((section, index, context))
                index += 1
    return chunks


class EmbeddingService:
    def __init__(self, model_name: str, dimension: int, cache_dir: Path):
        self.model_name = model_name
        self.dimension = dimension
        self.cache_dir = Path(cache_dir)
        self._model = None
        self._lock = Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    self._model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.cache_dir))
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [vector.tolist() for vector in self._load().embed(texts)]
        if any(len(vector) != self.dimension for vector in vectors):
            raise ValueError(f"El modelo {self.model_name} no produce vectores de dimensión {self.dimension}")
        return vectors


class LegalQdrantIndex:
    def __init__(self, settings, embedding_service: EmbeddingService | None = None, client=None):
        self.settings = settings
        self.embedding = embedding_service or EmbeddingService(
            settings.legal_embedding_model,
            settings.legal_embedding_dimension,
            settings.legal_embedding_cache_dir,
        )
        self.client = client or QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=15,
            check_compatibility=False,
        )
        self._collections_ensured = False
        self._ensure_lock = Lock()

    def health(self) -> dict:
        try:
            collections = {item.name for item in self.client.get_collections().collections}
            result = {
                "connected": True,
                "taxonomy_collection": self.settings.qdrant_taxonomy_collection,
                "resolutions_collection": self.settings.qdrant_resolutions_collection,
                "taxonomy_exists": self.settings.qdrant_taxonomy_collection in collections,
                "resolutions_exists": self.settings.qdrant_resolutions_collection in collections,
                "embedding_model": self.settings.legal_embedding_model,
                "dimension": self.settings.legal_embedding_dimension,
            }
            if result["taxonomy_exists"]:
                result["taxonomy_points"] = self.client.get_collection(self.settings.qdrant_taxonomy_collection).points_count
            if result["resolutions_exists"]:
                result["resolution_points"] = self.client.get_collection(self.settings.qdrant_resolutions_collection).points_count
            return result
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def ensure_collections(self) -> None:
        if self._collections_ensured:
            return
        with self._ensure_lock:
            if self._collections_ensured:
                return
            for collection in (self.settings.qdrant_taxonomy_collection, self.settings.qdrant_resolutions_collection):
                if not self.client.collection_exists(collection):
                    self.client.create_collection(
                        collection_name=collection,
                        vectors_config=models.VectorParams(
                            size=self.settings.legal_embedding_dimension,
                            distance=models.Distance.COSINE,
                        ),
                    )
            taxonomy_indexes = {
                "document_kind": models.PayloadSchemaType.KEYWORD,
                "taxonomy_node_id": models.PayloadSchemaType.KEYWORD,
                "family_code": models.PayloadSchemaType.KEYWORD,
                "type_code": models.PayloadSchemaType.KEYWORD,
                "subtype_code": models.PayloadSchemaType.KEYWORD,
                "status": models.PayloadSchemaType.KEYWORD,
                "entity_version": models.PayloadSchemaType.INTEGER,
            }
            resolution_indexes = {
                "document_kind": models.PayloadSchemaType.KEYWORD,
                "resolution_id": models.PayloadSchemaType.KEYWORD,
                "revision_id": models.PayloadSchemaType.KEYWORD,
                "resolution_number": models.PayloadSchemaType.KEYWORD,
                "year": models.PayloadSchemaType.INTEGER,
                "taxonomy_node_ids": models.PayloadSchemaType.KEYWORD,
                "canonical_for": models.PayloadSchemaType.KEYWORD,
                "secondary_for": models.PayloadSchemaType.KEYWORD,
                "related_to": models.PayloadSchemaType.KEYWORD,
                "section": models.PayloadSchemaType.KEYWORD,
                "active": models.PayloadSchemaType.BOOL,
                "entity_version": models.PayloadSchemaType.INTEGER,
            }
            for name, schema in taxonomy_indexes.items():
                self._ensure_payload_index(self.settings.qdrant_taxonomy_collection, name, schema)
            for name, schema in resolution_indexes.items():
                self._ensure_payload_index(self.settings.qdrant_resolutions_collection, name, schema)
            self._collections_ensured = True

    def _ensure_payload_index(self, collection: str, field: str, schema) -> None:
        info = self.client.get_collection(collection)
        if field not in (info.payload_schema or {}):
            self.client.create_payload_index(collection, field_name=field, field_schema=schema, wait=True)

    def upsert_taxonomy(self, document: str, payload: dict) -> None:
        self.ensure_collections()
        vector = self.embedding.embed([document])[0]
        point = models.PointStruct(
            id=deterministic_point_id("taxonomy", payload["taxonomy_node_id"]),
            vector=vector,
            payload=payload,
        )
        self.client.upsert(self.settings.qdrant_taxonomy_collection, [point], wait=True)

    def delete_taxonomy(self, taxonomy_node_id: str) -> None:
        if not self.client.collection_exists(self.settings.qdrant_taxonomy_collection):
            return
        self.client.delete(
            self.settings.qdrant_taxonomy_collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=[
                models.FieldCondition(key="taxonomy_node_id", match=models.MatchValue(value=taxonomy_node_id))
            ])),
            wait=True,
        )

    def upsert_resolution(self, resolution: dict, revision: dict, assignments: list[dict]) -> int:
        self.ensure_collections()
        self.delete_resolution(resolution["id"])
        chunks = semantic_chunks(resolution, revision)
        vectors = self.embedding.embed([chunk[2] for chunk in chunks])
        by_role = {"canonical": [], "secondary": [], "related": [], "negative_example": []}
        for assignment in assignments:
            by_role[assignment["role"]].append(assignment["taxonomy_node_id"])
        taxonomy_ids = [assignment["taxonomy_node_id"] for assignment in assignments]
        points = []
        for (section, chunk_index, text), vector in zip(chunks, vectors, strict=True):
            payload = {
                "document_kind": "resolution_example",
                "resolution_id": resolution["id"],
                "revision_id": revision["id"],
                "resolution_number": resolution["resolution_number"],
                "year": resolution.get("year"),
                "title": resolution["title"],
                "taxonomy_node_ids": taxonomy_ids,
                "canonical_for": by_role["canonical"],
                "secondary_for": by_role["secondary"],
                "related_to": by_role["related"],
                "negative_for": by_role["negative_example"],
                "section": section,
                "chunk_index": chunk_index,
                "active": resolution["status"] == "active",
                "entity_version": resolution["version"],
                "source_url": resolution["source_url"],
                "text": text,
            }
            points.append(models.PointStruct(
                id=deterministic_point_id("resolution", resolution["id"], revision["id"], section, str(chunk_index)),
                vector=vector,
                payload=payload,
            ))
        if points:
            self.client.upsert(self.settings.qdrant_resolutions_collection, points, wait=True)
        return len(points)

    def update_resolution_payload(self, resolution_id: str, payload: dict) -> None:
        if not self.client.collection_exists(self.settings.qdrant_resolutions_collection):
            return
        self.client.set_payload(
            self.settings.qdrant_resolutions_collection,
            payload=payload,
            points=models.Filter(must=[
                models.FieldCondition(key="resolution_id", match=models.MatchValue(value=resolution_id))
            ]),
            wait=True,
        )

    def delete_resolution(self, resolution_id: str) -> None:
        if not self.client.collection_exists(self.settings.qdrant_resolutions_collection):
            return
        self.client.delete(
            self.settings.qdrant_resolutions_collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=[
                models.FieldCondition(key="resolution_id", match=models.MatchValue(value=resolution_id))
            ])),
            wait=True,
        )

    def search_taxonomy(self, query: str, limit: int = 5) -> list[dict]:
        if not self.client.collection_exists(self.settings.qdrant_taxonomy_collection):
            return []
        vector = self.embedding.embed([query])[0]
        response = self.client.query_points(
            self.settings.qdrant_taxonomy_collection,
            query=vector,
            query_filter=models.Filter(must=[
                models.FieldCondition(key="status", match=models.MatchValue(value="active"))
            ]),
            limit=limit,
            with_payload=True,
        )
        return [{**(point.payload or {}), "score": float(point.score)} for point in response.points]

    def search_resolutions(self, taxonomy_node_id: str, query: str, limit: int = 8) -> list[dict]:
        if not self.client.collection_exists(self.settings.qdrant_resolutions_collection):
            return []
        vector = self.embedding.embed([query])[0]
        response = self.client.query_points(
            self.settings.qdrant_resolutions_collection,
            query=vector,
            query_filter=models.Filter(must=[
                models.FieldCondition(key="active", match=models.MatchValue(value=True)),
                models.FieldCondition(key="taxonomy_node_ids", match=models.MatchValue(value=taxonomy_node_id)),
            ]),
            limit=limit,
            with_payload=True,
        )
        return [{**(point.payload or {}), "score": float(point.score)} for point in response.points]

    def resolution_point_count(self, resolution_id: str) -> int:
        if not self.client.collection_exists(self.settings.qdrant_resolutions_collection):
            return 0
        result = self.client.count(
            self.settings.qdrant_resolutions_collection,
            count_filter=models.Filter(must=[
                models.FieldCondition(key="resolution_id", match=models.MatchValue(value=resolution_id))
            ]),
            exact=True,
        )
        return result.count

    def inventory(self, collection: str) -> list[dict]:
        if not self.client.collection_exists(collection):
            return []
        items = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection, limit=256, offset=offset, with_payload=True, with_vectors=False
            )
            items.extend([{"point_id": str(point.id), **(point.payload or {})} for point in points])
            if offset is None:
                break
        return items
