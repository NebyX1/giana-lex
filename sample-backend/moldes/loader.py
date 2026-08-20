from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from documents.parsers import DocumentParseError, normalize_text, resolve_safe_path


MOLDS_ROOT = Path(__file__).resolve().parent
DEFAULT_AUTHORITY_LEVEL = "TEMPLATE"


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


def load_mold(path: str | Path, root: str | Path = MOLDS_ROOT) -> dict[str, object]:
    root_path = Path(root).expanduser().resolve(strict=True)
    requested = Path(path).expanduser()
    resolved = resolve_safe_path(requested if requested.is_absolute() else root_path / requested, root_path)
    if resolved.suffix.lower() != ".md":
        raise DocumentParseError("Los moldes externos deben estar en formato Markdown (.md).")
    try:
        raw = resolved.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("El molde debe usar codificacion UTF-8.") from exc

    metadata, body = _parse_frontmatter(raw)
    name = str(metadata.get("name") or resolved.stem)
    # Files in this directory are generation constraints, never legal authority.
    authority_level = DEFAULT_AUTHORITY_LEVEL

    return {
        "name": name,
        "path": str(resolved),
        "format": "markdown",
        "editable": True,
        "authority_level": authority_level,
        "is_authority": False,
        "legal_status": "TEMPLATE",
        "document_type": metadata.get("document_type"),
        "subtype": metadata.get("subtype"),
        "jurisdiction": metadata.get("jurisdiction"),
        "variants": [v for v in (metadata.get("variants") or []) if isinstance(v, str)],
        "required_fields": [f for f in (metadata.get("required_fields") or []) if isinstance(f, str)],
        "conditional_fields": [f for f in (metadata.get("conditional_fields") or []) if isinstance(f, str)],
        "forbidden_inference": [f for f in (metadata.get("forbidden_inference") or []) if isinstance(f, str)],
        "content": normalize_text(body),
    }
