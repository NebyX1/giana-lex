import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from depto.service import DepartmentalNormImporter, DeptoService
from depto.download import DownloadedSource
from depto.extract import (
    DeptoExtractionError,
    extract_decree_from_official_minutes,
    extract_html_text,
    extract_official_compilation_section,
    extract_official_document_body,
)
from depto.normalize import detect_articles
from depto import storage as st


def make_html_source(url="https://www.gub.uy/test"):
    html = """<html><body><h1>Decreto Departamental N 3842/023</h1>
    <p>Artículo 1. Se modifica el Estatuto del Funcionario.</p>
    <p>Artículo 2. Incorpórase el Decreto 994/982.</p>
    </body></html>""".encode("utf-8")
    return DownloadedSource(url=url, final_url=url, content_type="text/html", raw=html, encoding="utf-8")


def test_html_extractor_resumes_after_header_with_void_elements():
    html = """<html><body>
    <header><img src="logo.png"><nav><a href="/">Inicio</a></nav></header>
    <main><article><h1>Decreto 3842</h1>
    <p>Artículo 1. Texto normativo que debe conservarse.</p></article></main>
    </body></html>""".encode("utf-8")
    source = DownloadedSource(
        url="https://www.gub.uy/test",
        final_url="https://www.gub.uy/test",
        content_type="text/html",
        raw=html,
        encoding="utf-8",
    )

    text = extract_html_text(source)

    assert "Inicio" not in text
    assert "Decreto 3842" in text
    assert "Artículo 1" in text


def test_extract_decree_from_official_minutes_ignores_prior_mentions():
    acta = """Se considera el Decreto N° 3589 en comisión.
    DECRETO N� 3589.
    LA JUNTA DEPARTAMENTAL DE LAVALLEJA DECRETA:
    Art�culo 1� - Der�gase la disposición anterior.
    Art�culo 2� - Comun�quese.
    *****   ***   *****
    ASUNTO SIGUIENTE
    Artículo 1. Este texto no pertenece al decreto.
    """

    result = extract_decree_from_official_minutes(acta, "3589")

    assert result.startswith("DECRETO N 3589")
    assert "Articulo 2" in result
    assert "ASUNTO SIGUIENTE" not in result


def test_extract_decree_from_official_minutes_requires_enactment_formula():
    with pytest.raises(DeptoExtractionError):
        extract_decree_from_official_minutes("Se menciona el Decreto N° 3589.", "3589")


def test_extract_official_compilation_section_stops_before_next_document():
    text = (
        "PORTADA\nESTATUTO DEL FUNCIONARIO MUNICIPAL\n"
        + "ARTICULO 1. Texto del estatuto.\n" * 30
        + "DIGESTO DE TRANSITO\nARTICULO 1. Texto ajeno."
    )

    result = extract_official_compilation_section(
        text, "ESTATUTO DEL FUNCIONARIO MUNICIPAL", "DIGESTO DE TRANSITO"
    )

    assert result.startswith("ESTATUTO DEL FUNCIONARIO MUNICIPAL")
    assert "Texto del estatuto" in result
    assert "Texto ajeno" not in result


def test_extract_official_document_body_removes_table_of_contents():
    text = (
        "INDICE\nArtículo 1. Aprobación ........ 1\n"
        "TITULO I\nDisposiciones Preliminares\nArtículo 1º - Aprobación.\n"
        + "Contenido normativo completo.\n" * 30
    )

    result = extract_official_document_body(
        text,
        r"(?m)^TITULO I\s*\nDisposiciones Preliminares\s*\nArtículo 1[º°]?\s*-\s*Aprobación\.",
    )

    assert result.startswith("TITULO I")
    assert "........ 1" not in result


def test_article_cross_reference_is_not_promoted_to_top_level_article():
    text = """Artículo 1º - Regla principal.
    Se aplicará lo previsto en el Artículo 25º Zonas Reglamentadas.
    Artículo 2º - Comuníquese.
    """

    articles = detect_articles(text)

    assert [article.number for article in articles] == ["1", "2"]
    assert "Artículo 25" in articles[0].text


def test_import_indirect_creates_stub_no_text(tmp_path, monkeypatch):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    importer = DepartmentalNormImporter(embedder=MagicMock(), store=MagicMock())
    result = importer.import_indirect(
        norm_id="decreto:524:1977", norm_type="Decreto", number="524", year="1977",
        family="tributaria_departamental",
        evidence_urls=["https://www.gub.uy/evidence"],
    )
    assert result.status == "indirect"
    assert result.text_available is False
    entry = st.load_registry()["decreto:524:1977"]
    assert entry["text_available"] is False
    assert entry["active_for_rag"] is False
    assert entry["source_quality"] == "official_indirect_reference"
    assert entry["original_found"] is False
    # no fake chunks
    assert entry["chunk_count"] == 0
    assert entry["article_count"] == 0


def test_import_source_with_mock_download(monkeypatch, tmp_path):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    src = make_html_source()
    fake_store = MagicMock()
    fake_store.ensure_collection = MagicMock()
    fake_store.delete_source = MagicMock()
    fake_store.upsert = MagicMock(return_value=2)
    fake_embedder = MagicMock()
    fake_embedder.vector_size = 3
    fake_embedder.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    importer = DepartmentalNormImporter(embedder=fake_embedder, store=fake_store)
    result = importer._import_downloaded(
        src, norm_type="Decreto", number="3842", year="2023",
        family="estatuto_funcionario", title="Test", source_quality="primary_full_text",
        active=True, index=True, evidence_url=None,
    )
    assert result.status in ("created",)
    assert result.article_count == 2
    assert result.chunk_count == 2
    entry = st.load_registry()["decreto:3842:2023"]
    assert entry["text_available"] is True
    assert entry["indexed"] is True
    assert entry["active_for_rag"] is True
    metadata_path = tmp_path / "decretos" / "decreto_3842_2023" / "metadata.json"
    persisted_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert persisted_metadata["indexed"] is True
    assert persisted_metadata["chunk_count"] == 2


def test_non_articulated_document_uses_text_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    body = ("Disposición general de ordenamiento territorial y desarrollo sostenible. " * 12).encode("utf-8")
    source = DownloadedSource(
        url="https://www.gub.uy/test",
        final_url="https://www.gub.uy/test",
        content_type="text/plain",
        raw=body,
        encoding="utf-8",
    )
    fake_store = MagicMock()
    fake_embedder = MagicMock()
    fake_embedder.vector_size = 3
    fake_embedder.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    importer = DepartmentalNormImporter(embedder=fake_embedder, store=fake_store)

    result = importer._import_downloaded(
        source, norm_type="Decreto", number="10", year="2024",
        family="general", title="Disposición general", source_quality="primary_full_text",
        active=True, index=True, evidence_url=None,
    )

    entry = st.load_registry()["decreto:10:2024"]
    assert result.article_count == 0
    assert result.chunk_count > 0
    assert entry["text_available"] is True
    assert entry["processing_state"] == "ready"
    assert entry["indexed"] is True


def test_title_only_page_is_not_marked_as_usable(monkeypatch, tmp_path):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    source = DownloadedSource(
        url="https://www.gub.uy/test",
        final_url="https://www.gub.uy/test",
        content_type="text/html",
        raw=b"<html><body><h1>Decreto departamental 10/2024</h1></body></html>",
        encoding="utf-8",
    )
    importer = DepartmentalNormImporter(embedder=MagicMock(), store=MagicMock())

    result = importer._import_downloaded(
        source, norm_type="Decreto", number="10", year="2024",
        family="general", title="Decreto 10", source_quality="primary_full_text",
        active=True, index=True, evidence_url=None,
    )

    entry = st.load_registry()["decreto:10:2024"]
    assert result.text_available is False
    assert entry["active_for_rag"] is False
    assert entry["processing_state"] == "source_without_usable_text"


def test_dedup_same_norm_same_url(monkeypatch, tmp_path):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    fake_store = MagicMock()
    fake_embedder = MagicMock()
    fake_embedder.vector_size = 3
    fake_embedder.embed = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    importer = DepartmentalNormImporter(embedder=fake_embedder, store=fake_store)
    src = make_html_source()
    importer._import_downloaded(src, norm_type="Decreto", number="3842", year="2023", family="estatuto_funcionario", title="T", source_quality="primary_full_text", active=True, index=True, evidence_url=None)
    result2 = importer._import_downloaded(src, norm_type="Decreto", number="3842", year="2023", family="estatuto_funcionario", title="T", source_quality="primary_full_text", active=True, index=True, evidence_url=None)
    assert result2.status == "unchanged"
    reg = st.load_registry()
    assert len(reg) == 1


def test_relationships_saved_and_queryable(tmp_path, monkeypatch):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr("depto.storage.RELATIONSHIPS_PATH", tmp_path / "relationships.json")
    st.add_relationship({"from": "decreto:3842:2023", "relation": "MODIFIES", "to": "decreto:994:1982", "status": "verified", "evidence_source": "e"})
    rels = st.relationships_for("decreto:994:1982")
    assert any(r["from"] == "decreto:3842:2023" and r["relation"] == "MODIFIES" for r in rels)
    mods = st.modifiying_norms_for_article("decreto:994:1982", "1")
    assert any(r["from"] == "decreto:3842:2023" for r in mods)


def test_service_stats(tmp_path, monkeypatch):
    monkeypatch.setattr("depto.storage.DEPARTAMENTAL_ROOT", tmp_path)
    monkeypatch.setattr("depto.storage.REGISTRY_PATH", tmp_path / "registry.json")
    fake_store = MagicMock()
    fake_embedder = MagicMock()
    importer = DepartmentalNormImporter(embedder=fake_embedder, store=fake_store)
    importer._import_downloaded(make_html_source(), norm_type="Decreto", number="3842", year="2023", family="estatuto_funcionario", title="T", source_quality="primary_full_text", active=True, index=False, evidence_url=None)
    service = DeptoService(embedder=fake_embedder, store=fake_store)
    stats = service.get_stats()
    assert stats["total"] == 1
    assert stats["with_text"] == 1
