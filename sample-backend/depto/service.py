from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag.embeddings import Embedder, FastEmbedder
from rag.store import QdrantStore, VectorStore

from . import storage as st
from .download import DownloadedSource, DeptoDownloadError, build_depto_client, download_source
from .extract import extract_text_from_source
from .identity import build_norm_id, deterministic_filename, directory_for_type, family_for_norm, type_slug
from .normalize import detect_articles, detect_relations, strip_html

logger = logging.getLogger(__name__)
EXTRACTION_VERSION = 2


@dataclass
class DeptoImportResult:
    status: str
    norm_id: str | None = None
    message: str = ""
    article_count: int = 0
    chunk_count: int = 0
    text_available: bool = False
    source_quality: str = ""
    changed: bool = False
    existing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "norm_id": self.norm_id,
            "message": self.message,
            "article_count": self.article_count,
            "chunk_count": self.chunk_count,
            "text_available": self.text_available,
            "source_quality": self.source_quality,
            "changed": self.changed,
            "existing": self.existing,
        }


class DepartmentalNormImporter:
    def __init__(self, *, embedder: Embedder | None = None, store: VectorStore | None = None, http_client=None):
        self.embedder = embedder or FastEmbedder()
        self.store = store or QdrantStore()
        self.http_client = http_client

    def import_source(
        self,
        *,
        url: str,
        norm_type: str | None = None,
        number: str | None = None,
        year: str | None = None,
        family: str | None = None,
        title: str | None = None,
        source_quality: str = "unknown",
        active: bool = True,
        index: bool = True,
        evidence_url: str | None = None,
    ) -> DeptoImportResult:
        try:
            source = download_source(url, client=self.http_client)
        except DeptoDownloadError as exc:
            return DeptoImportResult(status="failed", message=f"Descarga fallida: {exc}")
        return self._import_downloaded(
            source,
            norm_type=norm_type,
            number=number,
            year=year,
            family=family,
            title=title,
            source_quality=source_quality,
            active=active,
            index=index,
            evidence_url=evidence_url,
        )

    def _import_downloaded(
        self,
        source: DownloadedSource,
        *,
        norm_type: str | None,
        number: str | None,
        year: str | None,
        family: str | None,
        title: str | None,
        source_quality: str,
        active: bool,
        index: bool,
        evidence_url: str | None,
        force: bool = False,
    ) -> DeptoImportResult:
        text, method = extract_text_from_source(source)
        # Heuristic parse of number/year/title from text if not provided.
        if not number or not year:
            from .identity import guess_number_year_from_text
            g_number, g_year = guess_number_year_from_text(text, norm_type or "decreto")
            number = number or g_number
            year = year or g_year
        if not title:
            title = _infer_title(text) or f"{norm_type or 'Norma'} {number or ''}"
        norm_type_resolved = norm_type or "decreto"
        directory = directory_for_type(norm_type_resolved)
        filename = deterministic_filename(norm_type_resolved, number or "sn", year)
        norm_id = build_norm_id(norm_type_resolved, number or "sn", year)
        family_resolved = family_for_norm(norm_type_resolved, family, directory)

        checksum = hashlib.sha256(source.raw).hexdigest()
        existing = st.load_registry().get(norm_id)
        if (
            existing
            and existing.get("checksum") == checksum
            and existing.get("extraction_version") == EXTRACTION_VERSION
            and not force
        ):
            return DeptoImportResult(
                status="unchanged", norm_id=norm_id,
                message="Sin cambios. La norma ya estaba actualizada.",
                text_available=bool(existing.get("text_available")),
                source_quality=existing.get("source_quality", source_quality),
                existing=True, changed=False,
            )

        articles = detect_articles(text)
        relations = detect_relations(text, norm_id, evidence=evidence_url or source.url)
        usable_text = _has_usable_text(text, articles)
        processing_state = "ready" if usable_text else (
            "ocr_required" if source.is_pdf else "source_without_usable_text"
        )

        normalized = {
            "norm_id": norm_id,
            "norm_type": norm_type_resolved,
            "number": number,
            "year": year,
            "title": title,
            "directory": directory,
            "family": family_resolved,
            "article_count": len(articles),
            "articles": [{"number": a.number, "bis": a.bis, "title": a.title, "text": a.text, "label": a.label} for a in articles],
            "relations": relations,
        }

        previous = existing or {}
        alternate_sources = list(previous.get("alternate_sources", []))
        previous_canonical = previous.get("canonical_source")
        if previous_canonical and previous_canonical != source.url and previous_canonical not in alternate_sources:
            alternate_sources.append(previous_canonical)

        metadata = {
            "id": norm_id,
            "norm_id": norm_id,
            "jurisdiction": "UY-LA",
            "scope": "departamental",
            "department": "Lavalleja",
            "type": norm_type_resolved,
            "number": number,
            "year": int(year) if year and year.isdigit() else None,
            "title": title,
            "status": previous.get("status", "active"),
            "text_available": usable_text,
            "source_quality": source_quality,
            "canonical_source": source.url,
            "alternate_sources": alternate_sources,
            "active_for_rag": active if usable_text else False,
            "downloaded": True,
            "normalized": True,
            "indexed": previous.get("indexed", False),
            "checksum": checksum,
            "downloaded_at": st.utc_now_iso(),
            "last_synced_at": st.utc_now_iso(),
            "article_count": len(articles),
            "chunk_count": previous.get("chunk_count", 0),
            "normative_family": family_resolved,
            "modifies": [],
            "modified_by": [],
            "derogates": [],
            "derogated_by": [],
            "restores": [],
            "interprets": [],
            "incorporates_national_norms": [],
            "evidence_sources": [evidence_url] if evidence_url else [],
            "extraction_method": method,
            "extraction_version": EXTRACTION_VERSION,
            "processing_state": processing_state,
            "search_terms": _build_search_terms(normalized),
            "last_error": None,
        }

        source_html = source.raw if source.is_html else None
        source_pdf = source.raw if source.is_pdf else None
        source_txt = text if text else None

        st.write_norma_files(
            directory, filename,
            source_html=source_html, source_pdf=source_pdf,
            source_txt=source_txt, normalized=normalized, metadata=metadata,
        )
        for rel in relations:
            st.add_relationship(rel)

        chunk_count = 0
        if index and usable_text and active:
            try:
                chunk_count = self._index_norm(norm_id, normalized, checksum, active=True, directory=directory, filename=filename, text=text)
                metadata["indexed"] = True
                metadata["chunk_count"] = chunk_count
                metadata["active_for_rag"] = True
            except Exception as exc:
                logger.exception("Error indexando norma %s", norm_id)
                metadata["last_error"] = str(exc)
                metadata["indexed"] = False
                metadata["active_for_rag"] = False

        # Persist the post-indexing state to both sources of truth. Previously
        # metadata.json retained indexed=False/chunk_count=0 while registry.json
        # contained the successful indexing result.
        st.write_metadata(directory, filename, metadata)
        st.upsert_registry_entry(metadata)
        status = "updated" if existing else "created"
        return DeptoImportResult(
            status=status, norm_id=norm_id,
            message=(
                f"{norm_type_resolved.title()} {number} "
                f"{'actualizado' if existing else 'incorporado'} ({len(articles)} artículos)."
                if usable_text else
                f"{norm_type_resolved.title()} {number} guardado, pero el archivo requiere OCR antes de poder consultarse."
            ),
            article_count=len(articles), chunk_count=chunk_count,
            text_available=metadata["text_available"], source_quality=source_quality,
            existing=bool(existing), changed=True,
        )

    def import_indirect(
        self,
        *,
        norm_id: str,
        norm_type: str,
        number: str,
        year: str | None,
        family: str,
        evidence_urls: list[str],
        title: str | None = None,
    ) -> DeptoImportResult:
        """Register a norm whose original text was not located (e.g. Decreto 524/977)."""
        directory = directory_for_type(norm_type)
        filename = deterministic_filename(norm_type, number, year)
        metadata = {
            "id": norm_id,
            "norm_id": norm_id,
            "jurisdiction": "UY-LA",
            "scope": "departamental",
            "department": "Lavalleja",
            "type": norm_type,
            "number": number,
            "year": int(year) if year and year.isdigit() else None,
            "title": title or f"{norm_type} {number}",
            "status": "active",
            "text_available": False,
            "source_quality": "official_indirect_reference",
            "canonical_source": evidence_urls[0] if evidence_urls else "",
            "alternate_sources": evidence_urls,
            "active_for_rag": False,
            "downloaded": False,
            "normalized": False,
            "indexed": False,
            "checksum": "",
            "downloaded_at": st.utc_now_iso(),
            "last_synced_at": st.utc_now_iso(),
            "article_count": 0,
            "chunk_count": 0,
            "normative_family": family,
            "modifies": [],
            "modified_by": [],
            "derogates": [],
            "derogated_by": [],
            "restores": [],
            "interprets": [],
            "incorporates_national_norms": [],
            "evidence_sources": evidence_urls,
            "original_found": False,
            "existence_confirmed": True,
            "last_error": None,
            "processing_state": "reference_only",
            "extraction_version": EXTRACTION_VERSION,
        }
        evidence = {
            "norm_id": norm_id,
            "status": "original_not_found",
            "text_available": False,
            "existence_confirmed": True,
            "evidence_urls": evidence_urls,
        }
        st.write_stub(directory, filename, metadata, evidence)
        st.upsert_registry_entry(metadata)
        return DeptoImportResult(
            status="indirect", norm_id=norm_id,
            message=f"{norm_type} {number} registrado como fuente indirecta (texto original no localizado).",
            text_available=False, source_quality="official_indirect_reference",
        )

    def _index_norm(self, norm_id, normalized, checksum, *, active, directory, filename, text):
        from rag.constants import DEPARTMENTAL_COLLECTION
        from rag.store import stable_point_id

        source_file = f"departamental/{directory}/{filename}/normalized.txt"
        source_hash = hashlib.sha256(f"{norm_id}:{checksum}".encode()).hexdigest()

        self.store.ensure_collection(DEPARTMENTAL_COLLECTION, self.embedder.vector_size)
        self.store.delete_source(DEPARTMENTAL_COLLECTION, source_file)

        # Build chunks (one per article, fallback to text if no articles)
        chunks = []
        for art in normalized["articles"]:
            label = art["label"]
            body = f"{label}\n{art['text']}".strip()
            if body:
                chunks.append((body, art["number"]))
        if not chunks and text.strip():
            # non-articulated: logical sections fallback
            for i, para in enumerate(text.split("\n\n")[:200]):
                if para.strip():
                    chunks.append((para.strip(), str(i + 1)))

        vectors = self.embedder.embed([c[0] for c in chunks])
        points = []
        for idx, ((chunk_text, article), vector) in enumerate(zip(chunks, vectors)):
            digest = hashlib.sha256(f"{source_hash}:{idx}".encode()).hexdigest()
            import uuid
            point_id = str(uuid.UUID(digest[:32]))
            payload = {
                "text": chunk_text,
                "chunk_index": idx,
                "corpus": "departamental",
                "scope": "departamental",
                "jurisdiction": "UY-LA",
                "department": "Lavalleja",
                "category": directory,
                "document_type": normalized["norm_type"],
                "title": normalized["title"],
                "number": normalized["number"],
                "year": int(normalized["year"]) if normalized["year"] and normalized["year"].isdigit() else None,
                "norm_id": norm_id,
                "normative_family": normalized["family"],
                "source_file": source_file,
                "source_url": normalized.get("source_url", ""),
                "source_hash": source_hash,
                "indexed_at": st.utc_now_iso(),
                "active": active,
                "article": article,
            }
            points.append({
                "id": point_id,
                "vector": vector,
                "payload": payload,
            })
        self.store.upsert(DEPARTMENTAL_COLLECTION, points)
        return len(points)


def _infer_title(text: str) -> str | None:
    for line in (text or "").splitlines():
        line = line.strip()
        if 8 <= len(line) <= 200 and not line.lower().startswith(("artículo", "articulo", "decreto n", "visto", "considerando")):
            return line
    return None


def _build_search_terms(normalized: dict[str, Any]) -> str:
    parts = [
        normalized.get("norm_type", ""),
        str(normalized.get("number", "")),
        str(normalized.get("year", "")),
        normalized.get("title", ""),
        normalized.get("family", ""),
    ]
    for art in normalized.get("articles", [])[:60]:
        parts.append(art.get("title", ""))
        parts.append(art.get("text", "")[:150])
    return " ".join(p for p in parts if p)


class DeptoService:
    def __init__(self, *, embedder=None, store=None, http_client=None):
        self.importer = DepartmentalNormImporter(embedder=embedder, store=store, http_client=http_client)

    def list_norms(self, query: str | None = None, family: str | None = None) -> list[dict[str, Any]]:
        entries = st.search_registry(query) if query else st.list_registry_entries()
        if family:
            entries = [e for e in entries if e.get("normative_family") == family]
        return entries

    def get_stats(self) -> dict[str, Any]:
        reg = st.load_registry()
        total = len(reg)
        with_text = sum(1 for e in reg.values() if e.get("text_available"))
        only_ref = sum(1 for e in reg.values() if not e.get("text_available"))
        recoverable = sum(
            1 for e in reg.values()
            if (
                not e.get("text_available")
                and e.get("downloaded")
                and e.get("extraction_version") != EXTRACTION_VERSION
            )
        )
        reference_only = sum(
            1 for e in reg.values()
            if e.get("source_quality") == "official_indirect_reference"
        )
        ocr_required = sum(
            1 for e in reg.values()
            if e.get("processing_state") == "ocr_required"
        )
        indexed = sum(1 for e in reg.values() if e.get("indexed"))
        active = sum(1 for e in reg.values() if e.get("active_for_rag"))
        articles = sum(e.get("article_count", 0) for e in reg.values())
        chunks = sum(e.get("chunk_count", 0) for e in reg.values())
        families = {e.get("normative_family") for e in reg.values()}
        relations = st.count_relationships()
        return {
            "total": total, "with_text": with_text, "only_reference": only_ref,
            "recoverable": recoverable, "reference_only": reference_only,
            "ocr_required": ocr_required,
            "indexed": indexed, "active": active, "inactive": total - active,
            "articles": articles, "chunks": chunks, "relations": relations,
            "families": len(families),
        }

    def repair_cached_sources(self, *, index: bool = True) -> dict[str, Any]:
        """Re-extract already downloaded sources using the current parser.

        This is intentionally local-only: it never downloads a URL.  It repairs
        records produced by older extraction versions and leaves true indirect
        references untouched.
        """
        registry = st.load_registry()
        summary = {
            "scanned": 0,
            "repaired": 0,
            "with_text": 0,
            "indexed": 0,
            "failed": 0,
            "errors": [],
        }
        for norm_id, entry in registry.items():
            if not entry.get("downloaded"):
                continue
            if (
                entry.get("extraction_version") == EXTRACTION_VERSION
                and (entry.get("text_available") or entry.get("processing_state"))
            ):
                continue

            directory = directory_for_type(entry.get("type", "decreto"))
            year = str(entry["year"]) if entry.get("year") is not None else None
            filename = deterministic_filename(entry.get("type", "decreto"), str(entry.get("number") or "sn"), year)
            target = st.norm_dir(directory, filename)
            source_path: Path | None = None
            content_type = ""
            for candidate, candidate_type in (
                (target / "source.pdf", "application/pdf"),
                (target / "source.html", "text/html"),
                (target / "source.txt", "text/plain"),
            ):
                if candidate.exists():
                    source_path = candidate
                    content_type = candidate_type
                    break
            if source_path is None:
                continue

            summary["scanned"] += 1
            try:
                source_url = str(entry.get("canonical_source") or "")
                source = DownloadedSource(
                    url=source_url,
                    final_url=source_url,
                    content_type=content_type,
                    raw=source_path.read_bytes(),
                    encoding="utf-8" if content_type != "application/pdf" else None,
                )
                result = self.importer._import_downloaded(
                    source,
                    norm_type=entry.get("type") or "decreto",
                    number=str(entry.get("number") or "sn"),
                    year=year,
                    family=entry.get("normative_family") or None,
                    title=entry.get("title") or None,
                    source_quality=entry.get("source_quality") or "unknown",
                    active=entry.get("status", "active") == "active",
                    index=index,
                    evidence_url=(entry.get("evidence_sources") or [None])[0],
                    force=True,
                )
                summary["repaired"] += 1
                summary["with_text"] += int(result.text_available)
                summary["indexed"] += int(result.chunk_count > 0)
            except Exception as exc:
                logger.exception("Error reparando fuente local %s", norm_id)
                summary["failed"] += 1
                summary["errors"].append({"norm_id": norm_id, "message": str(exc)})
        return summary


def get_default_depto_service() -> DeptoService:
    return DeptoService()


def _has_usable_text(text: str, articles: list[Any]) -> bool:
    """Reject navigation/title-only pages while allowing non-articulated norms."""
    clean = (text or "").strip()
    if articles:
        return True
    letters = sum(1 for char in clean if char.isalpha())
    return len(clean) >= 400 and letters >= 250
