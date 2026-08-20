from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Any


def tokenize(value: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", plain)


def bm25_rank(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict[str, Any]]:
    """Rank an already-retrievable candidate pool with local BM25.

    This is deliberately not presented as a global sparse index. Its recall is
    bounded by the filtered candidate pool supplied by the vector store.
    """
    query_terms = tokenize(query)
    if not query_terms or not candidates:
        return []

    documents = [tokenize(_searchable_text(candidate)) for candidate in candidates]
    average_length = sum(map(len, documents)) / len(documents) or 1.0
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    query_frequency = Counter(query_terms)
    total = len(documents)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, (candidate, document) in enumerate(zip(candidates, documents)):
        frequencies = Counter(document)
        score = 0.0
        for term, query_count in query_frequency.items():
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_document_frequency = math.log(
                1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * len(document) / average_length)
            score += query_count * inverse_document_frequency * frequency * (k1 + 1) / denominator
        if score > 0:
            ranked = dict(candidate)
            ranked["bm25_score"] = score
            scored.append((score, index, ranked))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _score, _index, candidate in scored]


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[dict[str, Any]]],
    *,
    rank_constant: int = 60,
) -> list[dict[str, Any]]:
    if rank_constant < 1:
        raise ValueError("rank_constant must be positive")
    scores: dict[str, float] = {}
    values: dict[str, dict[str, Any]] = {}
    first_seen: dict[str, int] = {}
    order = 0
    for ranking in rankings:
        seen_in_ranking: set[str] = set()
        for rank, item in enumerate(ranking, start=1):
            identifier = str(item.get("id", ""))
            if not identifier or identifier in seen_in_ranking:
                continue
            seen_in_ranking.add(identifier)
            if identifier not in first_seen:
                first_seen[identifier] = order
                order += 1
            values.setdefault(identifier, dict(item))
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (rank_constant + rank)
    identifiers = sorted(scores, key=lambda identifier: (-scores[identifier], first_seen[identifier]))
    fused = []
    for identifier in identifiers:
        item = dict(values[identifier])
        item["rrf_score"] = scores[identifier]
        fused.append(item)
    return fused


def _searchable_text(candidate: dict[str, Any]) -> str:
    payload = candidate.get("payload") or {}
    metadata = payload.get("metadata") or {}
    return " ".join(
        str(value or "")
        for value in (
            payload.get("title"),
            payload.get("text"),
            payload.get("number"),
            payload.get("article"),
            metadata.get("title"),
            metadata.get("search_terms"),
        )
    )
