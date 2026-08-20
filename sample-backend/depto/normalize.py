from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


ARTICLE_RE = re.compile(
    r"(?im)^\s*(?:ART(?:Í|I)CULO|ART[.]?|ART°)\s*"
    r"(?P<num>\d{1,4})\s*(?P<bis>[bB]is|[tT]er|[qQ]uater|[pP]ro)?\s*[°º:.\-–—)]?\s*"
    r"(?P<title>[A-ZÁÉÍÓÚÑ][^:\n]{0,120})?"
    r"(?::\s*(?P<rest>.*))?"
)
_NORM_REF = re.compile(
    r"(?i)\b(decreto\s*(?:departamental\s*)?(?:n[°ºo]?\.?)?\s*(\d{1,5})(?:[/\-])(\d{2,4}))"
    r"|(?:ley\s+(?:n[°ºo]?\.?)?\s*(\d{1,5})(?:[/\-])(\d{4}))"
    r"|(?:ordenanza\s+(?:general\s+)?(?:n[°ºo]?\.?)?\s*([0-9/]+))"
)

RELATION_KEYWORDS = [
    ("MODIFIES", ["modifícase", "modificase", "modifícanse", "modificanse", "sustitúyese", "sustituyese", "en la redacción dada", "redaccion dada"]),
    ("DEROGATES", ["derógase", "derogase", "deróganse", "deroganse"]),
    ("RESTORES", ["restablécese", "restablecese", "declárase vigente", "declarase vigente", "restablézcase"]),
    ("INCORPORATES", ["incorpórase", "incorporase", "hace aplicable", "hacen aplicable", "aplicables las disposiciones", "incorpora"]),
    ("REGULATES", ["reglamenta", "reglamentase", "reglamenta la", "regula"]),
    ("INTERPRETS", ["interpretativo", "interpretación", "interpretacion", "interpretase", "interprétase"]),
    ("REPLACES", ["sustituye integralmente", "deroga y sustituye", "deja sin efecto y sustituye"]),
]


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", value)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


@dataclass
class Article:
    number: str
    bis: str
    title: str
    text: str

    @property
    def label(self) -> str:
        base = f"Artículo {self.number}"
        if self.bis:
            base += f" {self.bis.upper()}"
        return base


@dataclass
class NormalizedDeptoNorm:
    norm_id: str
    norm_type: str
    number: str
    year: str | None
    title: str
    directory: str
    family: str
    articles: list[Article] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "norm_id": self.norm_id,
            "norm_type": self.norm_type,
            "number": self.number,
            "year": self.year,
            "title": self.title,
            "directory": self.directory,
            "family": self.family,
            "article_count": len(self.articles),
            "articles": [{"number": a.number, "bis": a.bis, "title": a.title, "text": a.text, "label": a.label} for a in self.articles],
            "relations": self.relations,
        }


def detect_articles(text: str) -> list[Article]:
    articles: list[Article] = []
    lines = (text or "").splitlines()
    i = 0
    current: Article | None = None
    for line in lines:
        line = line.strip()
        m = ARTICLE_RE.match(line)
        if m and current:
            next_number = int(m.group("num"))
            current_number = int(current.number)
            next_bis = (m.group("bis") or "").strip()
            # A line beginning with "Artículo 79..." inside Article 66 is
            # commonly a cross-reference, not a new top-level article.  Main
            # provisions progress sequentially; quoted/referenced provisions
            # stay in the current article body.  A BIS/TER variant of the same
            # number is the only valid non-incrementing heading.
            if next_number != current_number + 1 and not next_bis:
                m = None
        if m:
            if current:
                articles.append(current)
            num = m.group("num")
            bis = m.group("bis") or ""
            title = (m.group("title") or "").strip().rstrip(":")
            rest = (m.group("rest") or "").strip()
            body = f"{title}: {rest}".strip() if title and rest else (rest or title or "")
            current = Article(number=num, bis=bis, title=title or "", text=body)
            i += 1
        else:
            if current and line:
                current.text = (current.text + "\n" + line).strip()
    if current:
        articles.append(current)
    return articles


def _normalize_year(yy: str) -> str | None:
    if not yy:
        return None
    if len(yy) == 4:
        return yy
    if len(yy) == 3:
        # e.g. "991" -> "1991", "009" -> "2009"
        return "1" + yy if yy[0] == "9" else ("2" + yy if int(yy) < 100 else "1" + yy)
    if len(yy) == 2:
        v = int(yy)
        return ("20" + yy) if v < 50 else ("19" + yy)
    return yy


def extract_norm_references(text: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for m in _NORM_REF.finditer(text or ""):
        if m.group(2):  # decreto
            refs.append({"type": "decreto", "number": m.group(2), "year": _normalize_year(m.group(3)), "text": m.group(1)})
        elif m.group(4):  # ley
            refs.append({"type": "ley", "number": m.group(4), "year": m.group(5), "text": m.group(0)})
        elif m.group(6):  # ordenanza
            refs.append({"type": "ordenanza", "number": m.group(6), "year": None, "text": m.group(0)})
    return refs


def detect_relations(text: str, from_norm_id: str, evidence: str = "") -> list[dict[str, Any]]:
    """Deterministic detection of normative relations based on keywords + references."""
    relations: list[dict[str, Any]] = []
    lower = (text or "").lower()
    refs = extract_norm_references(text)
    for rel, keywords in RELATION_KEYWORDS:
        for kw in keywords:
            idx = lower.find(kw)
            if idx == -1:
                continue
            # Find a norm reference near the keyword (within 400 chars)
            window = text[max(0, idx - 60): idx + 400]
            for ref in refs:
                if ref.get("text") and ref["text"].lower() in window.lower():
                    target_id = build_target_id(ref)
                    if target_id and target_id != from_norm_id:
                        relations.append({
                            "from": from_norm_id,
                            "relation": rel,
                            "to": target_id,
                            "status": "candidate",
                            "evidence_source": evidence,
                        })
                    break
    # de-duplicate
    seen = set()
    unique = []
    for r in relations:
        key = (r["from"], r["relation"], r["to"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def build_target_id(ref: dict[str, Any]) -> str | None:
    from .identity import build_norm_id
    if ref.get("type") == "ley":
        return f"ley:{ref['number']}:{ref['year'] or 'unknown'}"
    return build_norm_id(ref["type"], ref["number"], ref["year"])
