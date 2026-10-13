from pathlib import Path

import pytest

from example_catalog import ExampleCatalog
from example_verification import verify_draft
from legal_knowledge.database import LegalKnowledgeDatabase


@pytest.fixture(scope="module")
def catalog(tmp_path_factory):
    root = Path(__file__).resolve().parents[2]
    db = tmp_path_factory.mktemp("verification") / "verification.sqlite3"
    service = ExampleCatalog(LegalKnowledgeDatabase(f"sqlite:///{db.as_posix()}"))
    source = root / "sample-resolutions" / "Catalogo-Gianna-Lex.html"
    service.import_bytes(source.read_bytes(), source.name)
    return service


@pytest.mark.parametrize("external_id,expected", [
    ("LVR-004", "padron"),
    ("CAN-023", "importe_ur"),
    ("MVT-018", "efecto"),
    ("MVT-021", "articulado"),
    ("MAL-013", "cita_interna"),
    ("MVP-033", "motivacion_prorroga"),
])
def test_real_corpus_discrepancies_are_localized(catalog, external_id, expected):
    item = catalog.list({"q": external_id})["items"][0]
    text = catalog.get(item["id"])["source_text"]
    report = verify_draft(text, {}, [], 0)
    matching = [finding for finding in report.findings if finding.category == expected]
    assert matching, external_id
    assert matching[0].location
    assert matching[0].evidence
    assert matching[0].action


def test_critical_inconsistency_is_not_resolved_by_free_text():
    draft = "VISTO: el padrón 4876. RESUELVE: transferir el padrón 4786."
    first = verify_draft(draft, {}, [], 0)
    critical = next(finding for finding in first.findings if finding.category == "padron")
    second = verify_draft(draft, {}, [], 0, resolved={critical.id: "Está bien"})
    assert not next(finding for finding in second.findings if finding.category == "padron").resolved


def test_report_tracks_draft_hash_and_does_not_certify_norms():
    report = verify_draft("VISTO: expediente 123. RESUELVE: 1. Autorizar.", {}, [], 2)
    assert report.draft_revision == 2
    assert len(report.draft_hash) == 64
    assert report.normative_status["content"] == "not_checked"
    assert report.status == "informacion_insuficiente"
