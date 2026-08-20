import builtins
import sys
import types
from pathlib import Path

import pytest

from documents.parsers import DocumentParseError, normalize_text, parse_document
from documents.resolution import LegalResolutionDraft, Resolution, parse_resolution
from moldes.loader import load_mold
from tools.create_docx import render_resolution_docx
from tools.registry import ToolRegistry


def test_plain_document_is_normalized_and_confined(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    document = root / "sample.TXT"
    document.write_bytes(b"Uno  \r\nDos\x00\r\n")

    parsed = parse_document(document, allowed_root=root)

    assert parsed.format == "txt"
    assert parsed.text == "Uno\nDos"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(DocumentParseError, match="fuera"):
        parse_document(outside, allowed_root=root)


def test_parser_rejects_unsupported_and_oversized_files(tmp_path):
    unsupported = tmp_path / "sample.rtf"
    unsupported.write_text("x", encoding="utf-8")
    with pytest.raises(DocumentParseError, match="Formato no admitido"):
        parse_document(unsupported)

    text = tmp_path / "large.txt"
    text.write_text("1234", encoding="utf-8")
    with pytest.raises(DocumentParseError, match="supera"):
        parse_document(text, max_bytes=3)


def test_pdf_optional_dependency_error_is_clear(tmp_path, monkeypatch):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-placeholder")
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("mocked")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(DocumentParseError, match="pypdf"):
        parse_document(pdf)


def test_resolution_parser_produces_validated_structure():
    result = parse_resolution(
        "RESOLUCION N 12/2026\n\nVISTO:\nEl expediente 10;\n\n"
        "CONSIDERANDO:\nQue existen antecedentes;\n\n"
        "ARTICULO 1: Autorizar el tramite.\nARTICULO 2: Registrar.\n\n"
        "FIRMAS:\nNombre y cargo"
    )

    validated = Resolution.model_validate(result)
    assert validated.number == "12/2026"
    assert [article.number for article in validated.articles] == ["1", "2"]
    assert not validated.notes


def test_resolution_parser_detects_resultando_and_atento():
    result = parse_resolution(
        "VISTO: El expediente.\nRESULTANDO: Que existe una actuacion.\n"
        "CONSIDERANDO: Que corresponde revisarla.\nATENTO: A las fuentes disponibles.\n"
        "RESUELVE:\nARTICULO 1: Continuar el analisis."
    )
    assert result["resultandos"] == ["Que existe una actuacion."]
    assert result["atento"] == "A las fuentes disponibles."


def test_mold_is_external_editable_template():
    mold = load_mold("resolucion_basica.md")
    assert mold["editable"] is True
    assert mold["authority_level"] == "TEMPLATE"
    assert mold["legal_status"] == "TEMPLATE"
    assert mold["is_authority"] is False
    assert "TODO pendiente validacion juridica" not in mold["content"]


def test_all_foundation_tools_are_discoverable():
    names = ToolRegistry().discover().names
    assert {
        "read_document", "analyze_resolution", "extract_legal_references",
        "verify_legal_reference", "search_examples", "load_mold",
        "compare_with_mold", "review_procedure", "compare_documents", "create_docx",
    } <= names


def test_docx_renderer_uses_validated_json_and_optional_library(tmp_path, monkeypatch):
    saved = {}

    class Paragraph:
        alignment = None

        def add_run(self, _text):
            return types.SimpleNamespace(bold=False)

    class FakeDocument:
        def add_heading(self, *_args, **_kwargs):
            return Paragraph()

        def add_paragraph(self, *_args, **_kwargs):
            return Paragraph()

        def save(self, path):
            saved["path"] = path

    docx = types.ModuleType("docx")
    docx.Document = FakeDocument
    enum_text = types.ModuleType("docx.enum.text")
    enum_text.WD_ALIGN_PARAGRAPH = types.SimpleNamespace(CENTER=1)
    monkeypatch.setitem(sys.modules, "docx", docx)
    monkeypatch.setitem(sys.modules, "docx.enum", types.ModuleType("docx.enum"))
    monkeypatch.setitem(sys.modules, "docx.enum.text", enum_text)

    output = tmp_path / "resolution.docx"
    resolution = LegalResolutionDraft(
        visto="El expediente.",
        resultandos=["Que se incorporo documentacion."],
        considerandos=["Que corresponde verificar el fundamento."],
        atento="A las fuentes que se validen.",
        resuelve=[{"number": "1", "text": "Registrar."}],
    )
    result = render_resolution_docx(resolution, output, tmp_path)

    assert saved["path"] == str(output.resolve())
    assert result["validated"] is True
    assert result["legal_approval"] is False


def test_normalize_text_is_deterministic():
    assert normalize_text("a\r\n\r\n\r\n\r\nb  ") == "a\n\n\nb"
