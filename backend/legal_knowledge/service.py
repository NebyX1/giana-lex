from __future__ import annotations

import json
import logging
import re
import unicodedata
from io import BytesIO
from datetime import date, datetime
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from docx import Document
from pypdf import PdfReader

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError

from .database import LegalKnowledgeDatabase
from .document_storage import ResolutionDocumentStorage
from .importer import LavallejaResolutionImporter
from .indexing import LegalQdrantIndex
from .models import (
    LegalAuditEvent,
    Resolution,
    ResolutionCatalogEntry,
    ResolutionOriginal,
    ResolutionRevision,
    ResolutionTaxonomyAssignment,
    SyncOutbox,
    TaxonomyNode,
    utc_now,
)
from .parser import normalize_resolution_number, number_parts
from .schemas import (
    ManualResolutionInput,
    ParsedResolution,
    ResolutionAssignmentInput,
    ResolutionPatch,
    ResolutionReference,
    ResolutionTypeMatch,
    TaxonomyNodeInput,
    TaxonomyNodePatch,
)


LOGGER = logging.getLogger(__name__)
INDEXABLE_TAXONOMY_FIELDS = {
    "name", "description", "aliases", "positive_signals", "negative_signals", "required_facts",
    "recommended_facts", "forbidden_assumptions", "legal_notes", "drafting_notes", "status",
}
STOPWORDS = {"de", "del", "la", "el", "los", "las", "a", "y", "o", "por", "para", "con", "en", "una", "un", "resolucion"}


def _plain(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in text if not unicodedata.combining(char)).lower()


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _plain(value)) if len(token) > 2 and token not in STOPWORDS}


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _model_dict(model) -> dict:
    return {column.name: _json_value(getattr(model, column.name)) for column in model.__table__.columns}


class KnowledgeConflictError(ValueError):
    pass


class KnowledgeNotFoundError(ValueError):
    pass


class LegalKnowledgeService:
    def __init__(self, settings, database=None, index=None, importer=None):
        self.settings = settings
        self.database = database or LegalKnowledgeDatabase(settings.legal_database_url)
        self.database.ensure_schema()
        self.index = index or LegalQdrantIndex(settings)
        self.importer = importer or LavallejaResolutionImporter(
            timeout=settings.legal_import_timeout_seconds,
            retries=settings.legal_import_retries,
            rate_limit_seconds=settings.legal_import_rate_limit_seconds,
        )
        self.documents = ResolutionDocumentStorage(settings.legal_storage_dir)

    def _audit(self, session, actor: str, action: str, entity_type: str, entity_id: str, before=None, after=None):
        session.add(LegalAuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=_json_value(before),
            after_state=_json_value(after),
        ))
        LOGGER.info("%s actor=%s entity_type=%s entity_id=%s", action, actor, entity_type, entity_id)

    def _outbox(self, session, entity_type: str, entity_id: str, version: int, operation="upsert", force=False) -> str:
        existing = session.scalar(select(SyncOutbox).where(
            SyncOutbox.entity_type == entity_type,
            SyncOutbox.entity_id == entity_id,
            SyncOutbox.entity_version == version,
            SyncOutbox.operation == operation,
        ))
        if existing:
            if force or existing.status == "failed":
                existing.status = "pending"
                existing.processed_at = None
                existing.last_error = None
            return existing.id
        event = SyncOutbox(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_version=version,
            operation=operation,
            status="pending",
        )
        session.add(event)
        session.flush()
        return event.id

    def _sync_background(self):
        Thread(target=lambda: self.process_outbox(limit=10), daemon=True, name="legal-index-sync").start()

    def create_taxonomy(self, data: TaxonomyNodeInput, actor="local-admin", sync=True) -> dict:
        with self.database.session() as session:
            if data.parent_id and not session.get(TaxonomyNode, data.parent_id):
                raise KnowledgeNotFoundError("La tipología padre no existe")
            node = TaxonomyNode(**data.model_dump(), created_by=actor, updated_by=actor)
            session.add(node)
            try:
                session.flush()
            except IntegrityError as exc:
                raise KnowledgeConflictError("El código o slug ya existe") from exc
            if node.status == "active":
                node.index_status = "pending"
                self._outbox(session, "taxonomy", node.id, node.version)
            self._audit(session, actor, "taxonomy_created", "taxonomy", node.id, after=_model_dict(node))
            result = _model_dict(node)
        if sync and result["index_status"] == "pending":
            self._sync_background()
        return result

    def update_taxonomy(self, node_id: str, patch: TaxonomyNodePatch, actor="local-admin", sync=True) -> dict:
        values = patch.model_dump(exclude_unset=True)
        expected = values.pop("expected_version", None)
        with self.database.session() as session:
            node = session.get(TaxonomyNode, node_id)
            if not node:
                raise KnowledgeNotFoundError("Tipología no encontrada")
            if expected is not None and node.version != expected:
                raise KnowledgeConflictError("La tipología fue modificada por otro usuario")
            before = _model_dict(node)
            if "parent_id" in values and values["parent_id"]:
                if values["parent_id"] == node.id or not session.get(TaxonomyNode, values["parent_id"]):
                    raise ValueError("La tipología padre no es válida")
            changed = set(values)
            for key, value in values.items():
                setattr(node, key, value)
            node.version += 1
            node.updated_by = actor
            node.updated_at = utc_now()
            if changed & INDEXABLE_TAXONOMY_FIELDS:
                node.index_status = "pending" if node.status == "active" else "stale"
                self._outbox(session, "taxonomy", node.id, node.version, "upsert" if node.status == "active" else "delete")
            self._audit(session, actor, "taxonomy_updated", "taxonomy", node.id, before, _model_dict(node))
            result = _model_dict(node)
        if sync and changed & INDEXABLE_TAXONOMY_FIELDS:
            self._sync_background()
        return result

    def duplicate_taxonomy(self, node_id: str, code: str, slug: str, actor="local-admin") -> dict:
        source = self.get_taxonomy(node_id)
        fields = TaxonomyNodeInput(
            parent_id=source["parent_id"], level=source["level"], code=code, slug=slug,
            name=f"Copia de {source['name']}", description=source["description"], aliases=source["aliases"],
            positive_signals=source["positive_signals"], negative_signals=source["negative_signals"],
            required_facts=source["required_facts"], recommended_facts=source["recommended_facts"],
            forbidden_assumptions=source["forbidden_assumptions"], legal_notes=source["legal_notes"],
            drafting_notes=source["drafting_notes"], status="draft",
        )
        return self.create_taxonomy(fields, actor)

    def get_taxonomy(self, node_id: str) -> dict:
        with self.database.session() as session:
            node = session.get(TaxonomyNode, node_id)
            if not node:
                raise KnowledgeNotFoundError("Tipología no encontrada")
            result = _model_dict(node)
            assignments = session.scalars(select(ResolutionTaxonomyAssignment).where(
                ResolutionTaxonomyAssignment.taxonomy_node_id == node_id
            )).all()
            resolution_ids = [item.resolution_id for item in assignments]
            resolutions = {item.id: item for item in session.scalars(select(Resolution).where(Resolution.id.in_(resolution_ids))).all()} if resolution_ids else {}
            result["assignments"] = [{**_model_dict(item), "resolution": _model_dict(resolutions[item.resolution_id])} for item in assignments if item.resolution_id in resolutions]
            return result

    def taxonomy_tree(self, query="", status="", level="") -> list[dict]:
        with self.database.session() as session:
            statement = select(TaxonomyNode)
            if status:
                statement = statement.where(TaxonomyNode.status == status)
            if level:
                statement = statement.where(TaxonomyNode.level == level)
            if query:
                like = f"%{query}%"
                statement = statement.where(or_(TaxonomyNode.name.ilike(like), TaxonomyNode.code.ilike(like), TaxonomyNode.description.ilike(like)))
            nodes = session.scalars(statement.order_by(TaxonomyNode.code)).all()
            counts = dict(session.execute(select(
                ResolutionTaxonomyAssignment.taxonomy_node_id, func.count(ResolutionTaxonomyAssignment.id)
            ).group_by(ResolutionTaxonomyAssignment.taxonomy_node_id)).all())
            return [{**_model_dict(node), "resolution_count": counts.get(node.id, 0)} for node in nodes]

    def preview_url(self, url: str, expected_title: str | None = None) -> dict:
        parsed = self.importer.parse_url(url)
        validation = self._validate_semantics(parsed, expected_title)
        suggestions = [match.model_dump() for match in self.search_resolution_types(
            f"{parsed.official_summary}\n{parsed.normalized_text[:2500]}", limit=5
        )]
        return {"parsed": parsed.model_dump(mode="json", exclude={"source_html"}), "validation": validation, "suggestions": suggestions}

    def import_url(self, url: str, assignments: list[ResolutionAssignmentInput] | None = None, expected_title=None, actor="local-admin", sync=True) -> dict:
        parsed = self.importer.parse_url(url)
        return self.persist_parsed(parsed, assignments or [], expected_title, actor, sync)

    def import_number(self, number: str, assignments=None, expected_title=None, actor="seed", sync=False) -> dict:
        parsed = self.importer.resolve_number(number, self._catalog_lookup)
        return self.persist_parsed(parsed, assignments or [], expected_title, actor, sync)

    def _catalog_lookup(self, normalized_number: str) -> str | None:
        with self.database.session() as session:
            entry = session.scalar(select(ResolutionCatalogEntry).where(
                ResolutionCatalogEntry.resolution_number_normalized == normalized_number
            ))
            return entry.detail_url if entry else None

    def _validate_semantics(self, parsed: ParsedResolution, expected_title: str | None) -> dict:
        if not expected_title:
            return {"status": "validated", "reason": "Número oficial verificado"}
        expected = _tokens(expected_title)
        actual = _tokens(f"{parsed.title} {parsed.official_summary} {parsed.normalized_text}")
        overlap = sorted(expected & actual)
        if not overlap:
            return {"status": "import_review_required", "reason": "La ficha no comparte señales semánticas con la tipología esperada", "matched_signals": []}
        return {"status": "validated", "reason": "Número y señales semánticas verificadas", "matched_signals": overlap}

    def persist_parsed(self, parsed: ParsedResolution, assignments: list[ResolutionAssignmentInput], expected_title: str | None, actor: str, sync=True) -> dict:
        validation = self._validate_semantics(parsed, expected_title)
        with self.database.session() as session:
            existing = session.scalar(select(Resolution).where(or_(
                Resolution.source_url == parsed.source_url,
                and_(Resolution.source_domain == (urlparse(parsed.source_url).hostname or ""), Resolution.resolution_number_normalized == parsed.resolution_number_normalized),
            )))
            if existing:
                return {"resolution": _model_dict(existing), "created": False, "duplicate": True, "validation": validation}
            resolution = Resolution(
                source_type="official_url", source_url=parsed.source_url,
                source_domain=urlparse(parsed.source_url).hostname or "gub.uy",
                resolution_number=parsed.resolution_number,
                resolution_number_normalized=parsed.resolution_number_normalized,
                resolution_main_number=parsed.resolution_main_number,
                resolution_year_code=parsed.resolution_year_code, year=parsed.year,
                title=parsed.title, official_summary=parsed.official_summary,
                publication_date=parsed.publication_date, resolution_date=parsed.resolution_date,
                official_source_hash=parsed.source_hash,
                status="active" if validation["status"] == "validated" else "draft",
                review_status=validation["status"], index_status="pending" if validation["status"] == "validated" else "not_indexed",
                created_by=actor, updated_by=actor,
            )
            session.add(resolution)
            session.flush()
            revision = ResolutionRevision(
                resolution_id=resolution.id, revision_number=1, raw_text=parsed.raw_text,
                normalized_text=parsed.normalized_text, visto=parsed.visto,
                resultandos=parsed.resultandos, considerandos=parsed.considerandos,
                atento=parsed.atento, resuelve=parsed.resuelve,
                structured_sections=parsed.structured_sections,
                source="official_import", change_reason="Importación desde fuente oficial", created_by=actor,
            )
            session.add(revision)
            session.flush()
            resolution.current_revision_id = revision.id
            artifact = self.documents.persist_original(resolution.id, parsed)
            session.add(ResolutionOriginal(
                resolution_id=resolution.id, source_hash=parsed.source_hash,
                storage_path=artifact["storage_path"], content_type=artifact["content_type"], byte_size=artifact["byte_size"],
            ))
            if validation["status"] == "validated":
                self._replace_assignments(session, resolution, assignments, actor)
                self._outbox(session, "resolution", resolution.id, resolution.version)
            self._audit(session, actor, "resolution_imported", "resolution", resolution.id, after=_model_dict(resolution))
            result = {"resolution": _model_dict(resolution), "revision": _model_dict(revision), "created": True, "duplicate": False, "validation": validation}
        if sync and validation["status"] == "validated":
            self._sync_background()
        return result

    def create_manual_resolution(self, data: ManualResolutionInput, actor="local-admin", sync=True) -> dict:
        main, year_code, year = number_parts(data.resolution_number)
        normalized = normalize_resolution_number(data.resolution_number)
        source_url = str(data.source_url or f"manual://idl/{normalized}")
        parsed_sections = self._sections_from_text(data.normalized_text)
        with self.database.session() as session:
            resolution = Resolution(
                source_type="manual", source_url=source_url, source_domain=urlparse(source_url).hostname or "manual",
                resolution_number=data.resolution_number, resolution_number_normalized=normalized,
                resolution_main_number=main, resolution_year_code=year_code, year=year,
                title=data.title, official_summary=data.official_summary,
                publication_date=data.publication_date, resolution_date=data.resolution_date,
                official_source_hash="manual:" + normalized, status=data.status, review_status="validated",
                index_status="pending" if data.status == "active" else "not_indexed", created_by=actor, updated_by=actor,
            )
            session.add(resolution)
            session.flush()
            revision = ResolutionRevision(
                resolution_id=resolution.id, revision_number=1, raw_text=data.normalized_text,
                normalized_text=data.normalized_text, source="manual_edit", change_reason=data.change_reason,
                created_by=actor, **parsed_sections,
            )
            session.add(revision)
            session.flush()
            resolution.current_revision_id = revision.id
            self._replace_assignments(session, resolution, data.assignments, actor)
            if resolution.status == "active":
                self._outbox(session, "resolution", resolution.id, resolution.version)
            self._audit(session, actor, "resolution_created", "resolution", resolution.id, after=_model_dict(resolution))
            result = self._resolution_detail(session, resolution)
        if sync and data.status == "active":
            self._sync_background()
        return result

    def import_file(self, filename: str, content_type: str, content: bytes, metadata: dict, actor="local-admin") -> dict:
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("El archivo excede el límite de 10 MB")
        extension = Path(filename).suffix.lower()
        if extension in {".txt", ".md"}:
            text = content.decode("utf-8", errors="replace")
        elif extension == ".docx":
            document = Document(BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
        elif extension == ".pdf":
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            raise ValueError("Formato no admitido. Use PDF, DOCX, TXT o MD")
        if not text.strip():
            raise ValueError("No se pudo extraer texto utilizable del archivo")
        assignments = [ResolutionAssignmentInput.model_validate(item) for item in metadata.get("assignments", [])]
        data = ManualResolutionInput(
            resolution_number=metadata.get("resolution_number", ""), title=metadata.get("title", ""),
            official_summary=metadata.get("official_summary", ""), normalized_text=text,
            status=metadata.get("status", "draft"), assignments=assignments,
            change_reason="Carga desde archivo",
        )
        result = self.create_manual_resolution(data, actor=actor, sync=False)
        artifact = self.documents.persist_upload(result["id"], filename, content)
        with self.database.session() as session:
            session.add(ResolutionOriginal(
                resolution_id=result["id"], source_hash=artifact["source_hash"], storage_path=artifact["storage_path"],
                content_type=content_type or "application/octet-stream", byte_size=artifact["byte_size"],
            ))
        if data.status == "active":
            self._sync_background()
        return self.get_resolution(result["id"])

    def update_resolution(self, resolution_id: str, patch: ResolutionPatch, actor="local-admin", sync=True) -> dict:
        values = patch.model_dump(exclude_unset=True)
        assignments = values.pop("assignments", None)
        expected = values.pop("expected_version", None)
        normalized_text = values.pop("normalized_text", None)
        change_reason = values.pop("change_reason", "Corrección administrativa")
        with self.database.session() as session:
            resolution = session.get(Resolution, resolution_id)
            if not resolution:
                raise KnowledgeNotFoundError("Resolución no encontrada")
            if expected is not None and resolution.version != expected:
                raise KnowledgeConflictError("La resolución fue modificada por otro usuario")
            before = self._resolution_detail(session, resolution)
            for key, value in values.items():
                setattr(resolution, key, value)
            content_changed = normalized_text is not None
            if content_changed:
                latest = session.scalar(select(func.max(ResolutionRevision.revision_number)).where(ResolutionRevision.resolution_id == resolution.id)) or 0
                sections = self._sections_from_text(normalized_text)
                revision = ResolutionRevision(
                    resolution_id=resolution.id, revision_number=latest + 1, raw_text=normalized_text,
                    normalized_text=normalized_text, source="manual_edit", change_reason=change_reason,
                    created_by=actor, **sections,
                )
                session.add(revision)
                session.flush()
                resolution.current_revision_id = revision.id
            if assignments is not None:
                self._replace_assignments(
                    session,
                    resolution,
                    [item if isinstance(item, ResolutionAssignmentInput) else ResolutionAssignmentInput.model_validate(item) for item in assignments],
                    actor,
                )
            resolution.version += 1
            resolution.updated_by = actor
            resolution.updated_at = utc_now()
            resolution.index_status = "pending" if resolution.status == "active" else "stale"
            event_type = "resolution" if content_changed else "resolution_payload"
            self._outbox(session, event_type, resolution.id, resolution.version, "upsert" if resolution.status == "active" else "delete")
            self._audit(session, actor, "resolution_updated", "resolution", resolution.id, before, self._resolution_detail(session, resolution))
            result = self._resolution_detail(session, resolution)
        if sync:
            self._sync_background()
        return result

    def _replace_assignments(self, session, resolution: Resolution, assignments: list[ResolutionAssignmentInput], actor: str):
        session.query(ResolutionTaxonomyAssignment).filter_by(resolution_id=resolution.id).delete()
        for item in assignments:
            node = session.get(TaxonomyNode, item.taxonomy_node_id)
            if not node:
                raise KnowledgeNotFoundError(f"Tipología no encontrada: {item.taxonomy_node_id}")
            role = item.role
            if node.status != "active" and role == "canonical":
                raise ValueError("Una tipología no activa no puede recibir un antecedente canónico")
            session.add(ResolutionTaxonomyAssignment(
                resolution_id=resolution.id, taxonomy_node_id=node.id, role=role,
                priority=item.priority, notes=item.notes, created_by=actor,
            ))
        session.flush()

    @staticmethod
    def _sections_from_text(text: str) -> dict:
        buckets = {"visto": [], "resultandos": [], "considerandos": [], "atento": [], "resuelve": []}
        current = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            heading = re.match(r"^(VISTO|RESULTANDOS?|CONSIDERANDOS?|ATENTO|RESUELVE)\s*:?(.*)$", line, re.I)
            if heading:
                name = _plain(heading.group(1))
                current = "visto" if name == "visto" else "resultandos" if name.startswith("resultando") else "considerandos" if name.startswith("considerando") else "atento" if name == "atento" else "resuelve"
                if heading.group(2).strip():
                    buckets[current].append(heading.group(2).strip())
            elif current:
                buckets[current].append(line)
        return {
            "visto": "\n".join(buckets["visto"]), "resultandos": buckets["resultandos"],
            "considerandos": buckets["considerandos"], "atento": "\n".join(buckets["atento"]),
            "resuelve": buckets["resuelve"], "structured_sections": buckets,
        }

    def list_resolutions(self, page=1, page_size=25, query="", year=None, status="", role="", taxonomy_node_id="", index_status="", order="recent") -> dict:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        with self.database.session() as session:
            statement = select(Resolution).distinct()
            if role or taxonomy_node_id:
                statement = statement.join(ResolutionTaxonomyAssignment)
            if query:
                like = f"%{query}%"
                statement = statement.join(ResolutionRevision, ResolutionRevision.id == Resolution.current_revision_id, isouter=True).where(or_(
                    Resolution.resolution_number.ilike(like), Resolution.resolution_number_normalized.ilike(f"%{normalize_resolution_number(query)}%"),
                    Resolution.title.ilike(like), Resolution.official_summary.ilike(like), ResolutionRevision.normalized_text.ilike(like),
                ))
            if year:
                statement = statement.where(Resolution.year == year)
            if status:
                statement = statement.where(Resolution.status == status)
            if index_status:
                statement = statement.where(Resolution.index_status == index_status)
            if role:
                statement = statement.where(ResolutionTaxonomyAssignment.role == role)
            if taxonomy_node_id:
                statement = statement.where(ResolutionTaxonomyAssignment.taxonomy_node_id == taxonomy_node_id)
            total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
            ordering = Resolution.updated_at.desc()
            if order == "oldest": ordering = Resolution.updated_at.asc()
            if order == "number": ordering = Resolution.resolution_main_number.asc()
            items = session.scalars(statement.order_by(ordering).offset((page - 1) * page_size).limit(page_size)).all()
            return {"items": [self._resolution_summary(session, item) for item in items], "page": page, "page_size": page_size, "total": total}

    def get_resolution(self, resolution_id: str) -> dict:
        with self.database.session() as session:
            resolution = session.get(Resolution, resolution_id)
            if not resolution:
                raise KnowledgeNotFoundError("Resolución no encontrada")
            return self._resolution_detail(session, resolution)

    def _resolution_summary(self, session, resolution: Resolution) -> dict:
        result = _model_dict(resolution)
        result["assignments"] = [_model_dict(item) for item in session.scalars(select(ResolutionTaxonomyAssignment).where(
            ResolutionTaxonomyAssignment.resolution_id == resolution.id
        )).all()]
        return result

    def _resolution_detail(self, session, resolution: Resolution) -> dict:
        result = self._resolution_summary(session, resolution)
        result["revisions"] = [_model_dict(item) for item in session.scalars(select(ResolutionRevision).where(
            ResolutionRevision.resolution_id == resolution.id
        ).order_by(ResolutionRevision.revision_number.desc())).all()]
        result["originals"] = [_model_dict(item) for item in session.scalars(select(ResolutionOriginal).where(
            ResolutionOriginal.resolution_id == resolution.id
        )).all()]
        return result

    def overview(self) -> dict:
        with self.database.session() as session:
            metric = lambda model, *where: session.scalar(select(func.count()).select_from(model).where(*where)) or 0
            active_subtypes = metric(TaxonomyNode, TaxonomyNode.level == "subtype", TaxonomyNode.status == "active")
            canonical_nodes = session.scalars(select(ResolutionTaxonomyAssignment.taxonomy_node_id).where(
                ResolutionTaxonomyAssignment.role == "canonical"
            ).distinct()).all()
            pending = metric(SyncOutbox, SyncOutbox.status.in_(["pending", "processing"]))
            failed = metric(SyncOutbox, SyncOutbox.status == "failed")
        return {
            "typologies_active": active_subtypes,
            "resolutions": self._count_resolutions(),
            "canonical_precedents": len(canonical_nodes),
            "subtypes_without_canonical": max(0, active_subtypes - len(canonical_nodes)),
            "pending_index": pending,
            "index_errors": failed,
            "qdrant": self.index.health(),
        }

    def _count_resolutions(self):
        with self.database.session() as session:
            return session.scalar(select(func.count()).select_from(Resolution)) or 0

    def search_resolution_types(self, query: str, limit=5) -> list[ResolutionTypeMatch]:
        limit = min(max(limit, 1), 20)
        try:
            matches = self.index.search_taxonomy(query, limit)
            if matches:
                verified = []
                with self.database.session() as session:
                    for item in matches:
                        node = session.get(TaxonomyNode, item["taxonomy_node_id"])
                        if not node or node.status != "active" or node.level != "subtype":
                            continue
                        family, type_node = self._ancestors(session, node)
                        verified.append(ResolutionTypeMatch(
                            taxonomy_node_id=node.id, family=family.name if family else "",
                            type=type_node.name if type_node else "", subtype=node.name,
                            description=node.description, required_facts=node.required_facts,
                            score=item["score"],
                        ))
                if verified:
                    return verified
        except Exception as exc:
            LOGGER.warning("qdrant_taxonomy_search_failed error=%s", exc)
        query_tokens = _tokens(query)
        candidates = []
        with self.database.session() as session:
            nodes = session.scalars(select(TaxonomyNode).where(
                TaxonomyNode.level == "subtype", TaxonomyNode.status == "active"
            )).all()
            for node in nodes:
                content = " ".join([node.code, node.name, node.description, *node.aliases, *node.positive_signals])
                node_tokens = _tokens(content)
                overlap = len(query_tokens & node_tokens)
                if overlap:
                    score = overlap / max(len(query_tokens), 1)
                    family, type_node = self._ancestors(session, node)
                    candidates.append(ResolutionTypeMatch(
                        taxonomy_node_id=node.id, family=family.name if family else "",
                        type=type_node.name if type_node else "", subtype=node.name,
                        description=node.description, required_facts=node.required_facts, score=score,
                    ))
        return sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]

    def search_resolution_examples(self, taxonomy_node_id: str, query: str | None = None, limit=5) -> list[ResolutionReference]:
        with self.database.session() as session:
            assignments = session.scalars(select(ResolutionTaxonomyAssignment).join(Resolution).where(
                ResolutionTaxonomyAssignment.taxonomy_node_id == taxonomy_node_id,
                Resolution.status == "active",
            ).order_by(
                case((ResolutionTaxonomyAssignment.role == "canonical", 0), (ResolutionTaxonomyAssignment.role == "secondary", 1), else_=2),
                ResolutionTaxonomyAssignment.priority,
            )).all()
            references = []
            for assignment in assignments[:limit]:
                resolution = session.get(Resolution, assignment.resolution_id)
                references.append(ResolutionReference(
                    resolution_id=resolution.id, number=resolution.resolution_number, title=resolution.title,
                    source_url=resolution.source_url, taxonomy_node_id=taxonomy_node_id, role=assignment.role,
                    relevant_sections=[], similarity_score=None,
                ))
        if query:
            try:
                hits = self.index.search_resolutions(taxonomy_node_id, query, max(limit * 2, 8))
                by_resolution = {}
                for hit in hits:
                    current = by_resolution.setdefault(hit["resolution_id"], {"score": hit["score"], "sections": []})
                    current["score"] = max(current["score"], hit["score"])
                    if hit.get("section") not in current["sections"]:
                        current["sections"].append(hit.get("section"))
                for reference in references:
                    hit = by_resolution.get(reference.resolution_id)
                    if hit:
                        reference.similarity_score = hit["score"]
                        reference.relevant_sections = hit["sections"]
            except Exception as exc:
                LOGGER.warning("qdrant_resolution_search_failed error=%s", exc)
        return references

    def get_required_facts(self, taxonomy_node_id: str) -> list[str]:
        node = self.get_taxonomy(taxonomy_node_id)
        return node["required_facts"]

    def _ancestors(self, session, node: TaxonomyNode):
        type_node = session.get(TaxonomyNode, node.parent_id) if node.parent_id else None
        family = session.get(TaxonomyNode, type_node.parent_id) if type_node and type_node.parent_id else None
        return family, type_node

    def _taxonomy_index_document(self, session, node: TaxonomyNode) -> tuple[str, dict]:
        family, type_node = self._ancestors(session, node)
        document = "\n".join(filter(None, [
            f"Familia: {family.name if family else ''}", f"Tipo: {type_node.name if type_node else ''}",
            f"Subtipo: {node.name}", f"Descripción: {node.description}",
            "Aliases: " + ", ".join(node.aliases), "Señales positivas: " + ", ".join(node.positive_signals),
            "Señales negativas: " + ", ".join(node.negative_signals),
            "Hechos obligatorios: " + ", ".join(node.required_facts),
            "Hechos recomendados: " + ", ".join(node.recommended_facts),
            "Suposiciones prohibidas: " + ", ".join(node.forbidden_assumptions), node.legal_notes, node.drafting_notes,
        ]))
        payload = {
            "document_kind": "resolution_taxonomy", "taxonomy_node_id": node.id,
            "family_id": family.id if family else None, "type_id": type_node.id if type_node else None,
            "subtype_id": node.id, "family_code": family.code if family else "",
            "type_code": type_node.code if type_node else "", "subtype_code": node.code,
            "family": family.name if family else "", "type": type_node.name if type_node else "",
            "name": node.name, "description": node.description, "aliases": node.aliases,
            "required_facts": node.required_facts, "status": node.status, "entity_version": node.version,
        }
        return document, payload

    def process_outbox(self, limit=100, only_failed=False) -> dict:
        # `processing` se recupera porque un worker/CLI puede terminar luego de reclamar el evento.
        statuses = ["failed"] if only_failed else ["pending", "failed", "processing"]
        with self.database.session() as session:
            events = session.scalars(select(SyncOutbox).where(SyncOutbox.status.in_(statuses)).order_by(SyncOutbox.created_at).limit(limit)).all()
            event_ids = [event.id for event in events]
        completed = 0
        failed = 0
        for event_id in event_ids:
            try:
                self._process_event(event_id)
                completed += 1
            except Exception as exc:
                failed += 1
                LOGGER.exception("qdrant_index_failed event_id=%s", event_id)
                with self.database.session() as session:
                    event = session.get(SyncOutbox, event_id)
                    if event:
                        event.status = "failed"
                        event.attempts += 1
                        event.last_error = str(exc)[:4000]
        return {"selected": len(event_ids), "completed": completed, "failed": failed}

    def _process_event(self, event_id: str):
        with self.database.session() as session:
            event = session.get(SyncOutbox, event_id)
            if not event or event.status == "completed":
                return
            event.status = "processing"
            event.attempts += 1
            entity_type, entity_id, operation = event.entity_type, event.entity_id, event.operation
        LOGGER.info("qdrant_index_started entity_type=%s entity_id=%s", entity_type, entity_id)
        if entity_type == "taxonomy":
            with self.database.session() as session:
                node = session.get(TaxonomyNode, entity_id)
                if not node or operation == "delete" or node.status != "active" or node.level != "subtype":
                    self.index.delete_taxonomy(entity_id)
                else:
                    document, payload = self._taxonomy_index_document(session, node)
                    self.index.upsert_taxonomy(document, payload)
        elif entity_type in {"resolution", "resolution_payload"}:
            with self.database.session() as session:
                resolution = session.get(Resolution, entity_id)
                if not resolution or operation == "delete" or resolution.status != "active":
                    self.index.delete_resolution(entity_id)
                else:
                    assignments = [_model_dict(item) for item in session.scalars(select(ResolutionTaxonomyAssignment).where(
                        ResolutionTaxonomyAssignment.resolution_id == entity_id
                    )).all()]
                    if entity_type == "resolution_payload" and resolution.indexed_version:
                        by_role = {"canonical": [], "secondary": [], "related": [], "negative_example": []}
                        for item in assignments: by_role[item["role"]].append(item["taxonomy_node_id"])
                        self.index.update_resolution_payload(entity_id, {
                            "taxonomy_node_ids": [item["taxonomy_node_id"] for item in assignments],
                            "canonical_for": by_role["canonical"], "secondary_for": by_role["secondary"],
                            "related_to": by_role["related"], "negative_for": by_role["negative_example"],
                            "active": True, "entity_version": resolution.version,
                        })
                    else:
                        revision = session.get(ResolutionRevision, resolution.current_revision_id)
                        self.index.upsert_resolution(_model_dict(resolution), _model_dict(revision), assignments)
        with self.database.session() as session:
            event = session.get(SyncOutbox, event_id)
            event.status = "completed"
            event.processed_at = utc_now()
            event.last_error = None
            if entity_type == "taxonomy":
                node = session.get(TaxonomyNode, entity_id)
                if node:
                    node.indexed_version = event.entity_version
                    node.index_status = "synced" if node.status == "active" else "not_indexed"
            elif entity_type.startswith("resolution"):
                resolution = session.get(Resolution, entity_id)
                if resolution:
                    resolution.indexed_version = event.entity_version
                    resolution.index_status = "synced" if resolution.status == "active" else "not_indexed"
        LOGGER.info("qdrant_index_completed entity_type=%s entity_id=%s", entity_type, entity_id)

    def enqueue_reindex(self, entity_type: str, entity_id: str, actor="local-admin", sync=True) -> dict:
        with self.database.session() as session:
            if entity_type == "taxonomy":
                entity = session.get(TaxonomyNode, entity_id)
            else:
                entity = session.get(Resolution, entity_id)
            if not entity:
                raise KnowledgeNotFoundError("Entidad no encontrada")
            entity.index_status = "pending"
            event_id = self._outbox(session, entity_type, entity.id, entity.version, force=True)
            self._audit(session, actor, "reindex_requested", entity_type, entity.id)
        if sync:
            self._sync_background()
        return {"event_id": event_id, "status": "pending"}

    def enqueue_rebuild(self, actor="cli") -> dict:
        taxonomy = 0
        resolutions = 0
        with self.database.session() as session:
            for node in session.scalars(select(TaxonomyNode).where(
                TaxonomyNode.level == "subtype", TaxonomyNode.status == "active"
            )).all():
                node.index_status = "pending"
                self._outbox(session, "taxonomy", node.id, node.version, force=True)
                taxonomy += 1
            for resolution in session.scalars(select(Resolution).where(Resolution.status == "active")).all():
                resolution.index_status = "pending"
                self._outbox(session, "resolution", resolution.id, resolution.version, force=True)
                resolutions += 1
            self._audit(session, actor, "index_rebuild_enqueued", "index", "legal-knowledge", after={"taxonomy": taxonomy, "resolutions": resolutions})
        return {"taxonomy": taxonomy, "resolutions": resolutions, "status": "pending"}

    def index_status(self) -> dict:
        with self.database.session() as session:
            by_status = dict(session.execute(select(SyncOutbox.status, func.count()).group_by(SyncOutbox.status)).all())
            failed = [_model_dict(item) for item in session.scalars(select(SyncOutbox).where(
                SyncOutbox.status == "failed"
            ).order_by(SyncOutbox.created_at.desc()).limit(50)).all()]
        return {"qdrant": self.index.health(), "outbox": by_status, "failed_events": failed}

    def check_consistency(self) -> dict:
        issues = []
        with self.database.session() as session:
            stale_nodes = session.scalars(select(TaxonomyNode).where(
                TaxonomyNode.status == "active",
                or_(TaxonomyNode.indexed_version.is_(None), TaxonomyNode.indexed_version != TaxonomyNode.version),
            )).all()
            stale_resolutions = session.scalars(select(Resolution).where(
                Resolution.status == "active",
                or_(Resolution.indexed_version.is_(None), Resolution.indexed_version != Resolution.version),
            )).all()
            active_subtypes = session.scalars(select(TaxonomyNode).where(
                TaxonomyNode.level == "subtype", TaxonomyNode.status == "active"
            )).all()
            canonical_ids = set(session.scalars(select(ResolutionTaxonomyAssignment.taxonomy_node_id).where(
                ResolutionTaxonomyAssignment.role == "canonical"
            )).all())
            known_taxonomy = {item.id: item for item in session.scalars(select(TaxonomyNode)).all()}
            known_resolutions = {item.id: item for item in session.scalars(select(Resolution)).all()}
            for node in stale_nodes:
                issues.append({"kind": "taxonomy_version_mismatch", "entity_id": node.id, "version": node.version, "indexed_version": node.indexed_version})
            for resolution in stale_resolutions:
                issues.append({"kind": "resolution_version_mismatch", "entity_id": resolution.id, "version": resolution.version, "indexed_version": resolution.indexed_version})
            for node in active_subtypes:
                if node.id not in canonical_ids:
                    issues.append({"kind": "subtype_without_canonical", "entity_id": node.id, "code": node.code})
        try:
            taxonomy_points = self.index.inventory(self.settings.qdrant_taxonomy_collection)
            resolution_points = self.index.inventory(self.settings.qdrant_resolutions_collection)
            indexed_taxonomy_ids = {item.get("taxonomy_node_id") for item in taxonomy_points}
            indexed_resolution_ids = {item.get("resolution_id") for item in resolution_points}
            for point in taxonomy_points:
                node = known_taxonomy.get(point.get("taxonomy_node_id"))
                if not node:
                    issues.append({"kind": "orphan_taxonomy_point", "point_id": point["point_id"], "entity_id": point.get("taxonomy_node_id")})
                elif node.status != "active" or node.level != "subtype":
                    issues.append({"kind": "inactive_taxonomy_retrievable", "point_id": point["point_id"], "entity_id": node.id})
            seen_chunks = set()
            for point in resolution_points:
                resolution = known_resolutions.get(point.get("resolution_id"))
                if not resolution:
                    issues.append({"kind": "orphan_resolution_point", "point_id": point["point_id"], "entity_id": point.get("resolution_id")})
                elif resolution.status != "active" or not point.get("active"):
                    issues.append({"kind": "archived_resolution_retrievable", "point_id": point["point_id"], "entity_id": resolution.id})
                for taxonomy_id in point.get("taxonomy_node_ids", []):
                    if taxonomy_id not in known_taxonomy:
                        issues.append({"kind": "invalid_taxonomy_relation", "point_id": point["point_id"], "entity_id": taxonomy_id})
                chunk_key = (point.get("resolution_id"), point.get("revision_id"), point.get("section"), point.get("chunk_index"))
                if chunk_key in seen_chunks:
                    issues.append({"kind": "duplicate_resolution_chunk", "point_id": point["point_id"], "entity_id": point.get("resolution_id")})
                seen_chunks.add(chunk_key)
            for node in active_subtypes:
                if node.id not in indexed_taxonomy_ids:
                    issues.append({"kind": "taxonomy_missing_in_qdrant", "entity_id": node.id, "code": node.code})
            for resolution in known_resolutions.values():
                if resolution.status == "active" and resolution.id not in indexed_resolution_ids:
                    issues.append({"kind": "resolution_missing_in_qdrant", "entity_id": resolution.id})
        except Exception as exc:
            issues.append({"kind": "qdrant_consistency_unavailable", "error": str(exc)})
        return {"checked_at": utc_now().isoformat(), "issue_count": len(issues), "issues": issues, "destructive_repairs_applied": False}

    def export_manifest(self, path: Path) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.database.session() as session, path.open("w", encoding="utf-8") as handle:
            resolutions = session.scalars(select(Resolution).order_by(Resolution.resolution_number_normalized)).all()
            for resolution in resolutions:
                assignments = session.scalars(select(ResolutionTaxonomyAssignment).where(
                    ResolutionTaxonomyAssignment.resolution_id == resolution.id
                )).all()
                paths = [session.get(TaxonomyNode, item.taxonomy_node_id).code for item in assignments]
                handle.write(json.dumps({
                    "resolution_number": resolution.resolution_number, "resolution_id": resolution.id,
                    "source_url": resolution.source_url, "source_hash": resolution.official_source_hash,
                    "downloaded_at": resolution.created_at.isoformat(), "taxonomy_paths": paths,
                    "status": resolution.review_status,
                }, ensure_ascii=False) + "\n")
        return len(resolutions)

    def crawl_catalog(self, start_page=0, max_pages=1) -> dict:
        seen = 0
        created = 0
        updated = 0
        with self.database.session() as session:
            for item in self.importer.crawl_catalog(start_page, max_pages):
                seen += 1
                entry = session.scalar(select(ResolutionCatalogEntry).where(
                    ResolutionCatalogEntry.detail_url == item["detail_url"]
                ))
                if entry:
                    for key, value in item.items():
                        setattr(entry, key, value)
                    entry.last_seen_at = utc_now()
                    updated += 1
                else:
                    session.add(ResolutionCatalogEntry(**item))
                    created += 1
        return {"pages_requested": max_pages, "seen": seen, "created": created, "updated": updated}
