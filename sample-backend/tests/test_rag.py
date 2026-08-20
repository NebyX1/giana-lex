import importlib.util
import importlib
from pathlib import Path

import pytest

from ingestion.chunking import legal_chunk_text
from ingestion.pipeline import ingest_knowledge
from rag.constants import DEPARTMENTAL_COLLECTION, NATIONAL_COLLECTION
from rag.retriever import LegalRetriever
from tools.base import Tool


class FakeEmbedder:
    vector_size = 3

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0, 0.0] for text in texts]


class FakeStore:
    def __init__(self):
        self.collections = {}
        self.deleted_sources = []
        self.ensured = []
        self.search_hits = []
        self.search_call = None

    def ensure_collection(self, collection, vector_size, rebuild=False):
        self.ensured.append((collection, vector_size, rebuild))
        if rebuild or collection not in self.collections:
            self.collections[collection] = []

    def upsert(self, collection, points):
        self.collections.setdefault(collection, []).extend(points)
        return len(points)

    def delete_source(self, collection, source_file):
        self.deleted_sources.append((collection, source_file))
        self.collections[collection] = [
            point for point in self.collections.get(collection, [])
            if point["payload"]["source_file"] != source_file
        ]

    def list_sources(self, collection, corpus=None):
        return {
            point["payload"]["source_file"]
            for point in self.collections.get(collection, [])
            if corpus is None or point["payload"]["corpus"] == corpus
        }

    def search(self, collection, vector, limit, filters=None):
        self.search_call = (collection, list(vector), limit, filters)
        return self.search_hits[:limit]


def test_optional_vector_dependencies_are_not_required_for_imports():
    assert importlib.util.find_spec("rag") is not None
    from rag.embeddings import FastEmbedder

    embedder = FastEmbedder()
    assert embedder.vector_size == 384


def test_legal_chunking_tracks_hierarchy_and_fixed_fallback():
    text = """TITULO I Disposiciones
CAPITULO I Principios
Articulo 1. Ambito de aplicacion.
Inciso 1. La norma rige en todo el departamento.
Numeral 1. Primer supuesto.
Literal a) Detalle.
Articulo 2. Vigencia inmediata."""
    chunks = legal_chunk_text(text, chunk_size=200, overlap=20)

    article_two = next(chunk for chunk in chunks if chunk["text"].startswith("Articulo 2"))
    assert article_two["article"].startswith("Articulo 2")
    assert article_two["legal_path"]["titulo"].startswith("TITULO I")
    assert "inciso" not in article_two["legal_path"]
    fallback = legal_chunk_text("palabra " * 80, chunk_size=100, overlap=10)
    assert len(fallback) > 1
    assert all(len(chunk["text"]) <= 100 for chunk in fallback)


def test_ingestion_builds_required_metadata_and_is_reproducible(tmp_path):
    departmental = tmp_path / "departamental" / "resoluciones"
    national = tmp_path / "nacional" / "leyes"
    departmental.mkdir(parents=True)
    national.mkdir(parents=True)
    (departmental / "Resolucion_12_2024.txt").write_text(
        "Articulo 1. Autorizar la contratacion.", encoding="utf-8"
    )
    (national / "Ley_19889_2020.md").write_text(
        "Articulo 2. La ley entra en vigencia.", encoding="utf-8"
    )
    store = FakeStore()
    timestamp = "2026-01-02T03:04:05+00:00"

    first = ingest_knowledge(tmp_path, FakeEmbedder(), store, indexed_at=timestamp)
    first_ids = {
        point["id"] for points in store.collections.values() for point in points
    }
    second = ingest_knowledge(tmp_path, FakeEmbedder(), store, indexed_at=timestamp)
    second_ids = {
        point["id"] for points in store.collections.values() for point in points
    }

    assert first["documents"] == second["documents"] == 2
    assert first_ids == second_ids
    assert set(store.collections) == {DEPARTMENTAL_COLLECTION, NATIONAL_COLLECTION}
    payload = store.collections[DEPARTMENTAL_COLLECTION][0]["payload"]
    required = {
        "corpus", "category", "document_type", "title", "number", "year", "article",
        "source_file", "source_url", "source_hash", "indexed_at",
    }
    assert required <= payload.keys()
    assert payload["category"] == "resoluciones"
    assert payload["year"] == 2024
    assert payload["metadata"]["source_hash"] == payload["source_hash"]


def test_ingestion_replaces_changed_and_stale_documents(tmp_path):
    directory = tmp_path / "departamental" / "decretos"
    directory.mkdir(parents=True)
    path = directory / "Decreto_1_2025.txt"
    path.write_text("Articulo 1. Texto original.", encoding="utf-8")
    store = FakeStore()
    ingest_knowledge(tmp_path, FakeEmbedder(), store)

    path.write_text("Articulo 1. Texto modificado.", encoding="utf-8")
    ingest_knowledge(tmp_path, FakeEmbedder(), store)
    points = store.collections[DEPARTMENTAL_COLLECTION]
    assert len(points) == 1
    assert points[0]["payload"]["text"].endswith("modificado.")

    path.unlink()
    stats = ingest_knowledge(tmp_path, FakeEmbedder(), store)
    assert store.collections[DEPARTMENTAL_COLLECTION] == []
    assert stats["collections"][DEPARTMENTAL_COLLECTION]["stale_removed"] == 1


def test_rebuild_recreates_both_collections(tmp_path):
    store = FakeStore()
    store.collections[DEPARTMENTAL_COLLECTION] = [{"payload": {"source_file": "old"}}]
    ingest_knowledge(tmp_path, FakeEmbedder(), store, rebuild=True)
    assert set(store.ensured) == {
        (DEPARTMENTAL_COLLECTION, 3, True),
        (NATIONAL_COLLECTION, 3, True),
    }
    assert store.collections[DEPARTMENTAL_COLLECTION] == []


def test_retriever_preserves_traceable_result_contract():
    store = FakeStore()
    store.search_hits = [{
        "id": "point-1",
        "score": 0.91,
        "payload": {
            "text": "Articulo 1. Texto.",
            "corpus": "departamental",
            "active": True,
            "source_file": "departamental/decretos/d1.txt",
            "category": "decretos",
            "title": "Decreto 1",
            "year": 2025,
            "metadata": {"number": "1"},
        },
    }]
    retriever = LegalRetriever(FakeEmbedder(), store)
    result = retriever.search("contratacion", "departamental", category="decretos")

    assert result == [{
        "identifier": "point-1",
        "text": "Articulo 1. Texto.",
        "source": "departamental/decretos/d1.txt",
        "category": "decretos",
        "metadata": {
            "number": "1", "corpus": "departamental", "category": "decretos", "title": "Decreto 1",
            "year": 2025, "source_file": "departamental/decretos/d1.txt",
            "active": True,
        },
        "score": pytest.approx(0.91),
    }]
    assert store.search_call[0] == DEPARTMENTAL_COLLECTION
    assert store.search_call[3]["category"] == "decretos"


def test_three_search_tools_are_independently_discoverable_and_use_pydantic():
    names = ["search_departmental_norms", "search_national_norms", "search_resolutions"]
    tools = {
        name: importlib.import_module(f"tools.{name}").tool
        for name in names
    }
    assert all(isinstance(tool, Tool) for tool in tools.values())
    assert set(tools) == {tool.name for tool in tools.values()}
    fake = LegalRetriever(FakeEmbedder(), FakeStore())
    assert tools["search_resolutions"].invoke(
        {"query": "antecedente", "top_k": 2}, {"legal_retriever": fake}
    ) == []
    with pytest.raises(ValueError):
        tools["search_national_norms"].invoke(
            {"query": "x", "top_k": 0}, {"legal_retriever": fake}
        )
