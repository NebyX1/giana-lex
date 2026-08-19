from pathlib import Path

from tools.search_examples import has_lexical_support, search_examples


def test_search_examples_reads_real_files_dynamically():
    examples_dir = Path(__file__).parents[1] / "examples"
    results = search_examples("compensacion mensual para un funcionario", examples_dir, limit=3)

    assert results
    assert results[0].filename == "01_compensacion_funcionario.md"
    assert {result.filename for result in results} == {path.name for path in examples_dir.glob("*.md")}


def test_search_finds_budget_transfer_by_content():
    examples_dir = Path(__file__).parents[1] / "examples"
    results = search_examples("trasposicion entre rubros presupuestales de contaduria", examples_dir, limit=1)
    assert results[0].filename == "02_trasposicion_rubros.md"


def test_lexical_support_rejects_unrelated_candidate():
    examples_dir = Path(__file__).parents[1] / "examples"
    candidates = search_examples("compensacion mensual por nuevas responsabilidades", examples_dir, limit=2)
    by_name = {candidate.filename: candidate for candidate in candidates}
    assert has_lexical_support(
        "compensacion mensual por nuevas responsabilidades", by_name["01_compensacion_funcionario.md"]
    )
    assert not has_lexical_support(
        "compensacion mensual por nuevas responsabilidades", by_name["02_trasposicion_rubros.md"]
    )
