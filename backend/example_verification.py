"""Conservative, reproducible checks of a draft before approval.

Editorial examples guide structure. They cannot certify facts or applicable law.
"""
from __future__ import annotations

import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field

from example_catalog import norm


class Evidence(BaseModel):
    source_kind: Literal["draft", "case_fact", "official_norm", "editorial_example"]
    source_id: str
    revision_id: str | None = None
    location: str
    excerpt: str
    observation: Literal["observed", "inferred", "missing"] = "observed"


class Finding(BaseModel):
    id: str
    category: str
    severity: Literal["info", "warning", "critical"]
    location: str
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    action: str
    needs_document: bool = False
    resolved: bool = False
    resolution_note: str | None = None


class VerificationReport(BaseModel):
    draft_revision: int
    draft_hash: str
    summary: str
    coverage: list[str]
    examples: list[dict]
    similarities: list[str]
    differences: list[str]
    pending_facts: list[str]
    normative_status: dict
    findings: list[Finding]
    proposed_changes: list[str]
    status: Literal["sin_observaciones_materiales", "con_observaciones", "informacion_insuficiente"]
    duration_ms: float
    context_status: Literal["complete", "unavailable", "not_run"] = "not_run"
    corpus_version: str | None = None


def _excerpt(text: str, span: tuple[int, int], radius: int = 55) -> str:
    return text[max(0, span[0] - radius):min(len(text), span[1] + radius)].replace("\n", " ")


def _finding(category, severity, location, explanation, excerpt, action, *, needs_document=False):
    identifier = sha256(f"{category}|{location}|{excerpt}".encode()).hexdigest()[:12]
    return Finding(id=identifier, category=category, severity=severity, location=location, explanation=explanation,
                   evidence=[Evidence(source_kind="draft", source_id="current_draft", location=location, excerpt=excerpt)],
                   action=action, needs_document=needs_document)


def _identifiers(text: str, label: str):
    pattern = "padr[oó�]n" if label == "padron" else label
    return [(match.group(1), match.span()) for match in re.finditer(
        rf"\b{pattern}[^0-9\n]{{0,35}}([0-9][0-9./-]*)", text, re.IGNORECASE)]


def _amounts(text: str):
    values = []
    for match in re.finditer(r"(?:\$|USD|UYU|US\$)\s*([0-9][0-9.,]*)", text, re.IGNORECASE):
        raw = match.group(1)
        normalized = raw.replace(".", "").replace(",", ".") if "," in raw else raw.replace(".", "") if raw.count(".") and len(raw.rsplit(".", 1)[-1]) == 3 else raw
        try:
            values.append((Decimal(normalized), match.span(), raw))
        except InvalidOperation:
            pass
    return values


def verify_draft(draft: str, facts: dict, references: list[dict], draft_revision: int, corpus_version: str | None = None,
                 resolved: dict[str, str] | None = None) -> VerificationReport:
    started = time.perf_counter()
    findings: list[Finding] = []
    draft_hash = sha256(draft.encode("utf-8")).hexdigest()
    compact = norm(draft)
    coverage = ["identificadores y padrones", "expediente", "importes numéricos", "fechas ISO", "secuencia de numerales",
                "referencias internas", "objeto y motivación básica", "alcance editorial de ejemplos"]

    for label in ("padron", "expediente"):
        occurrences = _identifiers(draft, label)
        unique = {re.sub(r"\W", "", value) for value, _ in occurrences}
        if len(unique) > 1:
            excerpt = "; ".join(value for value, _ in occurrences[:8])
            findings.append(_finding(label, "critical", f"menciones de {label}",
                                     f"Aparecen identificadores distintos de {label}; no se puede decidir cuál corresponde al caso.",
                                     excerpt, "Cotejar el expediente o padrón original y corregir las menciones", needs_document=True))
        fact_value = str(facts.get(label) or facts.get(label + "_numero") or "").strip()
        if fact_value and occurrences and all(re.sub(r"\W", "", fact_value) != re.sub(r"\W", "", value) for value, _ in occurrences):
            findings.append(_finding(label + "_caso", "critical", f"menciones de {label}",
                                     f"El {label} del borrador no coincide con el dato proporcionado para el caso.",
                                     occurrences[0][0], "Confirmar el documento fuente del caso", needs_document=True))

    amounts = _amounts(draft)
    unit_amounts = []
    for match in re.finditer(r"\bUR\s*([0-9][0-9.,]*)", draft, re.IGNORECASE):
        raw = match.group(1).rstrip(".,")
        try:
            unit_amounts.append((Decimal(raw.replace(".", "").replace(",", ".")), raw))
        except InvalidOperation:
            pass
    if len({value for value, _ in unit_amounts}) > 1:
        findings.append(_finding("importe_ur", "warning", "importes en UR",
                                 "Aparecen importes diferentes en UR; comprobar si describen la misma operación.",
                                 ", ".join(raw for _, raw in unit_amounts[:8]),
                                 "Conciliar importes con las actuaciones y la liquidación", needs_document=True))
    fact_amount = facts.get("importe") or facts.get("monto") or facts.get("remuneracion")
    if fact_amount and amounts:
        try:
            expected = Decimal(str(fact_amount).replace(".", "").replace(",", "."))
            if any(value != expected for value, _, _ in amounts):
                findings.append(_finding("importe", "critical", "importes del borrador", "Un importe difiere del dato del caso.",
                                         ", ".join(raw for _, _, raw in amounts[:8]), "Revisar importe y moneda contra el expediente", needs_document=True))
        except InvalidOperation:
            pass
    dates = [(match.group(0), match.span()) for match in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", draft)]
    for value, span in dates:
        try:
            date.fromisoformat(value)
        except ValueError:
            findings.append(_finding("fecha", "critical", f"carácter {span[0]}", "Fecha calendario inválida", value,
                                     "Verificar la fecha del acto"))

    numerals = [int(match.group(1)) for match in re.finditer(r"(?m)^\s*(\d{1,2})\s*[.)-]\s+", draft)]
    if numerals and numerals != list(range(numerals[0], numerals[0] + len(numerals))):
        findings.append(_finding("numerales", "warning", "sección dispositiva", "Los numerales no siguen una secuencia continua.",
                                 ", ".join(map(str, numerals)), "Corregir numeración o justificar la remisión"))
    headings = {name: bool(re.search(r"\b" + name + r"\b", compact)) for name in ("visto", "resultando", "considerando", "atento", "resuelve")}
    if not headings["resuelve"] and not re.search(r"\b(resolver|dispone|disponer)\b", compact):
        findings.append(_finding("dispositivo", "critical", "borrador completo", "No se identifica una decisión dispositiva verificable.",
                                 draft[:120], "Explicitar el efecto que dispone el acto"))
    if headings["resuelve"] and not (headings["considerando"] or headings["resultando"] or headings["visto"]):
        findings.append(_finding("motivacion", "warning", "antes de RESUELVE", "No se identifica una motivación concreta en el borrador.",
                                 draft[:120], "Añadir hechos y motivos comprobados del caso"))
    if "prorroga" in compact and not any(term in compact for term in ("plazo", "hasta", "vencimiento")):
        findings.append(_finding("plazo", "warning", "prórroga", "La prórroga no explicita plazo o vencimiento.",
                                 "prórroga", "Precisar término inicial y final con respaldo del expediente"))
    if "prorroga" in compact and not any(term in compact for term in ("porque", "debido", "circunstancia", "razon excepcional", "fundament")):
        findings.append(_finding("motivacion_prorroga", "warning", "motivación de la prórroga",
                                 "No se expone una circunstancia concreta que justifique la prórroga.", "prórroga",
                                 "Agregar la causa acreditada en el expediente, si existe", needs_document=True))
    if "clausura" in compact and "paralizacion" in compact:
        findings.append(_finding("efecto", "critical", "efecto decidido", "Clausura y paralización aparecen como efectos distintos; verificar cuál se decidió.",
                                 "clausura / paralización", "Cotejar el acto y unificar el efecto", needs_document=True))
    citations = re.findall(r"\b(?:decreto|resolucion)(?:\s+departamental)?\s*(?:n[º°o.�]*)?\s*(\d{2,5})\s*/\s*(\d{2,4})", compact)
    by_number = {}
    for number, year in citations:
        by_number.setdefault(number, set()).add(year)
    for number, years in by_number.items():
        if len(years) > 1:
            findings.append(_finding("cita_interna", "critical", "citas de actos",
                                     f"El acto {number} aparece con años distintos: {', '.join(sorted(years))}.",
                                     f"{number}/" + ", ".join(sorted(years)),
                                     "Cotejar la identificación del acto en la fuente oficial", needs_document=True))
    normalized_articles = re.sub(r"\bD\.\s+", "D.", draft)
    for prefix, start, end in re.findall(r"\b([A-Z]\.[0-9.]+\.)(\d+)\s+a\s+[A-Z]\.[0-9.]+\.(\d+)", normalized_articles):
        observed = [int(value) for value in re.findall(r"(?i)\bart.culo\s+" + re.escape(prefix) + r"(\d+)\b", normalized_articles)]
        if observed and max(observed) < int(end):
            findings.append(_finding("articulado", "warning", "rango de artículos",
                                     f"El rango anuncia hasta {prefix}{end}, pero el texto recuperado llega a {prefix}{max(observed)}.",
                                     f"{prefix}{start} a {prefix}{end}", "Comprobar anexo o articulado completo", needs_document=True))

    # Existing citation metadata is historical evidence about the example, not a fresh legal check.
    cited = [citation for ref in references for citation in ref.get("normativa_citada", []) if isinstance(citation, dict)]
    normative = {"existence": "not_checked", "content": "not_checked", "temporal_version": "not_checked",
                 "territorial_applicability": "not_checked", "cited_in_examples": cited[:12]}
    if cited:
        findings.append(_finding("normativa", "warning", "fundamentos normativos",
                                 "Las citas de antecedentes no acreditan vigencia ni aplicabilidad de la norma al nuevo caso.",
                                 "; ".join(str(item.get("referencia", "")) for item in cited[:3]),
                                 "Aportar o comprobar el texto normativo aplicable a la fecha y territorio del caso", needs_document=True))
    else:
        findings.append(_finding("normativa", "warning", "fundamentos normativos",
                                 "No hay texto normativo comprobado para este caso.", "Sin fuente normativa cotejada",
                                 "Aportar norma nacional y departamental pertinente, si corresponde", needs_document=True))

    pending = []
    if not facts:
        pending.append("Documentos y hechos del expediente para cotejar identidades, importes y competencia")
    if "competencia" not in facts and "normativa" not in facts:
        pending.append("Acto de competencia o delegación aplicable")
    if resolved:
        for finding in findings:
            note = resolved.get(finding.id)
            if finding.severity != "critical" and isinstance(note, str) and note.strip():
                finding.resolved = True
                finding.resolution_note = note.strip()[:1000]
    active = [finding for finding in findings if not finding.resolved]
    status = "con_observaciones" if any(f.severity == "critical" for f in active) else "informacion_insuficiente" if pending or any(f.needs_document for f in active) else "con_observaciones" if active else "sin_observaciones_materiales"
    examples = [{"id": ref["id"], "revision_id": ref["revision_id"], "scope": ref["scope"], "title": ref["title"],
                 "match_class": ref["match_class"], "reasons": ref["reasons"], "differences": ref["differences"]} for ref in references]
    return VerificationReport(draft_revision=draft_revision, draft_hash=draft_hash,
                              summary={"con_observaciones": "Con observaciones", "informacion_insuficiente": "Información insuficiente",
                                       "sin_observaciones_materiales": "Sin observaciones materiales en los controles ejecutados"}[status],
                              coverage=coverage, examples=examples,
                              similarities=[reason for ref in references for reason in ref["reasons"]][:12],
                              differences=[reason for ref in references for reason in ref["differences"]][:12],
                              pending_facts=pending, normative_status=normative, findings=findings,
                              proposed_changes=[f.action for f in active], status=status,
                              duration_ms=round((time.perf_counter() - started) * 1000, 2), corpus_version=corpus_version)
