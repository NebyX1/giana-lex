"""Idempotent seed importer for Lavalleja departmental norms.

Reads the manifest at backend/knowledge/departamental/manifests/lavalleja_seed_manifest.json,
downloads each available source, normalizes, stores and indexes it.
Registers indirect sources (original not found) as stubs without fake text.

Usage (from backend/):
    py -3.14 -m scripts.seed_lavalleja_departamental
    py -3.14 -m scripts.seed_lavalleja_departamental --delay 1.5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from depto.service import DeptoService, DepartmentalNormImporter
from depto.download import DownloadedSource, build_depto_client, download_source
from depto.extract import (
    extract_decree_from_official_minutes,
    extract_official_document_body,
    extract_official_compilation_section,
    extract_pdf_text,
)
from scripts.recover_depto_legacy_word import _convert_with_word
from scripts.recover_depto_official_compilation import _download_official_legacy_pdf

MANIFEST_PATH = BACKEND_ROOT / "knowledge" / "departamental" / "manifests" / "lavalleja_seed_manifest.json"
DEFAULT_DELAY = 1.2


def _prepare_special_source(entry: dict, client) -> DownloadedSource | None:
    """Prepare archive formats that cannot be safely imported as a whole."""
    url = entry["source_url"]
    if entry.get("extract_decree_from_acta"):
        acta = download_source(url, client=client)
        acta_text, _ = extract_pdf_text(acta)
        decree_text = extract_decree_from_official_minutes(acta_text, entry["number"])
        return DownloadedSource(
            url=url, final_url=acta.final_url,
            content_type="text/plain; charset=utf-8",
            raw=decree_text.encode("utf-8"), encoding="utf-8",
        )
    if entry.get("legacy_word"):
        document = download_source(url, client=client)
        text = _convert_with_word(document.raw).strip()
        return DownloadedSource(
            url=url, final_url=document.final_url,
            content_type="text/plain; charset=utf-8",
            raw=text.encode("utf-8"), encoding="utf-8",
        )
    body_start_pattern = entry.get("body_start_pattern")
    if body_start_pattern:
        document = download_source(url, client=client)
        full_text, _ = extract_pdf_text(document)
        text = extract_official_document_body(full_text, body_start_pattern)
        return DownloadedSource(
            url=url, final_url=document.final_url,
            content_type="text/plain; charset=utf-8",
            raw=text.encode("utf-8"), encoding="utf-8",
        )
    compilation = entry.get("official_compilation")
    if compilation:
        raw = _download_official_legacy_pdf()
        pdf = DownloadedSource(
            url=url, final_url=url, content_type="application/pdf", raw=raw, encoding=None
        )
        full_text, _ = extract_pdf_text(pdf)
        text = extract_official_compilation_section(
            full_text, compilation["heading"], compilation["following_heading"]
        )
        return DownloadedSource(
            url=url, final_url=url,
            content_type="text/plain; charset=utf-8",
            raw=text.encode("utf-8"), encoding="utf-8",
        )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Lavalleja departmental norms into Giana-Lex.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--no-index", action="store_true")
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"ERROR: manifest not found: {args.manifest}")
        sys.exit(1)

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    norms = data.get("norms", [])
    indirect = data.get("indirect_sources", [])
    print(f"Manifiesto: {args.manifest.name}")
    print(f"Normas con fuente: {len(norms)}  |  Fuentes indirectas: {len(indirect)}")
    print("-" * 70)

    client = build_depto_client()
    service = DeptoService(http_client=client)
    importer = DepartmentalNormImporter(http_client=client)

    results = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0, "indexed": 0}
    failures: list[tuple[str, str]] = []

    # Process direct sources
    for i, entry in enumerate(norms, 1):
        prefix = f"[{i}/{len(norms)}]"
        url = entry["source_url"]
        norm_id = entry["norm_id"]
        try:
            prepared = _prepare_special_source(entry, client)
            common = {
                "norm_type": entry["type"],
                "number": entry["number"],
                "year": str(entry["year"]) if entry.get("year") else None,
                "family": entry.get("family"),
                "title": entry.get("title"),
                "source_quality": entry.get("source_quality", "unknown"),
                "active": entry.get("active", True),
                "index": not args.no_index,
                "evidence_url": entry.get("evidence_url"),
            }
            if prepared is not None:
                result = importer._import_downloaded(prepared, **common)
            else:
                result = importer.import_source(url=url, **common)
            if result.status == "created":
                results["created"] += 1
            elif result.status == "updated":
                results["updated"] += 1
            elif result.status == "unchanged":
                results["unchanged"] += 1
            if result.chunk_count > 0:
                results["indexed"] += 1
            print(f"{prefix} OK {norm_id} -> {result.status} ({result.article_count} art, {result.chunk_count} chunks)")
        except Exception as exc:
            results["failed"] += 1
            failures.append((norm_id, str(exc)))
            print(f"{prefix} FAIL {norm_id} -> {exc}")
        if i < len(norms):
            time.sleep(args.delay)

    # Register indirect sources
    for entry in indirect:
        norm_id = entry["norm_id"]
        service.importer.import_indirect(
            norm_id=norm_id,
            norm_type=norm_id.split(":")[0],
            number=norm_id.split(":")[1],
            year=norm_id.split(":")[2] if norm_id.split(":")[2] != "unknown" else None,
            family=entry.get("family", "general"),
            evidence_urls=entry.get("evidence_urls", []),
            title=entry.get("title"),
        )
        print(f"INDIRECT {norm_id} registrado (texto original no localizado)")

    client.close()

    print("-" * 70)
    stats = service.get_stats()
    print("Resumen:")
    print(f"  Normas con fuente en manifiesto: {len(norms)}")
    print(f"  Creadas: {results['created']}")
    print(f"  Actualizadas: {results['updated']}")
    print(f"  Sin cambios: {results['unchanged']}")
    print(f"  Fallidas: {results['failed']}")
    print(f"  Indexadas: {results['indexed']}")
    print(f"  Fuentes indirectas registradas: {len(indirect)}")
    print(f"  Total en registro: {stats['total']}")
    print(f"  Con texto completo: {stats['with_text']}")
    print(f"  Solo referencia: {stats['only_reference']}")
    print(f"  Indexadas total: {stats['indexed']}")
    print(f"  Artículos: {stats['articles']}")
    print(f"  Chunks: {stats['chunks']}")
    print(f"  Relaciones: {stats['relations']}")
    if failures:
        print("-" * 70)
        print("Descargas fallidas:")
        for norm_id, reason in failures:
            print(f"  - {norm_id}: {reason}")
    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
