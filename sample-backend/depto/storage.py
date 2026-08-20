from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import deterministic_filename, directory_for_type

DEPARTAMENTAL_ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "departamental"
REGISTRY_PATH = DEPARTAMENTAL_ROOT / "registry.json"
RELATIONSHIPS_PATH = DEPARTAMENTAL_ROOT / "relationships.json"
_LOCK = threading.RLock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _atomic_write_json(path: Path, data: Any) -> None:
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    _atomic_write_bytes(path, raw)


def norm_dir(directory: str, filename: str) -> Path:
    return DEPARTAMENTAL_ROOT / directory / filename


def write_norma_files(
    directory: str,
    filename: str,
    *,
    source_html: bytes | None,
    source_pdf: bytes | None,
    source_txt: str | None,
    normalized: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    target = norm_dir(directory, filename)
    target.mkdir(parents=True, exist_ok=True)
    if source_html is not None:
        _atomic_write_bytes(target / "source.html", source_html)
    if source_pdf is not None:
        _atomic_write_bytes(target / "source.pdf", source_pdf)
    if source_txt is not None:
        _atomic_write_bytes(target / "source.txt", source_txt.encode("utf-8"))
    _atomic_write_json(target / "normalized.json", normalized)
    _atomic_write_json(target / "metadata.json", metadata)


def write_evidence(directory: str, filename: str, evidence: dict[str, Any]) -> None:
    target = norm_dir(directory, filename)
    target.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target / "evidence.json", evidence)


def write_metadata(directory: str, filename: str, metadata: dict[str, Any]) -> None:
    target = norm_dir(directory, filename)
    target.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target / "metadata.json", metadata)


def write_stub(directory: str, filename: str, metadata: dict[str, Any], evidence: dict[str, Any]) -> None:
    target = norm_dir(directory, filename)
    target.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(target / "metadata.json", metadata)
    _atomic_write_json(target / "evidence.json", evidence)


def load_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(registry: dict[str, dict[str, Any]]) -> None:
    with _LOCK:
        _atomic_write_json(REGISTRY_PATH, registry)


def upsert_registry_entry(metadata: dict[str, Any]) -> None:
    with _LOCK:
        registry = load_registry()
        registry[metadata["id"]] = metadata
        save_registry(registry)


def update_registry_entry(norm_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    with _LOCK:
        registry = load_registry()
        entry = registry.get(norm_id)
        if entry is None:
            return None
        entry.update(changes)
        registry[norm_id] = entry
        save_registry(registry)
        return entry


def list_registry_entries() -> list[dict[str, Any]]:
    return list(load_registry().values())


def search_registry(query: str) -> list[dict[str, Any]]:
    registry = load_registry()
    q = (query or "").strip().lower()
    if not q:
        return list(registry.values())
    terms = q.split()
    results = []
    for entry in registry.values():
        haystack = " ".join(
            str(value) for key, value in entry.items()
            if key in ("id", "type", "number", "year", "title", "family", "search_terms", "norm_id")
        ).lower()
        if all(t in haystack for t in terms):
            results.append(entry)
    return results


# --- Relationships ---


def load_relationships() -> list[dict[str, Any]]:
    if not RELATIONSHIPS_PATH.exists():
        return []
    try:
        data = json.loads(RELATIONSHIPS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_relationships(relations: list[dict[str, Any]]) -> None:
    with _LOCK:
        _atomic_write_json(RELATIONSHIPS_PATH, relations)


def add_relationship(relation: dict[str, Any]) -> bool:
    """Add a relation if not already present (by from/relation/to). Returns True if added."""
    with _LOCK:
        relations = load_relationships()
        key = (relation.get("from"), relation.get("relation"), relation.get("to"))
        for existing in relations:
            if (existing.get("from"), existing.get("relation"), existing.get("to")) == key:
                return False
        relations.append(relation)
        save_relationships(relations)
        return True


def relationships_for(norm_id: str, relation: str | None = None) -> list[dict[str, Any]]:
    relations = load_relationships()
    result = []
    for rel in relations:
        if rel.get("from") != norm_id and rel.get("to") != norm_id:
            continue
        if relation and rel.get("relation") != relation:
            continue
        result.append(rel)
    return result


def modifiying_norms_for_article(norm_id: str, article: str) -> list[dict[str, Any]]:
    """Return relationships where another norm modifies a specific article of norm_id."""
    relations = load_relationships()
    result = []
    for rel in relations:
        if rel.get("relation") in ("MODIFIES", "MODIFIED_BY") and rel.get("to") == norm_id:
            target_art = rel.get("target_article")
            if target_art is None or str(target_art) == str(article):
                result.append(rel)
        if rel.get("relation") == "MODIFIES_ARTICLE" and rel.get("target_norm") == norm_id:
            target_art = rel.get("target_article")
            if target_art is None or str(target_art) == str(article):
                result.append(rel)
    return result


def build_relationship_graph() -> dict[str, Any]:
    relations = load_relationships()
    graph: dict[str, Any] = {}
    for rel in relations:
        frm = rel.get("from")
        to = rel.get("to")
        graph.setdefault(frm, []).append(rel)
        graph.setdefault(to, []).append(rel)
    return graph


def count_relationships() -> int:
    return len(load_relationships())
