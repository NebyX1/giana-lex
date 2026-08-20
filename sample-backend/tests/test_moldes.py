import re
from pathlib import Path

from moldes.loader import MOLDS_ROOT, load_mold

EXPECTED_MOLDS = [
    "contrato-arrendamiento-obra.md",
    "informe-juridico.md",
    "proyecto-decreto.md",
    "resolucion_basica.md",
    "resolucion-adjudicacion.md",
    "resolucion-contratacion.md",
    "resolucion-convenio.md",
    "resolucion-exoneracion.md",
]


def _load(name: str) -> dict:
    return load_mold(name)


def test_expected_molds_exist():
    for name in EXPECTED_MOLDS:
        assert (MOLDS_ROOT / name).is_file(), f"falta {name}"


def test_all_molds_load():
    for name in EXPECTED_MOLDS:
        mold = _load(name)
        assert mold["content"].strip(), f"{name} sin contenido"


def test_all_molds_are_template():
    for name in EXPECTED_MOLDS:
        mold = _load(name)
        assert mold["authority_level"] == "TEMPLATE", f"{name} no es TEMPLATE"
        assert mold["is_authority"] is False, f"{name} no debe ser autoridad"
        assert mold["legal_status"] == "TEMPLATE"


def _document_body(name: str) -> str:
    """Return only the document part of the mold, excluding internal instructions."""
    content = _load(name)["content"]
    marker = "## Instrucciones internas"
    return content.split(marker, 1)[0]


def test_resolucion_basica_uses_numerales_not_articulos():
    content = _document_body("resolucion_basica.md")
    assert "VISTO" in content
    assert "CONSIDERANDO" in content
    assert "ATENTO" in content
    assert "RESUELVE" in content
    assert "1°.-" in content
    assert "ARTÍCULO 1°" not in content
    assert "ARTICULO 1" not in content


def test_resultando_is_conditional():
    content = _load("resolucion_basica.md")["content"]
    assert "RESULTANDO" in content
    assert "INCLUIR CUANDO SEA NECESARIO" in content


def test_proyecto_decreto_uses_articulos():
    content = _load("proyecto-decreto.md")["content"]
    assert "Artículo 1°.-" in content
    assert "PROYECTO DE DECRETO" in content
    assert "RESUELVE" in content


def test_contratacion_has_three_variants():
    mold = _load("resolucion-contratacion.md")
    assert "personal" in mold["variants"]
    assert "arrendamiento_servicios" in mold["variants"]
    assert "servicio_proveedor" in mold["variants"]
    content = mold["content"]
    assert "VARIANTE A" in content
    assert "VARIANTE B" in content
    assert "VARIANTE C" in content


def test_arrendamiento_obra_has_contractual_controls():
    mold = _load("contrato-arrendamiento-obra.md")
    assert mold["document_type"] == "contrato"
    assert mold["subtype"] == "arrendamiento_obra"
    content = mold["content"]
    for section in ("Objeto y resultado", "criterios de aceptación", "Independencia técnica", "Terminación"):
        assert section in content


def test_exoneracion_distinguishes_directa_and_junta():
    mold = _load("resolucion-exoneracion.md")
    assert "directa" in mold["variants"]
    assert "junta" in mold["variants"]
    content = mold["content"]
    assert "VARIANTE DIRECTA" in content
    assert "VARIANTE JUNTA" in content
    assert "Elévese a consideración de la Junta Departamental" in content


def test_adjudicacion_supports_items():
    mold = _load("resolucion-adjudicacion.md")
    assert "total" in mold["variants"]
    assert "por_items" in mold["variants"]
    content = mold["content"]
    assert "Adjudicación por ítems" in content
    assert "DESIERTO" in content
    assert "RECHAZADO" in content


def test_convenio_distinguishes_aprobacion_suscripcion_ejecucion():
    content = _load("resolucion-convenio.md")["content"]
    assert "APROBAR EL PROYECTO" in content
    assert "SUSCRIBIR EL CONVENIO" in content
    assert "EJECUTAR EL CONVENIO" in content


def test_informe_juridico_has_required_sections():
    content = _load("informe-juridico.md")["content"]
    for section in ("ANTECEDENTES", "CUESTIÓN JURÍDICA", "NORMATIVA", "ANÁLISIS", "COMPETENCIA", "CONCLUSIÓN"):
        assert section in content, f"falta sección {section}"


def test_no_todo_fixme_in_molds():
    for name in EXPECTED_MOLDS:
        content = _load(name)["content"]
        assert "TODO" not in content, f"{name} contiene TODO"
        assert "FIXME" not in content, f"{name} contiene FIXME"
        assert "Lorem ipsum" not in content, f"{name} contiene Lorem ipsum"
        assert "pendiente validacion juridica" not in content.lower(), f"{name} contiene pendiente validacion"


def test_numeral_sequence_consistency():
    for name in ("resolucion_basica.md", "resolucion-adjudicacion.md", "resolucion-convenio.md", "resolucion-exoneracion.md"):
        content = _document_body(name)
        numerals = re.findall(r"(\d+)°\.-", content)
        if numerals:
            expected = list(range(1, len(numerals) + 1))
            assert [int(n) for n in numerals] == expected, f"{name} numerales fuera de secuencia"


def test_article_sequence_consistency():
    content = _document_body("proyecto-decreto.md")
    articles = re.findall(r"Artículo (\d+)°\.-", content)
    if articles:
        expected = list(range(1, len(articles) + 1))
        assert [int(n) for n in articles] == expected, "artículos fuera de secuencia"


def test_mold_never_used_as_authority():
    for name in EXPECTED_MOLDS:
        mold = _load(name)
        assert mold["authority_level"] == "TEMPLATE"
        assert mold["is_authority"] is False


def test_example_vs_template_separation():
    from ejemplos.loader import list_resolution_examples

    examples = list_resolution_examples()
    assert all(item["authority_level"] == "EXAMPLE" for item in examples)
    for name in EXPECTED_MOLDS:
        assert _load(name)["authority_level"] == "TEMPLATE"


def test_forbidden_inference_metadata_present():
    for name in EXPECTED_MOLDS:
        mold = _load(name)
        assert "norma" in mold["forbidden_inference"], f"{name} sin forbidden_inference norma"
        assert "monto" in mold["forbidden_inference"], f"{name} sin forbidden_inference monto"
        assert "fecha" in mold["forbidden_inference"], f"{name} sin forbidden_inference fecha"
