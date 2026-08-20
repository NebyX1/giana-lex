from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


EXAMPLES_ROOT = Path(__file__).resolve().parent
RESOLUCIONES_ROOT = EXAMPLES_ROOT / "resoluciones"
SEARCHABLE_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
AUXILIARY_NAMES = {"README.MD", "GUIA_USO_AGENTE.MD", "MANIFEST.JSON"}
DEFAULT_AUTHORITY_LEVEL = "EXAMPLE"
SEARCH_STOP_WORDS = {
    "para", "como", "con", "del", "desde", "este", "esta", "las", "los", "por", "que", "una", "uno",
    "unos", "unas", "quiero", "redactar", "redacta", "redacte", "documento", "juridico", "jurídico",
}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (metadata, body). Metadata comes from YAML frontmatter when present."""
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        frontmatter, body = text[4:].split("\n---\n", 1)
        try:
            loaded = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError:
            return {}, text
        if isinstance(loaded, dict):
            return loaded, body
    return {}, text


def _metadata_string(metadata: dict[str, Any]) -> str:
    parts = [
        str(metadata.get("document_id", "")),
        str(metadata.get("typology", "")),
        str(metadata.get("document_type", "")),
        str(metadata.get("jurisdiction", "")),
    ]
    parts.extend(str(tag) for tag in (metadata.get("tags") or []) if isinstance(tag, str))
    return " ".join(parts)


def _load_example(path: Path, terms: set[str] | None = None) -> dict[str, object]:
    # utf-8-sig elimina cualquier BOM inicial (comun al editar archivos en Windows).
    raw_text = path.read_text(encoding="utf-8-sig", errors="replace")
    metadata, body = (
        _parse_frontmatter(raw_text) if path.suffix.lower() == ".md" else ({}, raw_text)
    )
    title = str(metadata.get("title") or path.stem)
    full_text = f"{title} {_metadata_string(metadata)} {body}"
    haystack = full_text.casefold()
    score = 0
    if terms:
        score = sum(haystack.count(term) for term in terms)
    return {
        "classification": "EXAMPLE",
        "authority_level": DEFAULT_AUTHORITY_LEVEL,
        "is_authority": False,
        "warning": "Ejemplo no vinculante: no constituye fuente ni autoridad juridica.",
        "path": str(path),
        "title": title,
        "document_id": metadata.get("document_id"),
        "typology": metadata.get("typology"),
        "document_type": metadata.get("document_type"),
        "jurisdiction": metadata.get("jurisdiction"),
        "tags": [tag for tag in (metadata.get("tags") or []) if isinstance(tag, str)],
        "score": score,
        "excerpt": re.sub(r"\s+", " ", body).strip()[:500],
        # Interno, no destinado al LLM: texto completo para ranking por tokens.
        "_full_text": full_text,
    }


def _token_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in re.findall(r"\w+", text.casefold()):
        if len(token) > 1:
            counts[token] = counts.get(token, 0) + 1
    return counts


def list_resolution_examples(
    root: str | Path = RESOLUCIONES_ROOT,
) -> list[dict[str, object]]:
    """Enumerate resolution examples with metadata, independent of any query."""
    root_path = Path(root).resolve(strict=True)
    examples = []
    for path in sorted(root_path.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        if path.name.upper() in AUXILIARY_NAMES:
            continue
        examples.append(_load_example(path))
    return examples


def _all_examples(root: str | Path) -> list[dict[str, object]]:
    root_path = Path(root).resolve(strict=True)
    examples = []
    for path in root_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SEARCHABLE_EXTENSIONS:
            continue
        if path.name.upper() in AUXILIARY_NAMES:
            continue
        examples.append(_load_example(path))
    return examples


def search_examples(query: str, root: str | Path = EXAMPLES_ROOT, limit: int = 10) -> list[dict[str, object]]:
    terms = {
        term.casefold()
        for term in re.findall(r"\w+", query)
        if len(term) > 2 and term.casefold() not in SEARCH_STOP_WORDS
    }
    if not terms or not 1 <= limit <= 50:
        return []

    examples = _all_examples(root)

    def _document_tokens(item: dict[str, object]) -> set[str]:
        tokens = set(_token_counts(str(item.get("_full_text", ""))))
        tokens.update(str(item.get("typology", "")).split("_"))
        tokens.update(tag for tag in item.get("tags", []) if isinstance(tag, str))
        return tokens

    doc_frequency: dict[str, int] = {}
    for item in examples:
        for token in _document_tokens(item):
            doc_frequency[token] = doc_frequency.get(token, 0) + 1

    scored = []
    for item in examples:
        tokens = _document_tokens(item)
        # IDF puro: un termino distintivo (raro) pesa mas que uno comun.
        relevance = sum(1.0 / max(doc_frequency.get(term, len(examples)), 1) for term in terms if term in tokens)
        if relevance > 0:
            public_item = {key: value for key, value in item.items() if not key.startswith("_")}
            scored.append({**public_item, "score": round(relevance, 4)})

    return sorted(scored, key=lambda item: (-float(item["score"]), str(item["path"])))[:limit]
