from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .schemas import ParsedResolution


class ResolutionDocumentStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    def persist_original(self, resolution_id: str, parsed: ParsedResolution) -> dict:
        directory = self.root / resolution_id
        directory.mkdir(parents=True, exist_ok=True)
        source_path = directory / "source.html"
        normalized_path = directory / "normalized.md"
        metadata_path = directory / "metadata.json"
        if source_path.exists():
            existing = source_path.read_text(encoding="utf-8")
            if existing != parsed.source_html:
                source_path = directory / f"source-{parsed.source_hash[:12]}.html"
        if not source_path.exists():
            source_path.write_text(parsed.source_html, encoding="utf-8")
        normalized_path.write_text(parsed.normalized_text, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "resolution_id": resolution_id,
                    "resolution_number": parsed.resolution_number,
                    "source_url": parsed.source_url,
                    "source_hash": parsed.source_hash,
                    "publication_date": parsed.publication_date.isoformat() if parsed.publication_date else None,
                    "resolution_date": parsed.resolution_date.isoformat() if parsed.resolution_date else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "storage_path": str(source_path.relative_to(self.root.parent.parent.parent)),
            "byte_size": source_path.stat().st_size,
            "content_type": "text/html; charset=utf-8",
        }

    def persist_upload(self, resolution_id: str, filename: str, content: bytes) -> dict:
        extension = Path(filename).suffix.lower()
        directory = self.root / resolution_id
        directory.mkdir(parents=True, exist_ok=True)
        source_hash = hashlib.sha256(content).hexdigest()
        path = directory / f"upload-{source_hash[:12]}{extension}"
        if not path.exists():
            path.write_bytes(content)
        return {"storage_path": str(path), "byte_size": len(content), "source_hash": source_hash}
