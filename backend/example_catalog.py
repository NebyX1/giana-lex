"""Catálogo editorial de ejemplos. La fuente importada y las revisiones locales son independientes.

El corpus oficial de ``legal_knowledge`` conserva sus propias resoluciones y reglas de
autoridad. Estas fichas son antecedentes editoriales, nunca normativa comprobada.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from lxml import html
from rank_bm25 import BM25Okapi
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from legal_knowledge.models import Base


IMPORTER_VERSION = "1.0"
MAX_IMPORT_BYTES = 20 * 1024 * 1024
DECISIONS = {"preferente", "utilizable_con_ajustes", "no_usar_como_modelo", "pendiente_lectura"}
POSITIVE_SCOPES = {"editorial", "structure", "excerpt"}


def now():
    return datetime.now(timezone.utc)


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(c for c in value if not unicodedata.combining(c))


def tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(value))


def number_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", norm(value))


def context_units(body: str, query: str, *, max_words: int = 360, max_units: int = 2) -> list[str]:
    """Choose complete administrative clauses within a bounded drafting context.

    The budget is intentionally conservative: several references, the case facts,
    the draft and the model's answer must fit in the same LLM request. A clause
    that cannot fit is omitted rather than presented as an apparently complete
    but truncated legal condition.
    """
    boundaries = re.compile(
        r"(?im)^\s*(?:VISTO\s*:|RESULTANDO\s*:|CONSIDERANDO\s*:|ATENTO\s*:|"
        r"RESUELVE\s*:|\d{1,2}\s*[.)-])"
    )
    units: list[str] = []
    current: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                units.append(" ".join(current))
                current = []
            continue
        if boundaries.match(line) and current:
            units.append(" ".join(current))
            current = []
        current.append(line)
    if current:
        units.append(" ".join(current))
    if not units and body.strip():
        units = [body.strip()]
    qterms = set(tokens(query)) - STOP
    scored = []
    for position, unit in enumerate(units):
        word_count = len(tokens(unit))
        if not word_count or word_count > max_words:
            continue
        overlap = len(qterms & set(tokens(unit)))
        heading = bool(re.match(r"(?i)^(?:VISTO|RESULTANDO|CONSIDERANDO|ATENTO|RESUELVE|\d{1,2}\s*[.)-])", unit))
        scored.append((overlap * 3 + int(heading), position, word_count, unit))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen, used = [], 0
    for _score, position, word_count, unit in scored:
        if len(chosen) >= max_units or used + word_count > max_words:
            continue
        chosen.append((position, unit))
        used += word_count
    return [unit for _, unit in sorted(chosen)]


class ExampleDocument(Base):
    __tablename__ = "example_documents"
    __table_args__ = (
        UniqueConstraint("origin", "external_id", name="uq_example_origin_external"),
        Index("ix_example_identity", "department", "number_key", "act_date"),
        Index("ix_example_state", "decision", "enabled", "scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    origin: Mapped[str] = mapped_column(String(160), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    department: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    authority: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    number: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    number_key: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    act_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(600), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1200), default="", nullable=False)
    family: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    subtypes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    functions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    active_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)


class ExampleRevision(Base):
    __tablename__ = "example_revisions"
    __table_args__ = (UniqueConstraint("document_id", "revision_number", name="uq_example_revision_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("example_documents.id"), index=True, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    editorial_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    enabled_fragments: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    author: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExampleSourceVersion(Base):
    __tablename__ = "example_source_versions"
    __table_args__ = (UniqueConstraint("document_id", "source_hash", name="uq_example_source_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("example_documents.id"), index=True, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    declared_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExampleAudit(Base):
    __tablename__ = "example_audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("example_documents.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ExampleImportBatch(Base):
    __tablename__ = "example_import_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    importer_version: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    details: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


# Each group expands one legal action, but distinct actions are not equated.
EQUIVALENCES = {
    "rectificar": ("corregir", "correccion", "enmendar", "error material", "numero equivocado", "denominacion"),
    "investigar": ("investigacion", "indagacion", "instruir", "sumario", "hechos denunciados"),
    "restituir": ("restitucion", "devolver", "devolucion", "entregar nuevamente", "vencimiento comodato"),
    "delegar": ("delegacion", "encomendar", "atribuciones", "expedicion certificado"),
    "ampliar": ("ampliacion", "aumentar", "incrementar", "mayor cantidad", "prestaciones adicionales"),
    "adjudicar": ("adjudicacion", "seleccionar oferta", "licitacion"),
    "exonerar": ("exoneracion", "dispensa tributaria"),
    "revocar": ("revocacion", "dejar sin efecto", "anular multa"),
    "aceptar": ("aceptacion", "recibir", "donada", "donacion", "incorporar patrimonio"),
    "aprobar": ("aprobacion", "validar", "homologar"),
    "sancionar": ("sancion", "multa", "penalidad"),
    "autorizar": ("autorizacion", "permitir", "permiso", "habilitar"),
    "prorrogar": ("prorroga", "extender plazo", "prolongar vigencia"),
    "regularizar": ("regularizacion", "poner en regla"),
    "declarar": ("declaracion", "interes"),
    "reglamentar": ("reglamentacion", "reglamento", "regular una actividad"),
}
RELATED_NOT_EQUIVALENT = {frozenset(("ampliar", "prorrogar")), frozenset(("revocar", "rescindir")), frozenset(("exonerar", "devolver"))}
STOP = set("a al ante como con de del el en es la las lo los me mi o para por que se su un una y quiero necesito ayuda crear redactar preparar resolucion acto documento administrativa administrativo intendencia".split())


def axes(value: str) -> set[str]:
    n = norm(value)
    result = set()
    for key, variants in EQUIVALENCES.items():
        if re.search(r"\b" + re.escape(key) + r"\w*", n) or any(re.search(r"\b" + re.escape(v) + r"\b", n) for v in variants):
            result.add(key)
    return result


def stage(value: str) -> str:
    n = norm(value)
    if any(word in n for word in ("clausura", "cierre", "archivar", "terminacion")):
        return "cierre"
    if any(word in n for word in ("inicio", "iniciar", "apertura", "abrir", "quiero investigar", "investigar hechos")):
        return "inicio"
    if any(word in n for word in ("prorroga", "modificacion", "ampliacion", "rectificacion")):
        return "modificacion"
    return "decision"


def negated_axes(value: str) -> set[str]:
    text = norm(value)
    result = set()
    for key, variants in EQUIVALENCES.items():
        terms = (key, *variants)
        if any(re.search(r"\b(?:no|sin)\s+(?:quiero\s+)?" + re.escape(term) + r"\w*", text) for term in terms if " " not in term):
            result.add(key)
    return result


def parse_dataset(payload: bytes, filename: str) -> list[dict]:
    if not payload or len(payload) > MAX_IMPORT_BYTES:
        raise ValueError("Archivo vacío o mayor a 20 MB")
    suffix = Path(filename).suffix.lower()
    try:
        decoded = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("El archivo debe estar codificado en UTF-8") from exc
    if suffix in {".html", ".htm"}:
        tree = html.fromstring(payload, parser=html.HTMLParser(no_network=True))
        scripts = tree.xpath('//script[@id="dataset" and @type="application/json"]')
        if len(scripts) != 1 or not scripts[0].text:
            raise ValueError("El HTML debe contener exactamente un script JSON con id=dataset")
        decoded = scripts[0].text
    elif suffix not in {".json", ".jsonl"}:
        raise ValueError("Formato admitido: HTML de catálogo, JSON o JSONL")
    try:
        records = [json.loads(line) for line in decoded.splitlines() if line.strip()] if suffix == ".jsonl" else json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON de dataset inválido") from exc
    if not isinstance(records, list) or len(records) > 20000:
        raise ValueError("El dataset debe ser un array de hasta 20.000 fichas")
    seen = set()
    for index, item in enumerate(records):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("id", "titulo", "decision_editorial")):
            raise ValueError(f"Ficha {index + 1}: id, titulo y decision_editorial obligatorios")
        if item["id"] in seen:
            raise ValueError(f"ID externo duplicado en el lote: {item['id']}")
        seen.add(item["id"])
        if item["decision_editorial"] not in DECISIONS:
            raise ValueError(f"Ficha {item['id']}: decision_editorial desconocida")
        body = item.get("texto_fuente") or item.get("texto_modelo_base") or item.get("texto_original")
        if not isinstance(body, str) or not body.strip() or len(body) > 1_000_000:
            raise ValueError(f"Ficha {item['id']}: texto fuente ausente o excesivo")
    return records


def summary(doc: ExampleDocument, revision: ExampleRevision | None = None) -> dict:
    meta = revision.editorial_data if revision else doc.source_metadata
    return {
        "id": doc.id, "external_id": doc.external_id, "origin": doc.origin, "version": doc.version,
        "revision_id": revision.id if revision else None, "title": doc.title, "department": doc.department,
        "authority": doc.authority, "number": doc.number, "act_date": doc.act_date, "url": doc.source_url,
        "family": doc.family, "type": doc.kind, "subtypes": doc.subtypes, "functions": doc.functions,
        "decision": doc.decision, "enabled": doc.enabled, "scope": doc.scope, "archived": doc.archived,
        "fortalezas": meta.get("fortalezas", []), "defectos_detectados": doc.source_metadata.get("defectos_detectados", []),
        "defectos_resueltos": meta.get("defectos_resueltos", []),
        "hechos_requeridos": meta.get("hechos_requeridos", []), "elementos_reutilizables": meta.get("elementos_reutilizables", []),
        "adaptar_para_lavalleja": meta.get("adaptar_para_lavalleja", []), "normativa_citada": meta.get("normativa_citada", []),
    }


class ExampleCatalog:
    def __init__(self, database, legacy_dir: Path | None = None, settings=None):
        self.database = database
        self.legacy_dir = Path(legacy_dir) if legacy_dir else None
        self.database.ensure_schema()
        self._lock = RLock()
        self._cache_key = None
        self._cache = None
        self.vector = None
        if settings is not None:
            from example_vector import ExampleVector
            self.vector = ExampleVector(settings)

    def invalidate(self):
        with self._lock:
            self._cache_key = None
            self._cache = None

    def import_bytes(self, payload: bytes, filename: str, actor: str = "cli", *, preview=False) -> dict:
        records = parse_dataset(payload, filename)  # whole-batch validation before writes
        counts = Counter({"created": 0, "updated": 0, "skipped": 0, "conflicted": 0, "rejected": 0})
        decisions = Counter(item["decision_editorial"] for item in records)
        details = []
        origin = "gianna-lex-selection"
        with self.database.session() as session:
            for item in records:
                ext_id = item["id"]
                body = item.get("texto_fuente") or item.get("texto_modelo_base") or item.get("texto_original")
                source_hash = digest(json.dumps(item, ensure_ascii=False, sort_keys=True))
                found = session.scalar(select(ExampleDocument).where(ExampleDocument.origin == origin, ExampleDocument.external_id == ext_id))
                identity = (item.get("departamento") or "", number_key(item.get("numero") or ""), item.get("fecha_acto") or "")
                if found and (found.department, found.number_key, found.act_date) != identity:
                    counts["conflicted"] += 1
                    details.append({"id": ext_id, "status": "conflicted", "reason": "La identidad del acto cambió; requiere conciliación"})
                    continue
                if found and found.source_hash == source_hash:
                    known = session.scalar(select(ExampleSourceVersion).where(ExampleSourceVersion.document_id == found.id,
                                                                            ExampleSourceVersion.source_hash == source_hash))
                    if not known and not preview:
                        session.add(ExampleSourceVersion(document_id=found.id, source_hash=source_hash, text_hash=digest(body),
                                                         declared_hash=item.get("sha256_texto_recuperado") or "", text=body,
                                                         source_data=item))
                    audited = session.scalar(select(ExampleAudit.id).where(ExampleAudit.document_id == found.id).limit(1))
                    if not audited and not preview:
                        session.add(ExampleAudit(document_id=found.id, action="imported", actor=actor,
                                                 details={"external_id": ext_id, "source_hash": source_hash}))
                    counts["skipped"] += 1
                    continue
                if found and found.active_revision_id:
                    active = session.get(ExampleRevision, found.active_revision_id)
                    if active and active.author != "importer":
                        counts["conflicted"] += 1
                        details.append({"id": ext_id, "status": "conflicted", "reason": "La versión editorial local está publicada"})
                        if not preview:
                            pending = session.scalar(select(ExampleSourceVersion).where(
                                ExampleSourceVersion.document_id == found.id,
                                ExampleSourceVersion.source_hash == source_hash))
                            if not pending:
                                session.add(ExampleSourceVersion(document_id=found.id, source_hash=source_hash,
                                                                 text_hash=digest(body),
                                                                 declared_hash=item.get("sha256_texto_recuperado") or "",
                                                                 text=body, source_data=item))
                            session.add(ExampleAudit(document_id=found.id, action="source_conflict", actor=actor,
                                                     details={"external_id": ext_id, "source_hash": source_hash,
                                                              "active_revision_id": active.id}))
                        continue
                if not found:
                    decision = item["decision_editorial"]
                    scope = "editorial" if decision == "preferente" else "structure" if decision == "utilizable_con_ajustes" else "none"
                    found = ExampleDocument(
                        origin=origin, external_id=ext_id, department=identity[0], authority=item.get("organo") or identity[0],
                        number=item.get("numero") or "", number_key=identity[1], act_date=identity[2],
                        title=item["titulo"], source_url=item.get("url") or "", family=item.get("familia") or "",
                        kind=item.get("tipo") or "", subtypes=item.get("subtipos") or [],
                        functions=sorted(axes(" ".join([item.get("titulo") or "", item.get("tipo") or "", " ".join(item.get("subtipos") or [])]))),
                        decision=decision, enabled=decision in {"preferente", "utilizable_con_ajustes"}, scope=scope,
                        source_text=body, source_hash=source_hash, source_metadata=item,
                    )
                    session.add(found)
                    session.flush()
                    counts["created"] += 1
                else:
                    previous = found.source_hash
                    found.source_text = body
                    found.source_hash = source_hash
                    found.source_metadata = item
                    found.source_updated_at = now()
                    found.version += 1
                    counts["updated"] += 1
                    session.add(ExampleAudit(document_id=found.id, action="source_updated", actor=actor,
                                             details={"previous_hash": previous, "new_hash": source_hash}))
                    active = session.get(ExampleRevision, found.active_revision_id) if found.active_revision_id else None
                    if active and active.author == "importer":
                        found.title = item["titulo"]
                        found.family = item.get("familia") or ""
                        found.kind = item.get("tipo") or ""
                        found.subtypes = item.get("subtipos") or []
                        found.functions = sorted(axes(" ".join([found.title, found.kind, " ".join(found.subtypes)])))
                        last = session.scalar(select(func.max(ExampleRevision.revision_number)).where(ExampleRevision.document_id == found.id)) or 0
                        refreshed = ExampleRevision(document_id=found.id, revision_number=last + 1, text=body,
                                                    editorial_data=item, scope=found.scope, enabled_fragments=[],
                                                    author="importer", reason="Actualización de fuente")
                        session.add(refreshed)
                        session.flush()
                        found.active_revision_id = refreshed.id
                session.add(ExampleSourceVersion(document_id=found.id, source_hash=source_hash, text_hash=digest(body),
                                                 declared_hash=item.get("sha256_texto_recuperado") or "", text=body,
                                                 source_data=item))
                if not found.active_revision_id:
                    rev = ExampleRevision(document_id=found.id, revision_number=1, text=body,
                                          editorial_data=item, scope=found.scope, enabled_fragments=[], author="importer",
                                          reason="Importación inicial")
                    session.add(rev)
                    session.flush()
                    found.active_revision_id = rev.id
                session.add(ExampleAudit(document_id=found.id, action="imported", actor=actor,
                                         details={"external_id": ext_id, "source_hash": source_hash}))
            result = {**counts, "records": len(records), "decisions": dict(decisions), "details": details,
                      "file_hash": digest(payload), "importer_version": IMPORTER_VERSION}
            if preview:
                session.rollback()
            else:
                batch = ExampleImportBatch(filename=Path(filename).name, file_hash=result["file_hash"],
                                           importer_version=IMPORTER_VERSION, actor=actor, counts=dict(counts), details=details)
                session.add(batch)
                self.invalidate()
        return result

    def _active_revision(self, session, doc):
        return session.get(ExampleRevision, doc.active_revision_id) if doc.active_revision_id else None

    def list(self, filters: dict) -> dict:
        page = max(1, int(filters.get("page") or 1))
        page_size = min(100, max(1, int(filters.get("page_size") or 25)))
        query = norm(filters.get("q") or "")
        with self.database.session() as session:
            docs = session.scalars(select(ExampleDocument)).all()
            rows = [summary(doc, self._active_revision(session, doc)) for doc in docs]
        for field in ("department", "family", "type", "decision", "scope"):
            if filters.get(field):
                rows = [row for row in rows if norm(str(filters[field])) in norm(str(row[field]))]
        if filters.get("function"):
            rows = [row for row in rows if any(norm(str(filters["function"])) in norm(value) for value in row["functions"])]
        if filters.get("date_from"):
            rows = [row for row in rows if row["act_date"] and row["act_date"] >= filters["date_from"]]
        if filters.get("date_to"):
            rows = [row for row in rows if row["act_date"] and row["act_date"] <= filters["date_to"]]
        if query:
            rows = [row for row in rows if query in norm(" ".join(str(row[k]) for k in ("external_id", "number", "title", "type", "normativa_citada")))]
        order = filters.get("order") or "title"
        if order not in {"title", "act_date", "department", "family", "decision", "number"}:
            order = "title"
        rows.sort(key=lambda row: norm(str(row.get(order) or "")), reverse=filters.get("descending") in {"1", "true"})
        return {"total": len(rows), "page": page, "page_size": page_size,
                "items": rows[(page - 1) * page_size:page * page_size]}

    def get(self, identifier: str) -> dict | None:
        with self.database.session() as session:
            doc = session.get(ExampleDocument, identifier)
            if not doc:
                return None
            revision = self._active_revision(session, doc)
            history = session.scalars(select(ExampleRevision).where(ExampleRevision.document_id == doc.id).order_by(ExampleRevision.revision_number.desc())).all()
            source_versions = session.scalars(select(ExampleSourceVersion).where(ExampleSourceVersion.document_id == doc.id).order_by(ExampleSourceVersion.created_at.desc())).all()
            return {**summary(doc, revision), "source_text": doc.source_text, "source_metadata": doc.source_metadata,
                    "active_text": revision.text if revision else "", "active_metadata": revision.editorial_data if revision else {},
                    "enabled_fragments": revision.enabled_fragments if revision else [],
                    "history": [{"id": item.id, "number": item.revision_number, "author": item.author,
                                 "reason": item.reason, "scope": item.scope, "text": item.text,
                                 "created_at": item.created_at.isoformat()} for item in history],
                    "source_versions": [{"id": item.id, "source_hash": item.source_hash, "text_hash": item.text_hash,
                                         "declared_hash": item.declared_hash, "created_at": item.created_at.isoformat()} for item in source_versions]}

    def create(self, value: dict, actor: str) -> dict:
        title = str(value.get("title") or "").strip()
        body = str(value.get("text") or "").strip()
        family = str(value.get("family") or "").strip()
        function = str(value.get("function") or "").strip()
        origin = str(value.get("origin") or "").strip()
        if not all((title, body, family, function, origin)) or len(body) > 1_000_000:
            raise ValueError("Título, contenido, materia, función y procedencia son obligatorios")
        with self.database.session() as session:
            doc = ExampleDocument(origin="local:" + origin[:150], external_id=str(uuid4()), title=title, family=family,
                                  functions=[function], source_text=body, source_hash=digest(body),
                                  source_metadata={"provenance": origin}, decision="pendiente_lectura", enabled=False,
                                  scope="none", kind="Modelo interno")
            session.add(doc)
            session.flush()
            rev = ExampleRevision(document_id=doc.id, revision_number=1, text=body, editorial_data={"provenance": origin},
                                  author=actor, reason="Creación", scope="none", enabled_fragments=[])
            session.add(rev)
            session.flush()
            doc.active_revision_id = rev.id
            session.add(ExampleSourceVersion(document_id=doc.id, source_hash=doc.source_hash, text_hash=doc.source_hash,
                                             declared_hash="", text=body, source_data={"provenance": origin}))
            session.add(ExampleAudit(document_id=doc.id, action="created", actor=actor, details={"origin": origin}))
            identifier = doc.id
        self.invalidate()
        return self.get(identifier)

    def update(self, identifier: str, value: dict, actor: str) -> dict:
        expected = value.get("expected_version")
        if not isinstance(expected, int):
            raise ValueError("expected_version entero es obligatorio")
        with self.database.session() as session:
            doc = session.get(ExampleDocument, identifier)
            if not doc:
                raise KeyError(identifier)
            if doc.version != expected:
                raise RuntimeError("La ficha cambió desde que fue abierta; recargue antes de editar")
            last = session.scalar(select(func.max(ExampleRevision.revision_number)).where(ExampleRevision.document_id == doc.id)) or 0
            active = self._active_revision(session, doc)
            metadata = dict(active.editorial_data if active else doc.source_metadata)
            metadata.update(value.get("metadata") or {})
            text = str(value.get("text") if value.get("text") is not None else active.text if active else doc.source_text)
            if not text.strip() or len(text) > 1_000_000:
                raise ValueError("El texto de la revisión es obligatorio y no puede superar 1 MB")
            scope = value.get("scope", doc.scope)
            if scope not in {"none", "structure", "editorial", "excerpt"}:
                raise ValueError("Alcance inválido")
            fragments = value.get("enabled_fragments", active.enabled_fragments if active else [])
            if not isinstance(fragments, list) or any(not isinstance(part, str) or part not in text for part in fragments):
                raise ValueError("Los fragmentos habilitados deben existir literalmente en la revisión")
            publish = bool(value.get("publish"))
            promoted_decision = value.get("decision", doc.decision)
            if promoted_decision not in DECISIONS:
                raise ValueError("Clasificación editorial inválida")
            if publish and doc.decision in {"no_usar_como_modelo", "pendiente_lectura"} and promoted_decision in {"preferente", "utilizable_con_ajustes"} and not value.get("promotion_reason"):
                raise ValueError("La promoción de un excluido requiere justificación")
            if publish and scope == "excerpt" and not fragments:
                raise ValueError("El uso literal requiere fragmentos expresamente habilitados")
            if publish and doc.decision == "utilizable_con_ajustes" and scope == "editorial":
                unresolved = set(doc.source_metadata.get("defectos_detectados") or []) - set(metadata.get("defectos_resueltos") or [])
                if unresolved or not value.get("promotion_reason"):
                    raise ValueError("Para publicar texto condicionado como modelo editorial debe justificar y resolver todas las observaciones")
            rev = ExampleRevision(document_id=doc.id, revision_number=last + 1, text=text, editorial_data=metadata,
                                  scope=scope, enabled_fragments=fragments, author=actor,
                                  reason=str(value.get("reason") or value.get("promotion_reason") or "Edición"))
            session.add(rev)
            session.flush()
            if publish:
                doc.decision = promoted_decision
                doc.active_revision_id = rev.id
                doc.scope = scope
                doc.enabled = doc.decision in {"preferente", "utilizable_con_ajustes"} and scope in POSITIVE_SCOPES and not bool(value.get("suspend"))
                doc.archived = bool(value.get("archive"))
                for field, attr in (("title", "title"), ("family", "family"), ("type", "kind"), ("department", "department")):
                    if field in value:
                        setattr(doc, attr, str(value[field])[:600])
                if "functions" in value:
                    doc.functions = [str(item) for item in value["functions"]][:20]
            doc.version += 1
            session.add(ExampleAudit(document_id=doc.id, action="published" if publish else "draft_saved", actor=actor,
                                     details={"revision_id": rev.id, "scope": scope, "enabled": doc.enabled}))
        self.invalidate()
        return self.get(identifier)

    def restore(self, identifier: str, revision_id: str, expected_version: int, actor: str, reason: str) -> dict:
        if not reason.strip():
            raise ValueError("Debe indicar el motivo de restauración")
        with self.database.session() as session:
            doc = session.get(ExampleDocument, identifier)
            source = session.get(ExampleRevision, revision_id)
            if not doc or not source or source.document_id != identifier:
                raise KeyError(identifier)
            if doc.version != expected_version:
                raise RuntimeError("La ficha cambió desde que fue abierta")
            last = session.scalar(select(func.max(ExampleRevision.revision_number)).where(ExampleRevision.document_id == identifier)) or 0
            rev = ExampleRevision(document_id=identifier, revision_number=last + 1, text=source.text,
                                  editorial_data=source.editorial_data, scope=source.scope,
                                  enabled_fragments=source.enabled_fragments, author=actor,
                                  reason=f"Restauración de revisión {source.revision_number}: {reason.strip()}")
            session.add(rev)
            session.flush()
            doc.active_revision_id = rev.id
            doc.scope = rev.scope
            doc.enabled = doc.decision in {"preferente", "utilizable_con_ajustes"} and rev.scope in POSITIVE_SCOPES
            doc.archived = False
            doc.version += 1
            session.add(ExampleAudit(document_id=identifier, action="restored", actor=actor,
                                     details={"from_revision": revision_id, "new_revision": rev.id, "reason": reason}))
        self.invalidate()
        return self.get(identifier)

    def _index(self):
        with self.database.session() as session:
            docs = session.scalars(select(ExampleDocument).where(ExampleDocument.enabled.is_(True), ExampleDocument.archived.is_(False))).all()
            rows = []
            for doc in docs:
                if doc.decision == "no_usar_como_modelo":
                    continue
                rev = self._active_revision(session, doc)
                if not rev:
                    continue
                info = summary(doc, rev)
                # Adjustable records contribute their editorial analysis, never their unapproved full source.
                body = rev.text if doc.scope == "editorial" else " ".join(rev.enabled_fragments)
                fields = [doc.title, doc.kind, doc.family, " ".join(doc.subtypes), " ".join(doc.functions),
                          " ".join(info["hechos_requeridos"]), " ".join(info["elementos_reutilizables"]), body[:8000]]
                weighted = " ".join(" ".join([field] * weight) for field, weight in zip(fields, [4, 4, 2, 2, 4, 2, 3, 1]))
                rows.append((info, weighted, body))
        if self.legacy_dir and self.legacy_dir.is_dir():
            for path in sorted(self.legacy_dir.glob("*.md")):
                content = path.read_text(encoding="utf-8")
                rows.append(({"id": "legacy:" + path.name, "external_id": path.name, "revision_id": "legacy:" + digest(content)[:16],
                              "title": path.stem, "url": "", "department": "", "family": "", "type": "",
                              "functions": sorted(axes(content[:1000])), "decision": "sin_evaluacion", "scope": "structure",
                              "enabled": True, "defectos_detectados": [], "elementos_reutilizables": []},
                             path.stem * 3 + " " + content[:3000], content[:3000]))
        tokenized = [tokens(value) for _, value, _ in rows]
        return rows, BM25Okapi(tokenized) if tokenized else None, tokenized

    def search(self, query: str, limit: int = 20) -> dict:
        started = time.perf_counter()
        # DB version is checked on each request, so another process can publish/suspend safely.
        with self.database.session() as session:
            version = session.scalar(select(func.max(ExampleDocument.updated_at)))
            count = session.scalar(select(func.count(ExampleDocument.id))) or 0
        key = (str(version), count)
        with self._lock:
            if key != self._cache_key:
                self._cache = self._index()
                self._cache_key = key
            rows, bm25, tokenized = self._cache
        qtokens = [item for item in tokens(query) if item not in STOP]
        related_tokens = []
        if "prestamo" in qtokens and any(item in qtokens for item in ("local", "inmueble", "bien")):
            related_tokens.append("comodato")
        if "cedido" in qtokens and "gratuitamente" in qtokens:
            related_tokens.append("comodato")
        if "arte" in qtokens and any(item in qtokens for item in ("pieza", "obra", "donada")):
            related_tokens.extend(("artistica", "donacion"))
        excluded_axes = negated_axes(query)
        qaxes = axes(query) - excluded_axes
        if "ampliar" in qaxes and "contrato" in qtokens and "con" in tokens(query):
            qaxes.discard("aceptar")  # Consentimiento es condición de la ampliación, no el objeto del acto.
        if "bases" in qtokens and "concurso" in qtokens:
            qaxes.add("autorizar")
        qstage = stage(query)
        expanded = list(qtokens) + related_tokens + list(qaxes) * 2
        scores = bm25.get_scores(expanded) if bm25 and expanded else [0] * len(rows)
        vector_hits = []
        vector_error = None
        if self.vector and query.strip():
            try:
                vector_hits = self.vector.search(query)
            except Exception as exc:
                vector_error = str(exc)[:150]
        active_revisions = {info["id"]: info["revision_id"] for info, _, _ in rows}
        vector_rank = {item["id"]: rank for rank, item in enumerate(vector_hits, 1)
                       if item["score"] >= 0.5 and active_revisions.get(item["id"]) == item["revision_id"]}
        ranked = []
        for index, (info, _weighted, body) in enumerate(rows):
            shared = set(qtokens) & set(tokenized[index])
            title_shared = (set(qtokens) | set(related_tokens)) & set(tokens(info["title"] + " " + info["type"]))
            matching_axes = qaxes & set(info["functions"])
            text_axes = axes(" ".join((info["title"], info["type"])))
            matching_axes |= qaxes & text_axes
            if not shared and not matching_axes and info["id"] not in vector_rank:
                continue
            # A function match is decisive; editorial quality only breaks relevant ties.
            score = float(scores[index]) + 9 * len(matching_axes) + 1.2 * len(shared) + 7 * len(title_shared)
            if qaxes and not matching_axes:
                score *= 0.35
            if excluded_axes & (set(info["functions"]) | text_axes):
                score -= 30
            if info["decision"] == "preferente":
                score += 0.5
            doc_stage = stage(info["title"] + " " + info["type"])
            if qstage != "decision":
                if qstage == doc_stage:
                    score += 14
                elif {qstage, doc_stage} == {"inicio", "cierre"}:
                    score -= 18
            match_class = "directa" if matching_axes and len(shared) >= 2 else "cercana" if matching_axes else "estructural"
            if info["scope"] == "structure" and info["elementos_reutilizables"]:
                permitted_units = [item.strip() for item in info["elementos_reutilizables"]
                                   if item.strip() and len(tokens(item)) <= 360][:2]
            else:
                permitted_units = context_units(body, query)
            ranked.append({**info, "score": round(score, 3), "match_class": match_class,
                           "reasons": (["Función compartida: " + ", ".join(sorted(matching_axes))] if matching_axes else []) +
                                      (["Términos de contexto: " + ", ".join(sorted(shared)[:6])] if shared else []),
                           "differences": (["La función no coincide; usar sólo componentes compatibles"] if qaxes and not matching_axes else []) +
                                          (["La normativa departamental de otro territorio requiere cotejo propio"] if info["department"] not in {"", "Lavalleja"} else []),
                           "excerpt": permitted_units[0] if permitted_units else "",
                           "context_units": permitted_units,
                           "authorized_content": "\n\n".join(permitted_units),
                           "source_kind": "editorial_example"})
        ranked.sort(key=lambda item: item["score"], reverse=True)
        if vector_rank:
            local_rank = {item["id"]: rank for rank, item in enumerate(ranked, 1)}
            ranked.sort(key=lambda item: (1 / (60 + local_rank[item["id"]]) if item["id"] in local_rank else 0) +
                        (1 / (60 + vector_rank[item["id"]]) if item["id"] in vector_rank else 0), reverse=True)
        # Distinct acts only: the index contains one entry per document/revision.
        results = ranked[:max(1, min(100, limit))]
        return {"status": "direct" if results and results[0]["match_class"] == "directa" else "analogies" if results else "catalog_empty" if not rows else "out_of_scope",
                "results": results, "total": len(ranked), "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "corpus_version": str(version or "empty"), "capabilities": {"local": True, "vector": bool(vector_hits),
                                                                        "vector_error": vector_error}}

    def rebuild_vector(self) -> int:
        if not self.vector:
            raise RuntimeError("El adaptador vectorial no está configurado")
        with self._lock:
            if self._cache is None:
                self._cache = self._index()
            return self.vector.rebuild(self._cache[0])
