from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


TaxonomyStatus = Literal["draft", "active", "deprecated", "archived"]
IndexStatus = Literal["not_indexed", "pending", "indexing", "synced", "failed", "stale"]
AssignmentRole = Literal["canonical", "secondary", "related", "negative_example"]


class TaxonomyNodeInput(BaseModel):
    parent_id: str | None = None
    level: str = Field(min_length=1, max_length=32)
    code: str = Field(min_length=1, max_length=190, pattern=r"^[A-Za-z0-9_.-]+$")
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    recommended_facts: list[str] = Field(default_factory=list)
    forbidden_assumptions: list[str] = Field(default_factory=list)
    legal_notes: str = ""
    drafting_notes: str = ""
    status: TaxonomyStatus = "draft"
    replaced_by_id: str | None = None


class TaxonomyNodePatch(BaseModel):
    parent_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    aliases: list[str] | None = None
    positive_signals: list[str] | None = None
    negative_signals: list[str] | None = None
    required_facts: list[str] | None = None
    recommended_facts: list[str] | None = None
    forbidden_assumptions: list[str] | None = None
    legal_notes: str | None = None
    drafting_notes: str | None = None
    status: TaxonomyStatus | None = None
    replaced_by_id: str | None = None
    expected_version: int | None = None


class ResolutionAssignmentInput(BaseModel):
    taxonomy_node_id: str
    role: AssignmentRole
    priority: int = Field(default=100, ge=0, le=10000)
    notes: str = ""


class ImportResolutionInput(BaseModel):
    url: HttpUrl
    confirm: bool = False
    assignments: list[ResolutionAssignmentInput] = Field(default_factory=list)
    expected_title: str | None = None
    actor: str = "local-admin"


class ManualResolutionInput(BaseModel):
    resolution_number: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    official_summary: str = ""
    source_url: HttpUrl | None = None
    resolution_date: date | None = None
    publication_date: date | None = None
    normalized_text: str = Field(min_length=1)
    status: Literal["draft", "active", "archived"] = "draft"
    assignments: list[ResolutionAssignmentInput] = Field(default_factory=list)
    change_reason: str = "Carga manual"


class ResolutionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    official_summary: str | None = None
    status: Literal["draft", "active", "archived"] | None = None
    normalized_text: str | None = None
    change_reason: str = "Corrección administrativa"
    assignments: list[ResolutionAssignmentInput] | None = None
    expected_version: int | None = None

    @model_validator(mode="after")
    def revision_reason(self):
        if self.normalized_text is not None and not self.change_reason.strip():
            raise ValueError("Una nueva revisión requiere motivo del cambio")
        return self


class ParsedResolution(BaseModel):
    source_url: str
    source_html: str
    source_hash: str
    resolution_number: str
    resolution_number_normalized: str
    resolution_main_number: int | None = None
    resolution_year_code: str | None = None
    year: int | None = None
    title: str
    official_summary: str = ""
    publication_date: date | None = None
    resolution_date: date | None = None
    raw_text: str
    normalized_text: str
    visto: str = ""
    resultandos: list[str] = Field(default_factory=list)
    considerandos: list[str] = Field(default_factory=list)
    atento: str = ""
    resuelve: list[str] = Field(default_factory=list)
    firmantes: list[str] = Field(default_factory=list)
    structured_sections: dict = Field(default_factory=dict)


class ResolutionTypeMatch(BaseModel):
    taxonomy_node_id: str
    family: str
    type: str
    subtype: str
    description: str
    required_facts: list[str] = Field(default_factory=list)
    score: float


class ResolutionReference(BaseModel):
    resolution_id: str
    number: str
    title: str
    source_url: str
    taxonomy_node_id: str
    role: AssignmentRole
    relevant_sections: list[str] = Field(default_factory=list)
    similarity_score: float | None = None


class ClassificationAlternative(BaseModel):
    taxonomy_node_id: str
    score: float


class ResolutionClassification(BaseModel):
    taxonomy_node_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    alternatives: list[ClassificationAlternative] = Field(default_factory=list)
    rationale: str
    needs_clarification: bool = False
