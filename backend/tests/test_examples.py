from pathlib import Path

import pytest

from tools.search_examples import has_lexical_support, search_examples


def test_search_examples_reads_real_files_dynamically():
    examples_dir = Path(__file__).parents[1] / "examples"
    results = search_examples("compensacion mensual para un funcionario", examples_dir, limit=100)

    assert results
    assert results[0].filename == "01_compensacion_funcionario.md"
    assert {result.filename for result in results} == {path.name for path in examples_dir.glob("*.md")}


def test_search_finds_budget_transfer_by_content():
    examples_dir = Path(__file__).parents[1] / "examples"
    results = search_examples("trasposicion entre rubros presupuestales de contaduria", examples_dir, limit=1)
    assert results[0].filename == "02_trasposicion_rubros.md"


def test_lexical_support_rejects_unrelated_candidate():
    examples_dir = Path(__file__).parents[1] / "examples"
    candidates = search_examples("compensacion mensual por nuevas responsabilidades", examples_dir, limit=100)
    by_name = {candidate.filename: candidate for candidate in candidates}
    assert has_lexical_support(
        "compensacion mensual por nuevas responsabilidades", by_name["01_compensacion_funcionario.md"]
    )
    assert not has_lexical_support(
        "compensacion mensual por nuevas responsabilidades", by_name["02_trasposicion_rubros.md"]
    )


@pytest.mark.parametrize("query,filename", [
    ("Giana, quiero que me ayudes a crear una resolución para la contratación de un zafral para el área de parques y jardines.", "04_contratacion_zafral.md"),
    ("contratación de funcionario administrativo para cumplir funciones en una dependencia", "03_contratacion_funcionario.md"),
    ("contratar arrendamiento de obra con entregables", "05_arrendamiento_obra.md"),
    ("renovar contrato zafral por otro período", "07_renovacion_zafral.md"),
    ("llamado a concurso de oposición y méritos para vacantes", "06_llamado_concurso.md"),
    ("adjudicación de licitación de materiales eléctricos", "08_adjudicacion_licitacion.md"),
    ("aprobar convenio de cooperación interinstitucional", "09_aprobacion_convenio.md"),
    ("traslado interno de funcionario a otra dependencia", "10_traslado_funcionario.md"),
    ("exoneración de patente de rodados de un vehículo", "11_exoneracion_patente.md"),
])
def test_library_retrieves_relevant_model_first(query, filename):
    examples_dir = Path(__file__).parents[1] / "examples"
    candidate = search_examples(query, examples_dir, limit=1)[0]
    assert candidate.filename == filename
    assert has_lexical_support(query, candidate)
