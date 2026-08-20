from impo.normalize import normalized_from_dict
from rag.retriever import LegalRetriever


class FakeEmbedder:
    vector_size = 3

    def embed(self, texts):
        return [[float(len(text)), 1.0, 0.0] for text in texts]


class FakeStore:
    def __init__(self):
        self.search_calls = []
        self.search_hits = []

    def ensure_collection(self, collection, vector_size, rebuild=False):
        pass

    def upsert(self, collection, points):
        return len(points)

    def delete_source(self, collection, source_file):
        pass

    def list_sources(self, collection, corpus=None):
        return set()

    def set_payload(self, collection, *, filter_key, filter_value, payload):
        return 1

    def search(self, collection, vector, limit, filters=None):
        self.search_calls.append((collection, list(vector), limit, dict(filters or {})))
        return self.search_hits[:limit]


def test_retriever_filters_active_true_for_national():
    store = FakeStore()
    store.search_hits = [
        {"id": "p1", "score": 0.9, "payload": {"text": "norma activa", "metadata": {}}}
    ]
    retriever = LegalRetriever(FakeEmbedder(), store)
    retriever.search("competencia intendente", "nacional")
    assert store.search_calls[0][3].get("active") is True


def test_retriever_applies_active_filter_to_departamental():
    store = FakeStore()
    retriever = LegalRetriever(FakeEmbedder(), store)
    retriever.search("procedimiento", "departamental")
    assert store.search_calls[0][3]["active"] is True


def test_retriever_active_filter_cannot_be_disabled():
    store = FakeStore()
    retriever = LegalRetriever(FakeEmbedder(), store)
    retriever.search("procedimiento", "nacional", active=None)
    assert store.search_calls[0][3]["active"] is True


def test_inactive_norm_not_retrievable():
    store = FakeStore()
    store.search_hits = []
    retriever = LegalRetriever(FakeEmbedder(), store)
    results = retriever.search("consulta", "nacional")
    assert results == []
    # The filter must include active=True so inactive points are excluded
    assert store.search_calls[0][3]["active"] is True


def test_inactive_search_request_still_excludes_inactive_material():
    store = FakeStore()
    retriever = LegalRetriever(FakeEmbedder(), store)
    retriever.search("x", "nacional", active=False)
    assert store.search_calls[0][3]["active"] is True


def test_persisted_normalized_norm_can_be_restored_for_offline_reindex():
    restored = normalized_from_dict({
        "tipo": "Ley",
        "numero": "15903",
        "anio": "1987",
        "nombre": "Rendición de cuentas",
        "canonical_url": "https://www.impo.com.uy/bases/leyes/15903-1987",
        "json_url": "https://example.invalid/source.json",
        "norma_id": "ley:15903:1987",
        "articulos": [{"nroArticulo": "1", "textoArticulo": "Texto vigente."}],
    })
    assert restored.norma_id == "ley:15903:1987"
    assert restored.articulos[0].number == "1"
    assert restored.articulos[0].text == "Texto vigente."
