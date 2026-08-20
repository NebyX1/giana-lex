from pathlib import Path

import pytest

from depto.extract import extract_html_text, extract_pdf_text, pdf_text_quality
from depto.download import DownloadedSource
from depto.normalize import detect_articles, detect_relations, strip_html
from depto.identity import build_norm_id, deterministic_filename, type_slug


HTML_FIXTURE = """<!DOCTYPE html><html><head><title>Decreto</title></head><body>
<nav>Menu repetido</nav>
<h1>Decreto Departamental N 3842/023</h1>
<p>Artículo 1. Se modifica el Estatuto del Funcionario.</p>
<p>Artículo 2. Derógase el Decreto 994/982.</p>
<footer>Pie de pagina</footer>
</body></html>""".encode("utf-8")


def test_extract_html_removes_nav_and_footer():
    src = DownloadedSource(url="u", final_url="u", content_type="text/html", raw=HTML_FIXTURE, encoding="utf-8")
    text = extract_html_text(src)
    assert "Menu repetido" not in text
    assert "Pie de pagina" not in text
    assert "Decreto Departamental" in text
    assert "Artículo 1" in text


def test_strip_html_removes_tags():
    assert strip_html("<p>Hola <b>mundo</b></p>") == "Hola mundo"


def test_detect_articles():
    text = "Artículo 1. Primera disposición.\nAlgo más.\nArtículo 35 BIS. Segunda disposición."
    articles = detect_articles(text)
    assert len(articles) == 2
    assert articles[0].number == "1"
    assert articles[0].bis == ""
    assert articles[1].number == "35"
    assert articles[1].bis == "BIS"
    assert "Algo más" in articles[0].text


def test_pdf_text_quality_rejects_empty():
    q = pdf_text_quality("")
    assert q["usable"] is False
    q = pdf_text_quality("   \n  ")
    assert q["usable"] is False


def test_pdf_text_quality_accepts_real_text():
    text = "Artículo 1. " + ("norma " * 100)
    q = pdf_text_quality(text)
    assert q["usable"] is True


def test_identity():
    assert build_norm_id("Decreto Departamental", "3842", "2023") == "decreto:3842:2023"
    assert build_norm_id("Ordenanza", "general", None) == "ordenanza:general:unknown"
    assert deterministic_filename("Decreto", "3842", "2023") == "decreto_3842_2023"
    assert type_slug("Decreto Departamental") == "decreto"


def test_detect_relations_incorpores():
    text = "Incorpórase al Decreto 500/991 el procedimiento administrativo aplicable en el departamento."
    rels = detect_relations(text, "decreto:1145:1993", evidence="e")
    assert any(r["relation"] == "INCORPORATES" and r["to"] == "decreto:500:1991" for r in rels)


def test_detect_relations_derogates():
    text = "Derógase el Decreto 994/982."
    rels = detect_relations(text, "decreto:3982:2025", evidence="e")
    assert any(r["relation"] == "DEROGATES" and r["to"] == "decreto:994:1982" for r in rels)


def test_pdf_extraction_with_pypdf(monkeypatch):
    # Build a minimal valid PDF via pypdf writer
    try:
        from pypdf import PdfWriter
    except ImportError:
        pytest.skip("pypdf not available")
    writer = PdfWriter()
    from io import BytesIO
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    raw = buf.getvalue()
    src = DownloadedSource(url="u", final_url="u", content_type="application/pdf", raw=raw, encoding=None)
    text, method = extract_pdf_text(src)
    # blank page yields empty text -> falls back to OCR attempt or empty
    assert method in ("pdf_text", "ocr")
    assert isinstance(text, str)