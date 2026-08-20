from __future__ import annotations

import re
import unicodedata

FAMILY_BY_CATEGORY = {
    "decretos": "general",
    "ordenanzas": "general",
    "resoluciones": "resoluciones",
    "presupuestos": "presupuestos_departamentales",
    "instrumentos-territoriales": "ordenamiento_territorial",
    "estatutos": "estatuto_funcionario",
    "reglamentos": "general",
    "fuentes-indirectas": "general",
}

DIRECTORY_BY_TYPE = {
    "decreto": "decretos",
    "ordenanza": "ordenanzas",
    "resolucion": "resoluciones",
    "presupuesto": "presupuestos",
    "instrumento-territorial": "instrumentos-territoriales",
    "estatuto": "estatutos",
    "reglamento": "reglamentos",
}


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def type_slug(norm_type: str) -> str:
    key = strip_accents((norm_type or "").lower())
    if "ordenanza" in key:
        return "ordenanza"
    if "presupuesto" in key:
        return "presupuesto"
    if "resolucion" in key:
        return "resolucion"
    if "instrumento" in key or "directriz" in key or "ordenamiento territorial" in key:
        return "instrumento-territorial"
    if "estatuto" in key:
        return "estatuto"
    if "reglamento" in key:
        return "reglamento"
    if "decreto" in key:
        return "decreto"
    return "norma"


def directory_for_type(norm_type: str) -> str:
    return DIRECTORY_BY_TYPE.get(type_slug(norm_type), "decretos")


def _norm_number(norm_type: str, number: str, year: str | None) -> str:
    slug = type_slug(norm_type)
    if year and year.strip():
        return f"{slug}:{number}:{year.strip()}"
    return f"{slug}:{number}:unknown"


def build_norm_id(norm_type: str, number: str, year: str | None) -> str:
    return _norm_number(norm_type, number, year)


def deterministic_filename(norm_type: str, number: str, year: str | None) -> str:
    slug = type_slug(norm_type)
    num = re.sub(r"[^0-9]", "", number or "") or "sn"
    yr = year if year else "unknown"
    return f"{slug}_{num}_{yr}"


def family_for_norm(norm_type: str, family: str | None, directory: str | None) -> str:
    if family:
        return family
    if directory and directory in FAMILY_BY_CATEGORY:
        return FAMILY_BY_CATEGORY[directory]
    return FAMILY_BY_CATEGORY.get(type_slug(norm_type) + "s", "general")


def guess_number_year_from_text(text: str, norm_type: str) -> tuple[str | None, str | None]:
    """Heuristic, deterministic parsing of 'Decreto Nº 3842/023' or similar."""
    key = type_slug(norm_type)
    pat = re.compile(rf"{key}\s*(?:departamental\s*)?(?:n[º°o]?\.?)?\s*(\d{1,5})(?:[/\-])(\d{2,4})", re.IGNORECASE)
    m = pat.search(text or "")
    if not m:
        return None, None
    number = m.group(1).lstrip("0") or m.group(1)
    yy = m.group(2)
    year = "20" + yy if len(yy) == 2 and int(yy) < 50 else ("19" + yy if len(yy) == 2 else yy)
    return number, year