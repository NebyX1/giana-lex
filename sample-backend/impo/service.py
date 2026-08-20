from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.embeddings import Embedder, FastEmbedder
from rag.constants import NATIONAL_COLLECTION
from rag.store import QdrantStore, VectorStore

from .client import ImpoDownload, ImpoDownloadError, build_impo_client, download_norma
from .identity import build_norma_id, deterministic_filename, norm_dir_for_tipo
from .indexer import index_norma, set_norma_active_payload
from .normalize import normalize_impo_data, normalized_from_dict
from .storage import (
    NACIONAL_ROOT,
    filename_from_metadata,
    load_registry,
    persist_norma,
    read_metadata,
    update_registry_entry,
    upsert_registry_entry,
)
from .url import CanonicalUrl, normalize_impo_url


logger = logging.getLogger(__name__)


class ImpoImportResult:
    def __init__(
        self,
        *,
        status: str,
        norma_id: str | None = None,
        message: str,
        article_count: int = 0,
        chunk_count: int = 0,
        checksum: str | None = None,
        existing: bool = False,
        changed: bool = False,
    ):
        self.status = status
        self.norma_id = norma_id
        self.message = message
        self.article_count = article_count
        self.chunk_count = chunk_count
        self.checksum = checksum
        self.existing = existing
        self.changed = changed

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "norma_id": self.norma_id,
            "message": self.message,
            "article_count": self.article_count,
            "chunk_count": self.chunk_count,
            "checksum": self.checksum,
            "existing": self.existing,
            "changed": self.changed,
        }


class ImpoService:
    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        store: VectorStore | None = None,
        http_client=None,
    ):
        self.embedder = embedder or FastEmbedder()
        self.store = store or QdrantStore()
        self.http_client = http_client
        self._indexed_sources_cache: set[str] | None = None

    def _indexed_sources(self, *, refresh: bool = False) -> set[str]:
        if refresh or self._indexed_sources_cache is None:
            try:
                self._indexed_sources_cache = self.store.list_sources(NATIONAL_COLLECTION, "nacional")
            except Exception as exc:
                logger.warning("Qdrant unavailable while listing indexed national sources: %s", exc)
                self._indexed_sources_cache = set()
        return self._indexed_sources_cache

    def import_url(self, raw_url: str, *, index: bool = True) -> ImpoImportResult:
        canonical = normalize_impo_url(raw_url)
        logger.info("IMPO canonical URL: %s", canonical.canonical)
        return self._import_canonical(canonical, index=index)

    def _import_canonical(self, canonical: CanonicalUrl, *, index: bool) -> ImpoImportResult:
        download = download_norma(canonical, client=self.http_client)
        norma_id = build_norma_id(download.tipo, download.numero, download.anio)
        directory = norm_dir_for_tipo(download.tipo)
        filename = deterministic_filename(download.tipo, download.numero, download.anio)

        existing = read_metadata(directory, filename)
        existing_checksum = existing.get("checksum") if existing else None

        if existing_checksum and existing_checksum == download.checksum:
            logger.info("Sin cambios en %s", norma_id)
            if index:
                source_file = self._source_file(existing)
                indexed_sources = self._indexed_sources()
                if source_file not in indexed_sources:
                    chunks = self._reindex_local_entry(norma_id, existing)
                    return ImpoImportResult(
                        status="reindexed",
                        norma_id=norma_id,
                        message="La norma no tenía un índice utilizable y fue reparada desde la copia local.",
                        article_count=existing.get("article_count", 0),
                        chunk_count=chunks,
                        checksum=download.checksum,
                        existing=True,
                        changed=True,
                    )
            update_registry_entry(
                norma_id,
                {
                    "last_synced_at": datetime.now(timezone.utc).isoformat(),
                    "last_error": None,
                },
            )
            return ImpoImportResult(
                status="unchanged",
                norma_id=norma_id,
                message="Sin cambios. La norma ya estaba actualizada.",
                article_count=existing.get("article_count", 0) if existing else 0,
                checksum=download.checksum,
                existing=True,
                changed=False,
            )

        normalized = normalize_impo_data(
            download.data, canonical.canonical, canonical.json_url, norma_id
        )
        source_bytes = download.raw_bytes
        metadata = persist_norma(
            directory,
            filename,
            source_json_bytes=source_bytes,
            normalized=normalized,
            canonical_url=canonical.canonical,
            json_url=canonical.json_url,
            checksum=download.checksum,
            existing_metadata=existing,
        )

        chunk_count = 0
        index_status = "normalized"
        last_error = None
        if index:
            try:
                chunk_count = index_norma(
                    normalized,
                    embedder=self.embedder,
                    store=self.store,
                    active=metadata.get("active", True),
                    checksum=download.checksum,
                )
                index_status = "indexed"
            except Exception as exc:
                logger.exception("Error indexando norma %s", norma_id)
                last_error = str(exc)
                index_status = "downloaded"

        metadata.update(
            {
                "chunk_count": chunk_count,
                "index_status": index_status,
                "last_error": last_error,
            }
        )
        upsert_registry_entry(metadata)

        status = "updated" if existing else "created"
        message = (
            f"{normalized.tipo} Nº {normalized.numero} {'actualizada' if existing else 'descargada'} correctamente. "
            f"{len(normalized.articulos)} artículos. Norma {'indexada y ' if index_status == 'indexed' else ''}"
            f"{'activa' if metadata.get('active') else 'inactiva'}."
        )
        return ImpoImportResult(
            status=status,
            norma_id=norma_id,
            message=message,
            article_count=len(normalized.articulos),
            chunk_count=chunk_count,
            checksum=download.checksum,
            existing=bool(existing),
            changed=True,
        )

    @staticmethod
    def _source_file(entry: dict[str, Any]) -> str:
        local = str(entry.get("local_text_path") or "").replace("\\", "/")
        return f"nacional/{local}" if local and not local.startswith("nacional/") else local

    def _reindex_local_entry(self, norma_id: str, entry: dict[str, Any]) -> int:
        relative = str(entry.get("local_normalized_path") or "")
        path = (NACIONAL_ROOT / relative).resolve()
        root = NACIONAL_ROOT.resolve()
        if root not in path.parents or not path.is_file():
            raise FileNotFoundError(f"No existe la copia normalizada local de {norma_id}.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalized_from_dict(payload)
        if normalized.norma_id != norma_id:
            raise ValueError(f"La copia local no corresponde a {norma_id}.")
        count = index_norma(
            normalized,
            embedder=self.embedder,
            store=self.store,
            active=bool(entry.get("active", True)),
            checksum=str(entry.get("checksum") or "local"),
        )
        update_registry_entry(
            norma_id,
            {"index_status": "indexed", "chunk_count": count, "last_error": None},
        )
        return count

    def repair_index(self, *, missing_only: bool = True) -> dict[str, Any]:
        """Rebuild missing Qdrant sources from durable normalized files."""
        registry = load_registry()
        indexed_sources = self._indexed_sources()
        repaired = 0
        failed = 0
        chunks = 0
        for norma_id, entry in registry.items():
            if missing_only and self._source_file(entry) in indexed_sources:
                continue
            try:
                chunks += self._reindex_local_entry(norma_id, entry)
                repaired += 1
            except Exception as exc:
                failed += 1
                update_registry_entry(
                    norma_id,
                    {"index_status": "downloaded", "last_error": str(exc)},
                )
                logger.exception("No se pudo reparar el índice de %s", norma_id)
        available = len(self._indexed_sources(refresh=True))
        return {
            "records": len(registry),
            "repaired": repaired,
            "failed": failed,
            "chunks": chunks,
            "available_sources": available,
        }

    def refresh_norma(self, norma_id: str) -> ImpoImportResult:
        registry = load_registry()
        entry = registry.get(norma_id)
        if not entry:
            return ImpoImportResult(status="not_found", message="Norma no encontrada en el registro.", norma_id=norma_id)
        canonical = normalize_impo_url(entry["canonical_url"])
        return self._import_canonical(canonical, index=True)

    def activate_norma(self, norma_id: str) -> ImpoImportResult:
        registry = load_registry()
        entry = registry.get(norma_id)
        if not entry:
            return ImpoImportResult(status="not_found", message="Norma no encontrada.", norma_id=norma_id)
        active = bool(entry.get("active"))
        if active:
            return ImpoImportResult(status="ok", norma_id=norma_id, message="La norma ya estaba activa.")
        try:
            set_norma_active_payload(norma_id, active=True, store=self.store)
        except Exception as exc:
            logger.warning("No se pudo actualizar payload en Qdrant para %s: %s", norma_id, exc)
        update_registry_entry(norma_id, {"active": True, "last_error": None})
        logger.info("Norma activada: %s", norma_id)
        return ImpoImportResult(status="activated", norma_id=norma_id, message="Norma activada y disponible para Giana.")

    def deactivate_norma(self, norma_id: str) -> ImpoImportResult:
        registry = load_registry()
        entry = registry.get(norma_id)
        if not entry:
            return ImpoImportResult(status="not_found", message="Norma no encontrada.", norma_id=norma_id)
        if not entry.get("active"):
            return ImpoImportResult(status="ok", norma_id=norma_id, message="La norma ya estaba inactiva.")
        try:
            set_norma_active_payload(norma_id, active=False, store=self.store)
        except Exception as exc:
            logger.warning("No se pudo actualizar payload en Qdrant para %s: %s", norma_id, exc)
        update_registry_entry(norma_id, {"active": False, "last_error": None})
        logger.info("Norma desactivada: %s", norma_id)
        return ImpoImportResult(status="deactivated", norma_id=norma_id, message="Norma desactivada. Excluida del RAG.")

    def list_norms(self, query: str | None = None) -> list[dict[str, Any]]:
        from .storage import search_registry

        if query:
            entries = search_registry(query)
        else:
            from .storage import list_registry_entries

            entries = list_registry_entries()
        indexed_sources = self._indexed_sources()
        results = []
        for value in entries:
            entry = dict(value)
            entry["index_available"] = self._source_file(entry) in indexed_sources
            if not entry["index_available"] and entry.get("index_status") == "indexed":
                entry["index_status"] = "missing"
            results.append(entry)
        return results

    def get_stats(self) -> dict[str, Any]:
        registry = load_registry()
        total = len(registry)
        active = sum(1 for entry in registry.values() if entry.get("active"))
        indexed_sources = self._indexed_sources()
        indexed = sum(1 for entry in registry.values() if self._source_file(entry) in indexed_sources)
        articles = sum(entry.get("article_count", 0) for entry in registry.values())
        chunks = sum(entry.get("chunk_count", 0) for entry in registry.values())
        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "indexed": indexed,
            "missing_index": total - indexed,
            "articles": articles,
            "chunks": chunks,
        }


def get_default_service() -> ImpoService:
    return ImpoService()
