from __future__ import annotations

import re


REFERENCE_RE = re.compile(
    r"\b(?P<type>Ley|Decreto|Resoluci[oó]n|Disposici[oó]n|Ordenanza|C[oó]digo)"
    r"(?:\s+(?P<name>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,50}?))?"
    r"\s*(?:N(?:ro\.?|[º°o])?\s*)?(?P<number>\d[\w.-]*(?:/\d{2,4})?)\b",
    re.IGNORECASE,
)
ARTICLE_RE = re.compile(
    r"\bArt(?:[ií]culo|\.)\s*(?P<article>\d+[\w.-]*)"
    r"(?:\s+(?:de|del|de la)\s+(?P<reference>[^.;\n]{3,120}))?",
    re.IGNORECASE,
)


def extract_legal_references(text: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[tuple[str, int, int]] = set()
    for pattern, kind in ((REFERENCE_RE, "norma"), (ARTICLE_RE, "articulo")):
        for match in pattern.finditer(text):
            key = (match.group(0).casefold(), match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            groups = {name: value.strip() for name, value in match.groupdict().items() if value}
            found.append({
                "kind": kind,
                "text": match.group(0).strip(),
                "start": match.start(),
                "end": match.end(),
                "components": groups,
            })
    return sorted(found, key=lambda item: int(item["start"]))
