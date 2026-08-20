from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .parsers import normalize_text


class ResolutionArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=30)
    text: str = Field(min_length=1)


class LegalResolutionDraft(BaseModel):
    """Structured draft. Validation is syntactic and never legal approval."""

    model_config = ConfigDict(extra="forbid")

    document_type: str = Field(default="resolution", pattern="^resolution$")
    title: str = Field(default="RESOLUCION", min_length=1, max_length=300)
    number: str | None = Field(default=None, max_length=100)
    place: str | None = Field(default=None, max_length=200)
    date: str | None = Field(default=None, max_length=100)
    visto: str = Field(default="", max_length=200_000)
    resultandos: list[str] = Field(default_factory=list)
    considerandos: list[str] = Field(default_factory=list)
    atento: str = Field(default="", max_length=200_000)
    resuelve: list[ResolutionArticle] = Field(min_length=1)
    notes: list[str] = Field(default_factory=lambda: ["BORRADOR SUJETO A REVISION HUMANA"])

    @field_validator("resultandos", "considerandos", "notes")
    @classmethod
    def normalize_items(cls, values: list[str]) -> list[str]:
        return [normalize_text(value) for value in values if normalize_text(value)]


class Resolution(BaseModel):
    """Editable resolution structure; validation is syntactic, not legal approval."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="RESOLUCION", min_length=1, max_length=300)
    number: str | None = Field(default=None, max_length=100)
    place: str | None = Field(default=None, max_length=200)
    date: str | None = Field(default=None, max_length=100)
    seen: list[str] = Field(default_factory=list)
    resultandos: list[str] = Field(default_factory=list)
    considerations: list[str] = Field(default_factory=list)
    atento: str = Field(default="", max_length=200_000)
    articles: list[ResolutionArticle] = Field(default_factory=list)
    signatures: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("seen", "resultandos", "considerations", "signatures", "notes")
    @classmethod
    def no_empty_items(cls, values: list[str]) -> list[str]:
        return [normalize_text(value) for value in values if normalize_text(value)]


HEADING_RE = re.compile(
    r"^\s*(VISTO|VISTOS|RESULTANDO|RESULTANDOS|CONSIDERANDO|CONSIDERANDOS|ATENTO|RESUELVE|ART[IÍ]CULO(?:S)?|FIRMAS?)\s*:?[ \t]*(.*)$",
    re.IGNORECASE,
)
ARTICLE_RE = re.compile(
    r"^\s*ART[IÍ]CULO\s+([\w.-]+)(?:\s*[º°o])?\s*[-:.)]?\s*(.*)$",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(
    r"\bRESOLUCI[OÓ]N\s+(?:N(?:RO\.?|[º°])?\s*)?([^\n]+)",
    re.IGNORECASE,
)


def _paragraphs(lines: list[str]) -> list[str]:
    value = normalize_text("\n".join(lines))
    return [part.strip() for part in re.split(r"\n\s*\n|(?<=;)\s*\n", value) if part.strip()]


def parse_resolution(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    sections: dict[str, list[str]] = {
        "seen": [], "resultandos": [], "considerations": [], "atento": [], "articles": [], "signatures": []
    }
    current: str | None = None
    preamble: list[str] = []

    for line in normalized.splitlines():
        article = ARTICLE_RE.match(line)
        if article:
            current = "articles"
            sections[current].append(f"{article.group(1)}\t{article.group(2).strip()}")
            continue
        heading = HEADING_RE.match(line)
        if heading:
            key = heading.group(1).upper()
            current = (
                "seen" if key.startswith("VIST") else
                "resultandos" if key.startswith("RESULTANDO") else
                "considerations" if key.startswith("CONSIDER") else
                "atento" if key.startswith("ATENTO") else
                "signatures" if key.startswith("FIRMA") else "articles"
            )
            if heading.group(2).strip():
                sections[current].append(heading.group(2).strip())
            continue
        target = sections[current] if current else preamble
        if line.strip():
            if current == "articles" and target:
                target[-1] += " " + line.strip()
            else:
                target.append(line.strip())

    articles = []
    for index, raw in enumerate(sections["articles"], 1):
        if "\t" in raw:
            number, body = raw.split("\t", 1)
        else:
            number, body = str(index), raw
        if body.strip():
            articles.append({"number": number, "text": body.strip()})

    title = next((line for line in preamble if "RESOLUCI" in line.upper()), "RESOLUCION")
    number_match = NUMBER_RE.search(normalized)
    result = Resolution(
        title=title,
        number=number_match.group(1).strip() if number_match else None,
        seen=_paragraphs(sections["seen"]),
        resultandos=_paragraphs(sections["resultandos"]),
        considerations=_paragraphs(sections["considerations"]),
        atento=normalize_text("\n".join(sections["atento"])),
        articles=articles,
        signatures=_paragraphs(sections["signatures"]),
        notes=[] if sections["seen"] and sections["considerations"] and articles else [
            "Estructura incompleta: revisar manualmente las secciones no detectadas."
        ],
    )
    return result.model_dump(mode="json")
