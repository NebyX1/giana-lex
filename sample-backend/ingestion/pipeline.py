from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.constants import DEPARTMENTAL_COLLECTION, NATIONAL_COLLECTION
from rag.embeddings import Embedder, FastEmbedder
from rag.store import QdrantStore, VectorStore, stable_point_id

from .chunking import legal_chunk_text
from .loader import KNOWLEDGE_ROOT, load_documents


COLLECTIONS = {
    "departamental": DEPARTMENTAL_COLLECTION,
    "nacional": NATIONAL_COLLECTION,
}


def ingest_knowledge(
    knowledge_root: Path = KNOWLEDGE_ROOT,
    embedder: Embedder | None = None,
    store: VectorStore | None = None,
    rebuild: bool = False,
    indexed_at: str | None = None,
) -> dict[str, Any]:
    embedder = embedder or FastEmbedder()
    store = store or QdrantStore()
    timestamp = indexed_at or datetime.now(timezone.utc).isoformat()
    documents = load_documents(knowledge_root)
    by_corpus = {corpus: [] for corpus in COLLECTIONS}
    for document in documents:
        by_corpus[document["metadata"]["corpus"]].append(document)

    stats: dict[str, Any] = {"documents": len(documents), "chunks": 0, "points": 0, "collections": {}}
    for corpus, collection in COLLECTIONS.items():
        store.ensure_collection(collection, embedder.vector_size, rebuild=rebuild)
        current_sources = {document["source_file"] for document in by_corpus[corpus]}
        stale_sources = set() if rebuild else store.list_sources(collection, corpus) - current_sources
        for source_file in sorted(stale_sources):
            store.delete_source(collection, source_file)

        corpus_points = 0
        for document in by_corpus[corpus]:
            # Replacement before upsert removes obsolete chunks when a document shrinks or changes.
            store.delete_source(collection, document["source_file"])
            chunks = legal_chunk_text(document["text"])
            vectors = embedder.embed([chunk["text"] for chunk in chunks])
            points = []
            for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                metadata = {
                    **document["metadata"],
                    "active": document["metadata"].get("active", True),
                    "article": chunk["article"],
                    "source_file": document["source_file"],
                    "source_hash": document["source_hash"],
                    "indexed_at": timestamp,
                    "legal_path": chunk["legal_path"],
                }
                payload = {"text": chunk["text"], "chunk_index": index, **metadata, "metadata": metadata}
                points.append({
                    "id": stable_point_id(document["source_hash"], index),
                    "vector": vector,
                    "payload": payload,
                })
            corpus_points += store.upsert(collection, points)
            stats["chunks"] += len(points)
        stats["points"] += corpus_points
        stats["collections"][collection] = {
            "documents": len(by_corpus[corpus]),
            "points": corpus_points,
            "stale_removed": len(stale_sources),
        }
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Giana-Lex local legal knowledge in Qdrant.")
    parser.add_argument("--knowledge-root", type=Path, default=KNOWLEDGE_ROOT)
    parser.add_argument("--rebuild", action="store_true", help="Drop and recreate both collections.")
    arguments = parser.parse_args()
    print(ingest_knowledge(arguments.knowledge_root, rebuild=arguments.rebuild))


if __name__ == "__main__":
    main()
