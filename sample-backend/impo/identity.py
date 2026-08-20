from __future__ import annotations

import re
import unicodedata

from .url import slug_from_canonical


_ACCENTS = {
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
    "Á": "a", "É": "e", "Í": "i", "Ó": "o", "Ú": "u", "Ñ": "n",
}


def _strip_accents(text: str) -> str:
    return "".join(_ACCENTS.get(ch, ch) for ch in text)


def build_norma_id(tipo: str, numero: str, anio: str) -> str:
    tipo_slug = _tipo_slug(tipo)
    if not numero or not anio:
        if "constitucion" in _strip_accents(tipo.lower()):
            return "constitucion:1967:1967"
        return f"{tipo_slug}:{numero or 's/n'}:{anio or 's/a'}"
    return f"{tipo_slug}:{numero}:{anio}"


_TIPO_SLUGS = [
    ("codigo", "codigo"),
    ("decreto ley", "decreto-ley"),
    ("decreto-ley", "decreto-ley"),
    ("decretoley", "decreto-ley"),
    ("decreto", "decreto"),
    ("reglamento", "reglamento"),
    ("constitucion", "constitucion"),
    ("ley", "ley"),
]


def _tipo_slug(tipo: str) -> str:
    key = _strip_accents(tipo.strip().lower())
    if "codigo" in key:
        slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
        return slug or "codigo"
    for needle, slug in _TIPO_SLUGS:
        if needle in key:
            return slug
    clean = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    return clean or "norma"


def norm_category_for_tipo(tipo: str) -> str:
    key = _strip_accents(tipo.strip().lower())
    if "constitucion" in key:
        return "constitucion"
    if "codigo" in key:
        return "leyes"
    if "reglamento" in key:
        return "reglamentos"
    if "decreto ley" in key or "decreto-ley" in key or "decretoley" in key:
        return "leyes"
    if "decreto" in key:
        return "decretos"
    if "ley" in key:
        return "leyes"
    return "leyes"


def norm_dir_for_tipo(tipo: str) -> str:
    return norm_category_for_tipo(tipo)


def deterministic_filename(tipo: str, numero: str, anio: str) -> str:
    if not numero or not anio:
        if "constitucion" in _strip_accents(tipo.lower()):
            return "constitucion_1967_1967"
    return f"{_tipo_slug(tipo)}_{numero or 'sn'}_{anio or 'sa'}"


def norma_id_from_canonical(canonical_url: str, tipo: str, numero: str, anio: str) -> str:
    return build_norma_id(tipo, numero, anio)


def id_from_slug(slug: str) -> str:
    return slug.replace("-", ":", 1).replace("-", ":", 1) if "-" in slug else slug