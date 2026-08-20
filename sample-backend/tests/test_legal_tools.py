from pathlib import Path

from documents.legal_references import extract_legal_references
from ejemplos.loader import search_examples
from tools.compare_documents import compare_texts
from tools.review_procedure import tool as review_tool
from tools.verify_legal_reference import verify_reference


def test_reference_extractor_is_bounded_and_does_not_claim_verification():
    text = "Conforme a la Ley 123/2020 y al articulo 4 de la Ley 123/2020. Texto comun 99."
    references = extract_legal_references(text)

    assert [item["kind"] for item in references] == ["norma", "articulo", "norma"]
    assert all("status" not in item for item in references)


class FakeRag:
    def __init__(self, results):
        self.results = results

    def search(self, query, limit=5):
        assert limit <= 20
        return self.results


def test_verification_statuses_use_rag_evidence_only():
    verified = verify_reference(
        "Ley 123/2020",
        FakeRag([{"title": "Ley 123/2020", "source": "official:test"}]),
    )
    ambiguous = verify_reference(
        "Ley 123/2020",
        FakeRag([{"title": "Ley 123/2020 A"}, {"title": "Ley 123/2020 B"}]),
    )
    absent = verify_reference("Ley 123/2020", FakeRag([]))
    unavailable = verify_reference("Ley 123/2020", None)

    assert verified["status"] == "VERIFICADA"
    assert ambiguous["status"] == "AMBIGUA"
    assert absent["status"] == "NO ENCONTRADA"
    assert unavailable["status"] == "NO ENCONTRADA"


def test_examples_are_always_marked_non_authoritative(tmp_path):
    example = tmp_path / "authorized.md"
    example.write_text("Tramite administrativo de prueba.", encoding="utf-8")

    results = search_examples("tramite", tmp_path)

    assert results[0]["classification"] == "EXAMPLE"
    assert results[0]["is_authority"] is False
    assert "no constituye" in results[0]["warning"]


def test_comparison_and_review_do_not_make_legal_findings():
    comparison = compare_texts("uno\ndos", "uno\ntres")
    review = review_tool.invoke({"text": "VISTO:\nExpediente"})

    assert comparison["legal_assessment"] == "NO REALIZADA"
    assert comparison["identical"] is False
    assert review["assessment"] == "REVISION ESTRUCTURAL SOLAMENTE"
    assert "No se evaluaron" in review["warning"]
