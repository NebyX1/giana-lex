from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .extract import SUPPORTED_EXTENSIONS, extract_text


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1] / "knowledge"
CORPUS_DIRECTORIES = {
    "departamental": KNOWLEDGE_ROOT / "departamental",
    "nacional": KNOWLEDGE_ROOT / "nacional",
}


def _inferred_metadata(path: Path, corpus: str, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    parts = Path(relative).parts
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    years = re.findall(r"\b(?:19|20)\d{2}\b", stem)
    number = re.search(r"\b\d+(?:[./-]\d+)*\b", stem)
    return {
        "corpus": corpus,
        "category": parts[0] if len(parts) > 1 else "general",
        "document_type": parts[1] if len(parts) > 2 else (parts[0] if len(parts) > 1 else "documento"),
        "title": stem,
        "number": number.group(0) if number else None,
        "year": int(years[-1]) if years else None,
        "source_url": None,
        "active": True,
        "norma_id": None,
    }


_IMPO_METADATA_FIELDS = {
    "title", "number", "year", "source_url", "active", "norma_id",
    "category", "document_type",
}

_IMPO_METADATA_ALIASES = {
    "id": "norma_id",
    "canonical_url": "source_url",
    "tipo": "document_type",
    "numero": "number",
    "anio": "year",
    "nombre": "title",
    "norma_id": "norma_id",
}


def _merge_impo_metadata(path: Path, metadata: dict[str, Any]) -> None:
    parent_metadata = path.parent / "metadata.json"
    if not parent_metadata.exists():
        return
    try:
        custom = json.loads(parent_metadata.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for key, value in custom.items():
        target = _IMPO_METADATA_ALIASES.get(key, key)
        if target in _IMPO_METADATA_FIELDS:
            metadata[target] = value


def load_documents(knowledge_root: Path = KNOWLEDGE_ROOT) -> list[dict[str, Any]]:
    documents = []
    for corpus in sorted(CORPUS_DIRECTORIES):
        corpus_root = knowledge_root / corpus
        if not corpus_root.exists():
            continue
        for path in sorted(corpus_root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            data = path.read_bytes()
            text = extract_text(path)
            if not text:
                continue
            metadata = _inferred_metadata(path, corpus, corpus_root)
            sidecar = path.with_suffix(path.suffix + ".json")
            if sidecar.exists():
                custom = json.loads(sidecar.read_text(encoding="utf-8"))
                metadata.update({key: value for key, value in custom.items() if key in metadata})
            _merge_impo_metadata(path, metadata)
            source_file = path.relative_to(knowledge_root).as_posix()
            documents.append({
                "text": text,
                "source_file": source_file,
                "source_hash": hashlib.sha256(data).hexdigest(),
                "metadata": metadata,
            })
    return documents
