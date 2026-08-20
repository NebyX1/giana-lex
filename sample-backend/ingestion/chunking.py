from __future__ import annotations

import re
from typing import Any


LEGAL_HEADING = re.compile(
    r"(?im)^(?P<kind>t[ií]tulo|cap[ií]tulo|art[ií]culo|inciso|numeral|literal)"
    r"(?:\s+(?P<label>[A-Z0-9IVXLCDMº°.-]+))?[^\n]*$"
)


def fixed_chunks(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    clean = (text or "").strip()
    if not clean:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        if end < len(clean):
            boundary = max(clean.rfind("\n", start, end), clean.rfind(" ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary
        chunks.append(clean[start:end].strip())
        if end == len(clean):
            break
        start = end - overlap
    return [chunk for chunk in chunks if chunk]


def legal_chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[dict[str, Any]]:
    """Split on legal headings, preserving hierarchy and falling back for long sections."""
    clean = (text or "").strip()
    if not clean:
        return []
    matches = list(LEGAL_HEADING.finditer(clean))
    if not matches:
        return [
            {"text": chunk, "article": None, "legal_path": {}}
            for chunk in fixed_chunks(clean, chunk_size, overlap)
        ]

    hierarchy: dict[str, str] = {}
    result: list[dict[str, Any]] = []
    if matches[0].start() > 0:
        for part in fixed_chunks(clean[:matches[0].start()], chunk_size, overlap):
            result.append({"text": part, "article": None, "legal_path": {}})

    levels = ["titulo", "capitulo", "articulo", "inciso", "numeral", "literal"]
    for index, match in enumerate(matches):
        kind = match.group("kind").lower().translate(str.maketrans("í", "i"))
        heading = match.group(0).strip()
        level = levels.index(kind)
        for descendant in levels[level + 1:]:
            hierarchy.pop(descendant, None)
        hierarchy[kind] = heading
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
        section = clean[match.start():end].strip()
        article = hierarchy.get("articulo")
        for part in fixed_chunks(section, chunk_size, overlap):
            result.append({"text": part, "article": article, "legal_path": dict(hierarchy)})
    return result
