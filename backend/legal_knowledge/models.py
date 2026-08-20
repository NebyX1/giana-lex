from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_nodes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_taxonomy_code"),
        UniqueConstraint("parent_id", "slug", name="uq_taxonomy_parent_slug"),
        Index("ix_taxonomy_parent", "parent_id"),
        Index("ix_taxonomy_level_status", "level", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("taxonomy_nodes.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(190), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    positive_signals: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    negative_signals: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    required_facts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recommended_facts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    forbidden_assumptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    legal_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    drafting_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False, index=True)
    replaced_by_id: Mapped[str | None] = mapped_column(ForeignKey("taxonomy_nodes.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    indexed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    index_status: Mapped[str] = mapped_column(String(24), default="not_indexed", nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    updated_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    parent: Mapped[TaxonomyNode | None] = relationship(remote_side=[id], foreign_keys=[parent_id])


class Resolution(Base):
    __tablename__ = "resolutions"
    __table_args__ = (
        UniqueConstraint("source_domain", "resolution_number_normalized", name="uq_resolution_official_number"),
        UniqueConstraint("source_url", name="uq_resolution_source_url"),
        Index("ix_resolution_number", "resolution_number_normalized"),
        Index("ix_resolution_year_status", "year", "status"),
        Index("ix_resolution_index_status", "index_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(32), default="official_url", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    resolution_number: Mapped[str] = mapped_column(String(80), nullable=False)
    resolution_number_normalized: Mapped[str] = mapped_column(String(40), nullable=False)
    resolution_main_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_year_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    official_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    publication_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    resolution_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    current_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    official_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="validated", nullable=False, index=True)
    index_status: Mapped[str] = mapped_column(String(24), default="not_indexed", nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    indexed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    updated_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ResolutionRevision(Base):
    __tablename__ = "resolution_revisions"
    __table_args__ = (UniqueConstraint("resolution_id", "revision_number", name="uq_resolution_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resolution_id: Mapped[str] = mapped_column(ForeignKey("resolutions.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    visto: Mapped[str] = mapped_column(Text, default="", nullable=False)
    resultandos: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    considerandos: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    atento: Mapped[str] = mapped_column(Text, default="", nullable=False)
    resuelve: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    structured_sections: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    resolution: Mapped[Resolution] = relationship()


class ResolutionTaxonomyAssignment(Base):
    __tablename__ = "resolution_taxonomy_assignments"
    __table_args__ = (
        UniqueConstraint("resolution_id", "taxonomy_node_id", name="uq_resolution_taxonomy"),
        Index("ix_assignment_taxonomy_role", "taxonomy_node_id", "role"),
        Index("ix_assignment_resolution", "resolution_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resolution_id: Mapped[str] = mapped_column(ForeignKey("resolutions.id", ondelete="CASCADE"), nullable=False)
    taxonomy_node_id: Mapped[str] = mapped_column(ForeignKey("taxonomy_nodes.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ResolutionOriginal(Base):
    __tablename__ = "resolution_originals"
    __table_args__ = (UniqueConstraint("resolution_id", "source_hash", name="uq_resolution_original_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resolution_id: Mapped[str] = mapped_column(ForeignKey("resolutions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResolutionCatalogEntry(Base):
    __tablename__ = "resolution_catalog"
    __table_args__ = (
        UniqueConstraint("detail_url", name="uq_catalog_url"),
        Index("ix_catalog_number", "resolution_number_normalized"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resolution_number: Mapped[str] = mapped_column(String(80), nullable=False)
    resolution_number_normalized: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    publication_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    detail_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SyncOutbox(Base):
    __tablename__ = "sync_outbox"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "entity_version", "operation", name="uq_outbox_entity_version"),
        Index("ix_outbox_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LegalAuditEvent(Base):
    __tablename__ = "legal_audit_events"
    __table_args__ = (Index("ix_legal_audit_entity", "entity_type", "entity_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
