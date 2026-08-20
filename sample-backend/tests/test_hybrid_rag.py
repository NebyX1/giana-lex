import pytest

from rag.hybrid import bm25_rank, reciprocal_rank_fusion
from rag.retriever import LegalRetriever


class FakeEmbedder:
    vector_size = 3

    def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _text in texts]


class CandidateStore:
    def __init__(self, dense, candidates=None):
        self.dense = dense
        self.candidates = dense if candidates is None else candidates
        self.filters = []

    def search(self, collection, vector, limit, filters=None):
        self.filters.append(dict(filters or {}))
        return self.dense[:limit]

    def retrieve_candidates(self, collection, limit, filters=None):
        self.filters.append(dict(filters or {}))
        return self.candidates[:limit]


def hit(identifier, text, *, corpus="nacional", active=True, **payload):
    return {
        "id": identifier,
        "score": 0.8,
        "payload": {
            "text": text,
            "title": payload.pop("title", text),
            "source_file": f"{identifier}.txt",
            "corpus": corpus,
            "active": active,
            **payload,
        },
    }


def test_rrf_combines_rankings_deterministically():
    dense = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    sparse = [{"id": "c"}, {"id": "b"}]

    fused = reciprocal_rank_fusion([dense, sparse], rank_constant=60)

    assert [item["id"] for item in fused] == ["c", "b", "a"]
    assert fused[0]["rrf_score"] == pytest.approx(1 / 63 + 1 / 61)


def test_bm25_prefers_rare_exact_terms_and_ignores_non_matches():
    candidates = [
        hit("generic", "contrato contrato administrativo comun"),
        hit("rare", "fideicomiso financiero departamental"),
        hit("none", "procedimiento tributario"),
    ]

    ranked = bm25_rank("fideicomiso financiero", candidates)

    assert [item["id"] for item in ranked] == ["rare"]
    assert ranked[0]["bm25_score"] > 0


@pytest.mark.parametrize("corpus", ["nacional", "departamental"])
def test_hybrid_retrieval_excludes_inactive_and_applies_structured_filters(corpus):
    candidates = [
        hit("inactive", "contrato objetivo", corpus=corpus, active=False, case_id="case-1", source_class="official_primary"),
        hit("wrong-case", "contrato objetivo", corpus=corpus, case_id="case-2", source_class="official_primary"),
        hit("wrong-class", "contrato objetivo", corpus=corpus, case_id="case-1", source_class="institutional"),
        hit("good", "contrato objetivo", corpus=corpus, case_id="case-1", source_class="official_primary"),
    ]
    store = CandidateStore(candidates)
    retriever = LegalRetriever(FakeEmbedder(), store)

    results = retriever.search(
        "contrato", corpus, case_id="case-1", source_class="official_primary", active=False
    )

    assert [result["identifier"] for result in results] == ["good"]
    assert all(call["active"] is True for call in store.filters)
    assert all(call["case_id"] == "case-1" for call in store.filters)
    assert all(call["source_class"] == "official_primary" for call in store.filters)


def test_reranker_failure_falls_back_to_rrf_and_records_latency():
    recorded = []

    def failing_reranker(query, hits):
        raise RuntimeError("offline model unavailable")

    store = CandidateStore([hit("dense", "texto general")], [hit("sparse", "fideicomiso exacto")])
    retriever = LegalRetriever(
        FakeEmbedder(),
        store,
        reranker=failing_reranker,
        reranker_enabled=True,
        metrics_recorder=recorded.append,
    )

    results = retriever.search("fideicomiso", "nacional")

    assert results
    assert recorded[0]["reranker_enabled"] is True
    assert recorded[0]["reranker_fallback"] is True
    assert recorded[0]["reranker_ms"] >= 0
    assert recorded[0]["total_ms"] >= recorded[0]["sparse_ms"]
