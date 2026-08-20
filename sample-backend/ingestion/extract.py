from __future__ import annotations

import io
from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def extract_text(path: Path) -> str:
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires the 'pypdf' package.") from exc
        reader = PdfReader(io.BytesIO(path.read_bytes()))
        return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    raise ValueError(f"Unsupported file type: {path.suffix}")
