from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ingestion.chunking import fixed_chunks
from rag.constants import NATIONAL_COLLECTION
from rag.embeddings import Embedder
from rag.store import VectorStore

from .normalize import NormalizedNorma


CHUNK_SIZE = 1200
OVERLAP = 150


def build_article_chunks(norma: NormalizedNorma) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for article in norma.articulos:
        base_text = article.text or article.title
        if not base_text:
            continue
        article_label = article.number or "S/N"
        header = f"Artículo {article_label}"
        if article.title:
            header = f"{header} - {article.title}"
        full_text = f"{header}\n{base_text}"
        parts = fixed_chunks(full_text, CHUNK_SIZE, OVERLAP)
        if not parts:
            parts = [full_text]
        for index, part in enumerate(parts):
            chunks.append(
                {
                    "text": part,
                    "article": article_label,
                    "chunk_index": index,
                    "source_url": article.url or norma.canonical_url,
                }
            )
    return chunks


def stable_point_id(source_hash: str, chunk_index: int) -> str:
    digest = hashlib.sha256(f"{source_hash}:{chunk_index}".encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))


def _norma_source_hash(norma_id: str, checksum: str) -> str:
    return hashlib.sha256(f"{norma_id}:{checksum}".encode("utf-8")).hexdigest()


def index_norma(
    norma: NormalizedNorma,
    *,
    embedder: Embedder,
    store: VectorStore,
    active: bool,
    checksum: str,
) -> int:
    chunks = build_article_chunks(norma)
    if not chunks:
        return 0
    source_file = f"nacional/{norma.directory}/{deterministic_filename(norma.tipo, norma.numero, norma.anio)}/normalized.txt"
    source_hash = _norma_source_hash(norma.norma_id, checksum)

    store.ensure_collection(NATIONAL_COLLECTION, embedder.vector_size)
    store.delete_source(NATIONAL_COLLECTION, source_file)

    vectors = embedder.embed([chunk["text"] for chunk in chunks])
    points = []
    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        metadata = {
            "corpus": "nacional",
            "scope": "nacional",
            "category": norma.category,
            "document_type": norma.tipo,
            "title": norma.title,
            "number": norma.numero,
            "year": int(norma.anio) if norma.anio.isdigit() else None,
            "norma_id": norma.norma_id,
            "source_file": source_file,
            "source_url": norma.canonical_url,
            "source_hash": source_hash,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "active": active,
            "jurisdiction": "UY",
            "article": chunk["article"],
            "chunk_index": chunk["chunk_index"],
            "article_url": chunk["source_url"],
        }
        payload = {"text": chunk["text"], **metadata, "metadata": metadata}
        points.append(
            {
                "id": stable_point_id(source_hash, index),
                "vector": vector,
                "payload": payload,
            }
        )
    store.upsert(NATIONAL_COLLECTION, points)
    return len(points)


def set_norma_active_payload(
    norma_id: str,
    *,
    active: bool,
    store: VectorStore,
) -> int:
    return store.set_payload(
        NATIONAL_COLLECTION,
        filter_key="norma_id",
        filter_value=norma_id,
        payload={"active": active},
    )


from .identity import deterministic_filename  # noqa: E402