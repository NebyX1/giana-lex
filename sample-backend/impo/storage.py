from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import deterministic_filename, norm_dir_for_tipo
from .normalize import NormalizedNorma, build_plain_text


NACIONAL_ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "nacional"
REGISTRY_PATH = NACIONAL_ROOT / "registry.json"
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


def norma_dir(directory: str, filename: str) -> Path:
    return NACIONAL_ROOT / directory / filename


def persist_norma(
    directory: str,
    filename: str,
    *,
    source_json_bytes: bytes,
    normalized: NormalizedNorma,
    canonical_url: str,
    json_url: str,
    checksum: str,
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = norma_dir(directory, filename)
    target.mkdir(parents=True, exist_ok=True)

    source_path = target / "source.impo.json"
    normalized_path = target / "normalized.json"
    text_path = target / "normalized.txt"
    metadata_path = target / "metadata.json"

    _atomic_write_bytes(source_path, source_json_bytes)
    _atomic_write_json(normalized_path, normalized.to_dict())
    text_path.write_text(build_plain_text(normalized), encoding="utf-8")

    previous = existing_metadata or {}
    metadata = {
        "id": normalized.norma_id,
        "source": "IMPO",
        "tipo": normalized.tipo,
        "numero": normalized.numero,
        "anio": normalized.anio,
        "title": normalized.title,
        "nombre": normalized.nombre,
        "canonical_url": canonical_url,
        "json_url": json_url,
        "local_source_path": source_path.relative_to(NACIONAL_ROOT).as_posix(),
        "local_normalized_path": normalized_path.relative_to(NACIONAL_ROOT).as_posix(),
        "local_text_path": text_path.relative_to(NACIONAL_ROOT).as_posix(),
        "active": previous.get("active", True),
        "checksum": checksum,
        "downloaded_at": utc_now_iso(),
        "last_synced_at": utc_now_iso(),
        "index_status": previous.get("index_status", "downloaded"),
        "article_count": len(normalized.articulos),
        "chunk_count": previous.get("chunk_count", 0),
        "last_error": None,
        "search_terms": _build_search_terms(normalized),
    }
    _atomic_write_json(metadata_path, metadata)
    return metadata


def _build_search_terms(normalized: "NormalizedNorma") -> str:
    parts = [
        normalized.tipo,
        normalized.numero,
        str(normalized.anio),
        normalized.nombre,
        normalized.title,
    ]
    indexation = getattr(normalized, "indexacion", "") or ""
    vistos = getattr(normalized, "vistos", "") or ""
    if indexation:
        parts.append(indexation[:300])
    if vistos:
        parts.append(vistos[:300])
    for article in normalized.articulos[:40]:
        parts.append(article.title)
    parts.append(_KNOWN_ALIASES.get(normalized.norma_id, ""))
    return " ".join(part for part in parts if part)


# Descriptive aliases for well-known norms, to improve the plain-text searcher.
_KNOWN_ALIASES = {
    "ley:18381:2008": "transparencia acceso a la información pública",
    "decreto:500:1991": "procedimiento administrativo vista interesado",
    "ley:9515:1935": "ley orgánica municipal orgánica municipalidad",
    "decreto:150:2012": "tocaf texto ordenado contabilidad financiera administración financiera del estado",
    "decreto:232:2010": "rendición de cuentas balances auditoría",
    "ley:18308:2008": "ordenamiento territorial desarrollo sostenible",
    "ley:17930:2005": "tocaf texto ordenado de contabilidad y administración financiera",
}


def read_metadata(directory: str, filename: str) -> dict[str, Any] | None:
    path = norma_dir(directory, filename) / "metadata.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_file(directory: str, filename: str) -> str | None:
    path = norma_dir(directory, filename) / "normalized.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def delete_norma_files(directory: str, filename: str) -> None:
    target = norma_dir(directory, filename)
    if target.exists():
        for child in target.iterdir():
            child.unlink()
        target.rmdir()


def load_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_registry(registry: dict[str, dict[str, Any]]) -> None:
    with _LOCK:
        _atomic_write_json(REGISTRY_PATH, registry)


def upsert_registry_entry(metadata: dict[str, Any]) -> None:
    with _LOCK:
        registry = load_registry()
        registry[metadata["id"]] = metadata
        save_registry(registry)


def remove_registry_entry(norma_id: str) -> None:
    with _LOCK:
        registry = load_registry()
        registry.pop(norma_id, None)
        save_registry(registry)


def update_registry_entry(norma_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    with _LOCK:
        registry = load_registry()
        entry = registry.get(norma_id)
        if entry is None:
            return None
        entry.update(changes)
        registry[norma_id] = entry
        save_registry(registry)
        return entry


_NORMA_SLUG = re.compile(r"^(?P<tipo>[A-Za-z][A-Za-z-]+)[-_](?P<num>\d+)[-_](?P<anio>\d+)$")


def rebuild_registry_from_disk() -> int:
    registry: dict[str, dict[str, Any]] = {}
    for directory in ("constitucion", "decretos", "leyes", "reglamentos"):
        root = NACIONAL_ROOT / directory
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            metadata_path = child / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if "id" in metadata:
                    registry[metadata["id"]] = metadata
                    continue
    save_registry(registry)
    return len(registry)


def list_registry_entries(active_only: bool = False) -> list[dict[str, Any]]:
    registry = load_registry()
    entries = list(registry.values())
    if active_only:
        return [entry for entry in entries if entry.get("active")]
    return entries


def search_registry(query: str) -> list[dict[str, Any]]:
    registry = load_registry()
    query_norm = query.strip().lower()
    if not query_norm:
        return list(registry.values())
    terms = query_norm.split()
    results: list[dict[str, Any]] = []
    for entry in registry.values():
        haystack = " ".join(
            str(value)
            for key, value in entry.items()
            if key in ("id", "tipo", "numero", "anio", "title", "nombre", "canonical_url", "search_terms")
        ).lower()
        if all(term in haystack for term in terms):
            results.append(entry)
    return results


def filename_from_metadata(metadata: dict[str, Any]) -> str:
    return deterministic_filename(metadata.get("tipo", ""), metadata.get("numero", ""), metadata.get("anio", ""))


def directory_from_metadata(metadata: dict[str, Any]) -> str:
    return norm_dir_for_tipo(metadata.get("tipo", ""))