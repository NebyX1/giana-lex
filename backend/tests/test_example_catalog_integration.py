import json
from pathlib import Path

import pytest

from app import create_app
from config import settings
from example_catalog import ExampleCatalog, parse_dataset
from intake_fallback import generic_intake
from legal_knowledge.database import LegalKnowledgeDatabase
from schemas import LLMRun


class FakeAgents:
    def intake(self, context):
        return LLMRun(output=generic_intake(context["solicitud"]),
                      usage={"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, duration_ms=0)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "sample-resolutions" / "Catalogo-Gianna-Lex.html"


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    path = tmp_path_factory.mktemp("editorial") / "active.sqlite3"
    service = ExampleCatalog(LegalKnowledgeDatabase(f"sqlite:///{path.as_posix()}"), settings.examples_dir)
    result = service.import_bytes(CATALOG.read_bytes(), CATALOG.name, "test")
    assert result["created"] == 235
    return service


def test_real_html_batch_is_stable_and_preserves_policy(corpus):
    repeated = corpus.import_bytes(CATALOG.read_bytes(), CATALOG.name, "test")
    assert repeated["skipped"] == 235
    assert repeated["created"] == 0
    assert repeated["decisions"] == {
        "preferente": 13, "utilizable_con_ajustes": 187,
        "no_usar_como_modelo": 33, "pendiente_lectura": 2,
    }
    assert corpus.list({})["total"] == 235
    assert corpus.list({"q": "MVP-003"})["items"][0]["scope"] == "editorial"
    adjustable = corpus.list({"q": "MVC-002"})["items"][0]
    assert adjustable["scope"] == "structure"
    assert adjustable["enabled"]
    excluded = corpus.list({"q": "MVT-018"})["items"][0]
    assert not excluded["enabled"]
    assert excluded["id"] not in {item["id"] for item in corpus.search(excluded["title"], 100)["results"]}
    detail = corpus.get(adjustable["id"])
    assert detail["source_text"]
    assert detail["source_versions"][0]["declared_hash"]


EVALUATION = [
    ("Quiero investigar hechos denunciados sin atribuir todavía responsabilidad", "MVP-003"),
    ("Iniciar un sumario administrativo", "MVP-019"),
    ("Corregir la denominación de una empresa en una resolución", "MVP-006"),
    ("Delegar la expedición de un certificado tributario", "LAV-004"),
    ("Aumentar prestaciones de un contrato con consentimiento del proveedor", "MVC-002"),
    ("Corregir el número de una licitación", "MVC-033"),
    ("Aceptar una obra artística e incorporarla al patrimonio", "MVC-042"),
    ("Fijar indemnizaciones de expropiación parcial", "MVT-001"),
    ("Declarar de interés una iniciativa privada y reconocer costos eventuales", "MVT-014"),
    ("Revocar una multa porque no se dio vista", "MVR-005"),
    ("Analizar molestias por perros y ruidos", "MVT-030"),
    ("Preparar condiciones de un programa de becas", "MAL-001"),
    ("Regularizar obras mediante un procedimiento departamental", "MAL-013"),
    ("Permitir venta ambulante de alimentos", "LAV-031"),
    ("Devolver un inmueble al vencer el comodato", "MVC-023"),
    ("Abrir una investigación sin atribuir culpa", "MVP-003"),
    ("Enmendar un error en el nombre de una sociedad", "MVP-006"),
    ("Expedir certificado tributario mediante delegación", "LAV-004"),
    ("Recibir una pieza de arte donada", "MVC-042"),
    ("Intimar devolución de local dado en préstamo", "MVC-023"),
]

HOLDOUT = [
    ("Permitir que un contratista ceda el crédito de su contrato a un banco", "MVC-015"),
    ("Recibir dinero donado y abrir cuenta extrapresupuestal", "MVC-016"),
    ("Aceptar pase en comisión de trabajador de otra institución", "MVP-008"),
    ("Tramitar renuncia de funcionario que se jubila", "MVP-016"),
    ("Aceptar financiamiento de cooperación española para integración fronteriza", "CAN-029"),
    ("Reducir sanción al acoger parcialmente un recurso disciplinario", "MVP-023"),
    ("Modificar puntajes tras recursos de aspirantes de concurso", "MVP-036"),
    ("Adelantar prestación por muerte de un servidor público", "MAL-020"),
    ("Adjudicar licencias informáticas después de mejorar precio", "MVC-045"),
    ("Adjudicar obras de viviendas financiadas por el BID", "MVC-011"),
    ("Actualizar la tarifa del estacionamiento regulado", "MVT-025"),
    ("Extender contrato de construcción del Molino Viejo", "LVR-008"),
    ("Dejar sin efecto llamado y convocar una segunda licitación", "MVC-007"),
    ("Abrir la segunda etapa de un procedimiento licitatorio internacional", "MVC-013"),
    ("Aprobar una nueva estructura de oficinas municipales", "LVR-002"),
    ("Habilitar supermercado de gran superficie", "MVT-009"),
    ("Dictar reglas generales para licencias del personal", "CAN-005"),
    ("Aprobar protocolo de auditoría y código de ética", "CAN-014"),
    ("Adoptar protocolo laboral de transición de género", "MVP-028"),
    ("Alquilar inmueble departamental para gestión de residuos", "MVC-025"),
]


def test_recall_and_negative_cases(corpus):
    hits = 0
    for query, expected in EVALUATION:
        result = corpus.search(query, 5)
        hits += expected in {item["external_id"] for item in result["results"]}
        assert all(item["decision"] != "no_usar_como_modelo" for item in result["results"])
    assert hits / len(EVALUATION) >= .90, f"Recall@5: {hits}/{len(EVALUATION)}"
    assert corpus.search("Necesito hornear una pizza con queso", 5)["status"] == "out_of_scope"
    negated = corpus.search("No quiero sancionar, sólo investigar hechos", 5)
    assert negated["results"]
    assert "investigar" in negated["results"][0]["functions"]


def test_fresh_holdout_recall_is_at_least_ninety_percent(corpus):
    hits = sum(expected in {item["external_id"] for item in corpus.search(query, 5)["results"]}
               for query, expected in HOLDOUT)
    assert hits / len(HOLDOUT) >= .90, f"Holdout Recall@5: {hits}/{len(HOLDOUT)}"


def test_edit_publish_suspend_and_conflict(corpus):
    item = corpus.list({"q": "MVC-002"})["items"][0]
    detail = corpus.get(item["id"])
    original = detail["source_text"]
    saved = corpus.update(item["id"], {"expected_version": item["version"], "text": detail["active_text"] + "\nNota editorial.",
                                      "reason": "Depuración", "scope": "structure", "publish": False}, "editor")
    assert saved["revision_id"] == item["revision_id"]
    with pytest.raises(RuntimeError):
        corpus.update(item["id"], {"expected_version": item["version"], "publish": True}, "other")
    published = corpus.update(item["id"], {"expected_version": saved["version"], "text": detail["active_text"] + "\nNota editorial.",
                                            "scope": "structure", "reason": "Depuración", "publish": True}, "editor")
    assert published["revision_id"] != item["revision_id"]
    assert published["source_text"] == original
    suspended = corpus.update(item["id"], {"expected_version": published["version"], "publish": True,
                                            "scope": "structure", "suspend": True, "reason": "Revisión pendiente"}, "editor")
    assert not suspended["enabled"]
    assert item["id"] not in {candidate["id"] for candidate in corpus.search("ampliar prestaciones contractuales", 20)["results"]}


def test_changed_source_preserves_published_edit_and_records_conflict(tmp_path):
    service = ExampleCatalog(LegalKnowledgeDatabase(f"sqlite:///{(tmp_path / 'source.sqlite3').as_posix()}"))
    record = next(item for item in parse_dataset(CATALOG.read_bytes(), CATALOG.name) if item["id"] == "MVP-003")
    assert service.import_bytes(json.dumps([record]).encode(), "one.json")["created"] == 1
    doc = service.list({"q": "MVP-003"})["items"][0]
    published = service.update(doc["id"], {"expected_version": doc["version"], "text": "Modelo local corregido",
                                           "reason": "Revisión jurídica", "scope": "editorial", "publish": True}, "editor")
    changed = {**record, "texto_fuente": record["texto_fuente"] + "\nNueva publicación de fuente."}
    result = service.import_bytes(json.dumps([changed]).encode(), "changed.json")
    assert result["conflicted"] == 1
    detail = service.get(doc["id"])
    assert detail["revision_id"] == published["revision_id"]
    assert detail["active_text"] == "Modelo local corregido"
    assert len(detail["source_versions"]) == 2


def test_invalid_html_is_rejected_without_network_or_execution(corpus):
    before = corpus.list({})["total"]
    with pytest.raises(ValueError, match="script JSON"):
        corpus.import_bytes(b"<html><script>alert('x')</script></html>", "bad.html")
    assert corpus.list({})["total"] == before


def test_api_uses_same_catalog_for_conversation_and_settings(tmp_path):
    db_path = tmp_path / "active.sqlite3"
    app = create_app(settings, agents=FakeAgents(), database_path=db_path)
    app.testing = True
    client = app.test_client()
    with CATALOG.open("rb") as stream:
        import io
        imported = client.post("/api/settings/examples/import", data={"file": (io.BytesIO(stream.read()), CATALOG.name)})
    assert imported.status_code == 200
    assert imported.json["created"] == 235
    listing = client.get("/api/settings/examples?q=MVP-003")
    assert listing.json["total"] == 1
    preview = client.get("/api/settings/examples/search-preview?q=iniciar+investigacion")
    assert preview.json["results"]
    created = client.post("/api/conversations", json={"message": "Iniciar una investigación por hechos denunciados"})
    assert created.status_code == 200
    assert created.json["example_references"]
    assert created.json["example_references"][0]["id"] in {item["id"] for item in preview.json["results"]}
    assert "Encontré" in created.json["message"]
    assert "plantilla genérica" not in created.json["message"]


def test_context_uses_complete_clauses(corpus):
    item = corpus.search("aceptar una obra artística donada", 5)["results"][0]
    assert item["context_units"]
    assert item["authorized_content"] == "\n\n".join(item["context_units"])
    assert len(item["context_units"]) <= 2
    assert len(item["authorized_content"].split()) <= 360


def test_existing_draft_is_checked_before_approval_and_export(tmp_path):
    db_path = tmp_path / "active.sqlite3"
    app = create_app(settings, agents=FakeAgents(), database_path=db_path)
    app.testing = True
    client = app.test_client()
    bad = client.post("/api/conversations/check-draft", json={
        "context": "Restituir inmueble", "draft": "VISTO: padrón 4876. RESUELVE: 1. Restituir padrón 4786."})
    assert bad.status_code == 200
    assert bad.json["verification"]["status"] == "con_observaciones"
    assert client.post(f"/api/conversations/{bad.json['conversation_id']}/approve").status_code == 409
    good = client.post("/api/conversations/check-draft", json={
        "context": "Autorizar gestión", "draft": "VISTO: expediente 123. CONSIDERANDO: los informes del caso. RESUELVE: 1. Autorizar la gestión."})
    assert good.status_code == 200
    identifier = good.json["conversation_id"]
    assert good.json["verification"]["draft_hash"]
    assert client.post(f"/api/conversations/{identifier}/approve").status_code == 200
    assert client.get(f"/api/conversations/{identifier}/export").data[:2] == b"PK"
