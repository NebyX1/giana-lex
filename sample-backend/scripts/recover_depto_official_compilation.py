"""Recover Decreto 994 from the Intendencia's official compiled statute PDF."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from depto.download import DEPT_UA, MAX_BYTES, DownloadedSource
from depto.extract import extract_official_compilation_section, extract_pdf_text
from depto.service import DeptoService


# The institution's legacy HTTPS listener is currently unavailable, while the
# same official server still serves this exact document over HTTP.  The URL is
# intentionally hard-coded; this is not a general-purpose insecure downloader.
SOURCE_URL = (
    "http://www.lavalleja.gub.uy/c/document_library/get_file?"
    "folderId=26946&name=DLFE-9801.pdf"
)


def _download_official_legacy_pdf() -> bytes:
    response = httpx.get(
        SOURCE_URL,
        headers={"User-Agent": DEPT_UA, "Accept": "application/pdf"},
        timeout=120,
        follow_redirects=True,
    )
    response.raise_for_status()
    raw = response.content
    if not raw.startswith(b"%PDF-"):
        raise RuntimeError("La fuente oficial del Decreto 994 no devolvió un PDF")
    if len(raw) > MAX_BYTES:
        raise RuntimeError("La fuente oficial del Decreto 994 excede el máximo permitido")
    return raw


def main() -> None:
    raw = _download_official_legacy_pdf()
    pdf = DownloadedSource(
        url=SOURCE_URL,
        final_url=SOURCE_URL,
        content_type="application/pdf",
        raw=raw,
        encoding=None,
    )
    compilation_text, _ = extract_pdf_text(pdf)
    statute_text = extract_official_compilation_section(
        compilation_text,
        "ESTATUTO DEL FUNCIONARIO MUNICIPAL",
        "DIGESTO DE TRANSITO",
    )
    source = DownloadedSource(
        url=SOURCE_URL,
        final_url=SOURCE_URL,
        content_type="text/plain; charset=utf-8",
        raw=statute_text.encode("utf-8"),
        encoding="utf-8",
    )
    result = DeptoService().importer._import_downloaded(
        source,
        norm_type="decreto",
        number="994",
        year="1982",
        family="estatuto_funcionario",
        title="Estatuto del Funcionario Municipal",
        source_quality="official_republication",
        active=True,
        index=True,
        evidence_url=SOURCE_URL,
        force=True,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
