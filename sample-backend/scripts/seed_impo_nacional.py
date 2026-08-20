"""Idempotent seed importer for IMPO national norms.

Reads the manifest at backend/knowledge/nacional/impo_seed_manifest.json,
downloads each norma from IMPO, normalizes, stores and indexes it.
Continues on individual failures and prints a summary at the end.

Usage (from backend/):
    py -3.14 -m scripts.seed_impo_nacional
    py -3.14 -m scripts.seed_impo_nacional --manifest path/to/manifest.json
    py -3.14 -m scripts.seed_impo_nacional --delay 2.0
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from impo.client import ImpoDownloadError, build_impo_client
from impo.service import ImpoService
from impo.storage import load_registry
from impo.url import ImpoUrlError


MANIFEST_PATH = BACKEND_ROOT / "knowledge" / "nacional" / "impo_seed_manifest.json"
DEFAULT_DELAY = 1.5


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed IMPO national norms into Giana-Lex.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--no-index", action="store_true", help="Download only, skip Qdrant indexing.")
    args = parser.parse_args()

    manifest_path: Path = args.manifest
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}")
        sys.exit(1)

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    total = len(entries)
    print(f"Manifest: {manifest_path.name}")
    print(f"Normas del manifiesto: {total}")
    print("-" * 60)

    registry_before = load_registry()
    existing_ids = set(registry_before.keys())

    results = {
        "existing": 0,
        "downloaded": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
        "indexed": 0,
    }
    failed_urls: list[tuple[str, str]] = []

    http_client = build_impo_client()
    service = ImpoService(http_client=http_client)
    if args.no_index:
        service = ImpoService(http_client=http_client)
        service.embedder = None  # type: ignore[assignment]

    for index, entry in enumerate(entries, 1):
        url = entry["url"]
        prefix = f"[{index}/{total}]"
        try:
            if args.no_index:
                result = service.import_url(url, index=False)
            else:
                result = service.import_url(url, index=True)
            status = result.status
            if status == "created":
                results["downloaded"] += 1
            elif status == "updated":
                results["updated"] += 1
            elif status == "unchanged":
                results["unchanged"] += 1
            elif status in ("ok", "activated"):
                results["existing"] += 1
            if result.chunk_count and result.chunk_count > 0:
                results["indexed"] += 1
            symbol = "OK" if status != "failed" else "FAIL"
            print(f"{prefix} {symbol} {url} -> {status} ({result.article_count} art, {result.chunk_count} chunks)")
        except ImpoUrlError as exc:
            results["failed"] += 1
            failed_urls.append((url, f"URL invalida: {exc}"))
            print(f"{prefix} FAIL {url} -> URL invalida: {exc}")
        except ImpoDownloadError as exc:
            results["failed"] += 1
            failed_urls.append((url, f"descarga: {exc}"))
            print(f"{prefix} FAIL {url} -> descarga: {exc}")
        except Exception as exc:
            results["failed"] += 1
            failed_urls.append((url, f"error: {exc}"))
            print(f"{prefix} FAIL {url} -> error: {exc}")
        if index < total:
            time.sleep(args.delay)

    http_client.close()

    print("-" * 60)
    registry_after = load_registry()
    new_count = len(set(registry_after.keys()) - existing_ids)
    print("Resumen:")
    print(f"  Normas del manifiesto: {total}")
    print(f"  Ya existentes: {results['existing']}")
    print(f"  Descargadas (nuevas): {new_count}")
    print(f"  Actualizadas: {results['updated']}")
    print(f"  Sin cambios: {results['unchanged']}")
    print(f"  Fallidas: {results['failed']}")
    print(f"  Indexadas: {results['indexed']}")
    print(f"  Total en registro: {len(registry_after)}")
    if failed_urls:
        print("-" * 60)
        print("URLs IMPO fallidas:")
        for url, reason in failed_urls:
            print(f"  - {url}")
            print(f"    {reason}")
    print("-" * 60)
    stats = service.get_stats()
    print(
        f"Articulos totales: {stats['articles']}  "
        f"Chunks totales: {stats['chunks']}  "
        f"Activas: {stats['active']}/{stats['total']}"
    )

    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()