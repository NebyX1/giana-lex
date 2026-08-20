from __future__ import annotations

from functools import lru_cache
import logging
import os
import re
from time import perf_counter
import unicodedata
from collections.abc import Callable
from typing import Any

from .constants import DEPARTMENTAL_COLLECTION, NATIONAL_COLLECTION
from .embeddings import Embedder, FastEmbedder
from .hybrid import bm25_rank, reciprocal_rank_fusion
from .store import QdrantStore, VectorStore


logger = logging.getLogger(__name__)


class LegalRetriever:
    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        *,
        reranker: Any | None = None,
        reranker_enabled: bool | None = None,
        metrics_recorder: Callable[[dict[str, Any]], None] | None = None,
        candidate_pool_size: int = 200,
    ):
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        self.reranker_enabled = (
            _env_flag("RAG_RERANK_ENABLED") if reranker_enabled is None else reranker_enabled
        )
        self.metrics_recorder = metrics_recorder
        self.candidate_pool_size = max(20, candidate_pool_size)
        self.last_search_metrics: dict[str, Any] = {}

    def search(
        self,
        query: str,
        corpus: str,
        top_k: int = 5,
        category: str | None = None,
        document_type: str | None = None,
        year: int | None = None,
        active: bool | None = True,
        case_id: str | None = None,
        source_class: str | None = None,
    ) -> list[dict[str, Any]]:
        started = perf_counter()
        clean_query = query.strip()
        if not clean_query:
            return []
        if corpus not in {"departamental", "nacional"}:
            raise ValueError(f"Unsupported corpus: {corpus}")
        collection = DEPARTMENTAL_COLLECTION if corpus == "departamental" else NATIONAL_COLLECTION
        filters = {
            "corpus": corpus,
            "category": category,
            "document_type": document_type,
            "year": year,
            "case_id": case_id,
            "source_class": source_class,
            "active": True,
        }
        # Keep the existing argument in the public interface, but inactive legal
        # material is never a retrievable authority in either corpus.
        _ = active
        vector = self.embedder.embed([clean_query])[0]
        limit = max(1, min(top_k, 20))
        dense_started = perf_counter()
        dense_hits: list[dict[str, Any]] = []
        direct_norm_ids = self._direct_norm_ids(clean_query) if corpus == "nacional" else []
        if corpus == "nacional" and isinstance(self.store, QdrantStore):
            for norm_id in direct_norm_ids[:2]:
                dense_hits.extend(self.store.search(collection, vector, limit, {**filters, "norma_id": norm_id}))
        dense_hits.extend(
            self.store.search(collection, vector, min(self.candidate_pool_size, max(limit * 4, 40)), filters)
        )
        dense_hits = self._filtered_unique(dense_hits, filters)
        dense_ms = (perf_counter() - dense_started) * 1000

        retrieve_candidates = getattr(self.store, "retrieve_candidates", None)
        candidates = retrieve_candidates(collection, self.candidate_pool_size, filters) if callable(retrieve_candidates) else []
        candidate_pool = self._filtered_unique([*dense_hits, *candidates], filters)
        sparse_started = perf_counter()
        sparse_hits = bm25_rank(clean_query, candidate_pool)
        sparse_ms = (perf_counter() - sparse_started) * 1000
        hits = reciprocal_rank_fusion([dense_hits, sparse_hits])

        reranker_ms = 0.0
        reranker_fallback = False
        if self.reranker_enabled:
            reranker_started = perf_counter()
            try:
                if self.reranker is None:
                    raise RuntimeError("reranker is enabled but unavailable")
                reranked = (
                    self.reranker.rerank(clean_query, hits)
                    if hasattr(self.reranker, "rerank")
                    else self.reranker(clean_query, hits)
                )
                if not isinstance(reranked, list):
                    raise TypeError("reranker must return a list")
                hits = self._filtered_unique(reranked, filters)
            except Exception as exc:
                reranker_fallback = True
                logger.warning("RAG reranker failed; using RRF results: %s", exc)
            reranker_ms = (perf_counter() - reranker_started) * 1000

        results = []
        per_source: dict[str, int] = {}
        seen_ids: set[str] = set()
        for hit in hits:
            hit_id = str(hit.get("id", ""))
            if hit_id in seen_ids:
                continue
            payload = dict(hit.get("payload") or {})
            score = float(hit.get("score") or hit.get("bm25_score") or 0.0)
            source = str(payload.get("source_file", payload.get("source", "")))
            if per_source.get(source, 0) >= 2:
                continue
            seen_ids.add(hit_id)
            per_source[source] = per_source.get(source, 0) + 1
            metadata = dict(payload.get("metadata") or {})
            for key in (
                "corpus", "category", "document_type", "title", "number", "year",
                "article", "source_file", "source_url", "source_hash", "indexed_at",
                "norm_id", "norma_id", "normative_family", "jurisdiction",
                "department", "scope", "case_id", "source_class",
                "active",
            ):
                if key in payload:
                    metadata.setdefault(key, payload[key])
            results.append({
                "identifier": str(hit.get("id", "")),
                "text": payload.get("text", ""),
                "source": payload.get("source_file", payload.get("source", "")),
                "category": payload.get("category", ""),
                "metadata": metadata,
                "score": score,
            })
            if len(results) >= limit:
                break
        metrics = {
            "corpus": corpus,
            "dense_ms": round(dense_ms, 3),
            "sparse_ms": round(sparse_ms, 3),
            "reranker_ms": round(reranker_ms, 3),
            "total_ms": round((perf_counter() - started) * 1000, 3),
            "dense_count": len(dense_hits),
            "candidate_count": len(candidate_pool),
            "sparse_count": len(sparse_hits),
            "result_count": len(results),
            "reranker_enabled": self.reranker_enabled,
            "reranker_fallback": reranker_fallback,
        }
        self.last_search_metrics = metrics
        logger.info("rag_retrieval=%s", metrics)
        if self.metrics_recorder is not None:
            try:
                self.metrics_recorder(dict(metrics))
            except Exception:
                logger.exception("RAG metrics recorder failed")
        return results

    @classmethod
    def _filtered_unique(
        cls,
        hits: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            identifier = str(hit.get("id", ""))
            if not identifier or identifier in seen:
                continue
            payload = hit.get("payload") or {}
            if not cls._matches_filters(payload, filters):
                continue
            seen.add(identifier)
            unique.append(hit)
        return unique

    @staticmethod
    def _matches_filters(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
        metadata = payload.get("metadata") or {}
        if payload.get("active", metadata.get("active")) is False:
            return False
        for key, expected in filters.items():
            if expected is None or key == "active":
                continue
            actual = payload.get(key, metadata.get(key))
            if actual != expected:
                return False
        return True

    @staticmethod
    def _normalized_tokens(value: str) -> set[str]:
        folded = unicodedata.normalize("NFKD", value.casefold())
        plain = "".join(char for char in folded if not unicodedata.combining(char))
        stop = {"para", "sobre", "entre", "desde", "como", "aplicacion", "gobiernos", "departamentales", "intendencia"}
        return {token for token in re.findall(r"[a-z0-9]+", plain) if len(token) > 2 and token not in stop}

    @classmethod
    def _lexical_overlap(cls, query: str, candidate: str) -> float:
        wanted = cls._normalized_tokens(query)
        return len(wanted & cls._normalized_tokens(candidate)) / max(len(wanted), 1)

    @classmethod
    def _direct_norm_ids(cls, query: str) -> list[str]:
        """Resolve explicit norm numbers and stable aliases before semantic search."""
        try:
            from impo.storage import load_registry
        except ImportError:
            return []
        normalized = " ".join(cls._normalized_tokens(query))
        compact_digits = re.sub(r"\D", "", query)
        tocaf = "tocaf" in normalized or "contabilidad administracion financiera" in normalized
        matches: list[tuple[int, str]] = []
        for norm_id, entry in load_registry().items():
            number = re.sub(r"\D", "", str(entry.get("numero") or ""))
            title = " ".join(cls._normalized_tokens(str(entry.get("title") or "")))
            haystack = " ".join(cls._normalized_tokens(
                f"{norm_id} {entry.get('title', '')} {entry.get('search_terms', '')}"
            ))
            score = 0
            if number and number in compact_digits:
                score += 10
            if tocaf and "tocaf" in haystack:
                score += 8
            if tocaf and "tocaf" in title:
                score += 4
            if score:
                matches.append((score, norm_id))
        return [norm_id for _score, norm_id in sorted(matches, reverse=True)]

    def expand_with_modifiers(
        self,
        results: list[dict[str, Any]],
        *,
        top_k: int = 5,
        max_extra: int = 4,
    ) -> list[dict[str, Any]]:
        """Expand retrieval results by fetching modifying norms for the same
        norm_id/article from the normative relationship graph.

        Keeps expansion bounded (max_extra extra hits) so we never retrieve
        dozens of norms indiscriminately.
        """
        from depto import storage as dstorage

        expanded = list(results)
        if max_extra <= 0:
            return expanded

        seen_ids = set()
        for r in results:
            meta = r.get("metadata") or {}
            nid = meta.get("norm_id")
            if not nid:
                continue
            seen_ids.add(nid)
            article = meta.get("article")

        extra_added = 0
        for r in results:
            if extra_added >= max_extra:
                break
            meta = r.get("metadata") or {}
            nid = meta.get("norm_id")
            if not nid:
                continue
            article = meta.get("article")
            relations = dstorage.relationships_for(nid, relation="MODIFIES") + dstorage.relationships_for(nid, relation="MODIFIED_BY")
            relations += dstorage.relationships_for(nid, relation="MODIFIES_ARTICLE")
            for rel in relations:
                if extra_added >= max_extra:
                    break
                if rel.get("relation") in ("MODIFIES", "MODIFIED_BY", "MODIFIES_ARTICLE"):
                    other = rel.get("from") if rel.get("to") == nid else rel.get("to")
                    if not other or other in seen_ids:
                        continue
                    # only expand when the modifier targets this article or is article-agnostic
                    target_art = rel.get("target_article")
                    if target_art is not None and article and str(target_art) != str(article):
                        continue
                    seen_ids.add(other)
                    modifier = self._fetch_modifier(other, top_k=top_k)
                    if modifier:
                        expanded.append(modifier)
                        extra_added += 1
        return expanded

    def _fetch_modifier(self, norm_id: str, *, top_k: int) -> dict[str, Any] | None:
        """Fetch a single representative chunk for a modifier norm."""
        from qdrant_client import models
        from .constants import DEPARTMENTAL_COLLECTION, NATIONAL_COLLECTION
        for collection in (DEPARTMENTAL_COLLECTION, NATIONAL_COLLECTION):
            if not self.store.client.collection_exists(collection):
                continue
            filter_ = models.Filter(must=[models.FieldCondition(key="norm_id", match=models.MatchValue(value=norm_id))])
            try:
                response = self.store.client.query_points(
                    collection_name=collection,
                    query=self.embedder.embed(["disposición normativa"])[0],
                    query_filter=filter_,
                    limit=1,
                    with_payload=True,
                )
                if response.points:
                    hit = response.points[0]
                    payload = dict(hit.payload or {})
                    metadata = dict(payload.get("metadata") or {})
                    for key in ("corpus", "title", "number", "year", "norm_id", "article", "source_file"):
                        if key in payload:
                            metadata.setdefault(key, payload[key])
                    return {
                        "identifier": str(hit.id),
                        "text": payload.get("text", ""),
                        "source": payload.get("source_file", ""),
                        "category": payload.get("category", ""),
                        "metadata": metadata,
                        "score": float(hit.score),
                        "expanded": True,
                    }
            except Exception:
                continue
        return None


@lru_cache(maxsize=1)
def get_default_retriever() -> LegalRetriever:
    return LegalRetriever(FastEmbedder(), QdrantStore())


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}
