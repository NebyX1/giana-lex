from pathlib import Path

import pytest

from legal_knowledge.parser import LavallejaResolutionParser, validate_official_resolution_url


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("filename", "number", "summary_signal", "resolve_count"),
    [
        ("resolution_2826_026.html", "2.826/026", "trasposición", 3),
        ("resolution_2834_026.html", "2.834/026", "horas extras", 4),
        ("resolution_2827_026.html", "2.827/026", "Sabrina", 3),
        ("resolution_2825_026.html", "2.825/026", "Licitación", 3),
    ],
)
def test_parser_extracts_official_structure(filename, number, summary_signal, resolve_count):
    source = (FIXTURES / filename).read_text(encoding="utf-8")
    parsed = LavallejaResolutionParser().parse(
        f"https://www.gub.uy/intendencia-lavalleja/institucional/normativa/{filename}", source
    )
    assert parsed.resolution_number == number
    assert summary_signal in parsed.official_summary
    assert parsed.visto
    assert parsed.considerandos
    assert parsed.atento
    assert len(parsed.resuelve) == resolve_count


@pytest.mark.parametrize("url", [
    "http://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-1",
    "https://127.0.0.1/intendencia-lavalleja/institucional/normativa/resolucion-n-1",
    "file:///etc/passwd",
    "https://www.gub.uy/otro-organismo/normativa/resolucion-n-1",
])
def test_import_url_rejects_unsafe_sources(url):
    with pytest.raises(ValueError):
        validate_official_resolution_url(url)
