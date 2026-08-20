import json
import re
from pathlib import Path

from ejemplos.loader import (
    AUXILIARY_NAMES,
    EXAMPLES_ROOT,
    RESOLUCIONES_ROOT,
    list_resolution_examples,
    search_examples,
)

RESOLUTION_FILES = [
    "01_reintegro_gastos.md",
    "02_horas_extraordinarias.md",
    "03_compensacion_funcionario.md",
    "04_exoneracion_patente.md",
    "05_adjudicacion_licitacion.md",
    "06_aprobacion_convenio.md",
    "07_designacion_funcion.md",
    "08_modificacion_resolucion.md",
    "09_reiteracion_gasto_observado.md",
    "10_trasposicion_rubros.md",
    "11_subrogacion_funcionario.md",
]

EXPECTED_DOCUMENT_IDS = {
    "EX-RES-REINTEGRO-GASTOS",
    "EX-RES-HORAS-EXTRA",
    "EX-RES-COMPENSACION",
    "EX-RES-EXONERACION-PATENTE",
    "EX-RES-ADJUDICACION-LICITACION",
    "EX-RES-CONVENIO",
    "EX-RES-DESIGNACION",
    "EX-RES-MODIFICACION",
    "EX-RES-REITERACION-GASTO",
    "EX-RES-TRASPOSICION-RUBROS",
    "EX-RES-SUBROGACION",
    "IDL-RES-2629-026",
}

REQUIRED_FIELDS = ["document_id", "typology", "authority_level", "document_type", "jurisdiction", "tags"]
REQUIRED_HEADINGS = ["VISTO", "CONSIDERANDO", "ATENTO", "RESUELVE"]


def _read_resolution(name: str) -> str:
    return (RESOLUCIONES_ROOT / name).read_text(encoding="utf-8")


def test_eleven_example_files_exist():
    missing = [name for name in RESOLUTION_FILES if not (RESOLUCIONES_ROOT / name).is_file()]
    assert missing == []


def test_all_resolutions_are_classified_as_example():
    examples = {Path(item["path"]).name: item for item in list_resolution_examples()}
    for name in RESOLUTION_FILES:
        assert examples[name]["classification"] == "EXAMPLE"
        assert examples[name]["authority_level"] == "EXAMPLE"
        assert examples[name]["is_authority"] is False


def test_document_ids_are_unique_and_expected():
    ids = [item["document_id"] for item in list_resolution_examples()]
    assert len(ids) == len(set(ids)) == 12
    assert set(ids) == EXPECTED_DOCUMENT_IDS


def test_typologies_are_unique():
    typologies = [item["typology"] for item in list_resolution_examples()]
    assert len(typologies) == len(set(typologies)) == 12


def test_minimal_metadata_is_present():
    for item in list_resolution_examples():
        for field in REQUIRED_FIELDS:
            assert item.get(field) not in (None, ""), f"falta {field} en {item['path']}"


def test_legal_warning_present_in_each_file():
    for name in RESOLUTION_FILES:
        assert "NO CONSTITUYE ACTO ADMINISTRATIVO NI FUENTE JURÍDICA" in _read_resolution(name)


def test_resolutive_structure_present():
    for name in RESOLUTION_FILES:
        text = _read_resolution(name)
        upper = text.upper()
        for heading in REQUIRED_HEADINGS:
            assert re.search(rf"\b{heading}\b", upper), f"falta {heading} en {name}"


def test_numeral_and_resolutive_section_present():
    for name in RESOLUTION_FILES:
        text = _read_resolution(name)
        assert "1°.-" in text, f"falta numeral 1°.- en {name}"
        assert "RESUELVE" in text.upper(), f"falta seccion RESUELVE en {name}"


def test_placeholders_present():
    for name in RESOLUTION_FILES:
        assert re.search(r"\[[A-Z][^\]]+\]", _read_resolution(name)), f"falta placeholder en {name}"


def test_manifest_is_valid_and_consistent():
    manifest = json.loads((RESOLUCIONES_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["authority_policy"]["all_documents_are_examples"] is True
    assert manifest["authority_policy"]["may_be_used_as_legal_authority"] is False
    documents = manifest["documents"]
    assert len(documents) == 12
    by_file = {Path(item["path"]).name: item for item in list_resolution_examples()}
    for entry in documents:
        file_path = RESOLUCIONES_ROOT / entry["file"]
        assert file_path.is_file(), f"manifest apunta a archivo inexistente {entry['file']}"
        example = by_file[entry["file"]]
        assert example["document_id"] == entry["document_id"]
        assert example["typology"] == entry["typology"]
        assert example["title"] == entry["title"]
        assert sorted(example["tags"]) == sorted(entry["tags"])


def test_auxiliary_files_are_not_loaded_as_resolutions():
    examples = [Path(item["path"]).name for item in list_resolution_examples()]
    assert "README.md" not in examples
    assert "GUIA_USO_AGENTE.md" not in examples
    assert "manifest.json" not in examples


def test_examples_never_enter_authoritative_knowledge_pipeline():
    from ingestion.loader import KNOWLEDGE_ROOT, load_documents

    knowledge_tree = {path.name for path in KNOWLEDGE_ROOT.rglob("*")}
    assert EXAMPLES_ROOT.name not in knowledge_tree

    documents = load_documents()
    for document in documents:
        assert "ejemplos" not in document["source_file"]


def test_authority_protection_filter_excludes_examples():
    # La busqueda autoritativa opera sobre knowledge/, nunca sobre ejemplos/.
    from ingestion.loader import CORPUS_DIRECTORIES

    assert all("ejemplos" not in str(path) for path in CORPUS_DIRECTORIES.values())


def _favored_typology(query: str) -> str | None:
    results = search_examples(query, RESOLUCIONES_ROOT, limit=5)
    if not results:
        return None
    return results[0]["typology"]


def test_semantic_typology_selection():
    cases = {
        "Necesito redactar una resolucion para pagar horas extra a personal municipal.": "autorizacion_horas_extraordinarias",
        "Tenemos que adjudicar una licitacion abreviada.": "adjudicacion_licitacion",
        "Hay que corregir el numeral segundo de una resolucion anterior.": "modificacion_resolucion_anterior",
        "El Contador Delegado observo el gasto pero el Ejecutivo quiere mantenerlo.": "reiteracion_gasto_observado",
        "El jefe se va de licencia y otro funcionario debe ocupar temporalmente el cargo.": "designacion_subrogante",
    }
    for query, expected in cases.items():
        assert _favored_typology(query) == expected, f"consulta no favorece {expected}"


def test_search_examples_does_not_match_every_document_on_spanish_stop_words():
    assert search_examples("contratación por arrendamiento de obra arquitecto") == []


def test_agent_has_example_authority_warning():
    prompt = (EXAMPLES_ROOT.parent / "agent" / "prompts" / "GIANA_LEX.md").read_text(encoding="utf-8")
    assert "EXAMPLE solo constituyen ejemplos de estructura y redaccion" in prompt
    assert "No los utilices como autoridad juridica" in prompt
