from __future__ import annotations

import json
import re

from documents.legal_references import extract_legal_references

from .evidence_ledger import EvidenceLedger
from .schemas import GateResult, ValidationIssue, VerificationResult
from .state import TaskState


LEGAL_ASSERTION_RE = re.compile(
    r"\b(?:la\s+intendencia|el\s+gobierno\s+departamental).{0,100}?\b(?:es\s+competente|tiene\s+competencia|est[aá]\s+facultad[ao]|puede|deber[aá])\b",
    re.IGNORECASE | re.DOTALL,
)
PLACEHOLDER_RE = re.compile(r"\[(?:DATO PENDIENTE[^\]]*|NORMA[^\]]*|FECHA|MONTO|NOMBRE)[^\]]*\]", re.IGNORECASE)
NUMERAL_RE = re.compile(r"(?m)^\s*(\d+)°\.-")
ARTICLE_RE = re.compile(r"(?mi)^\s*Art[ií]culo\s+(\d+)°\.-")


class Verifier:
    @staticmethod
    def normalize_draft(state: TaskState, draft: str) -> str:
        """Canonicalize one model-produced JSON object without repairing its content."""
        if state.task_type == "document_generation" and state.document_type == "contract":
            def replace_pending(match: re.Match[str]) -> str:
                label = match.group(0).strip("[]").replace("DATO PENDIENTE:", "").strip()
                return f"Pendiente de confirmación antes de la firma: {label}"

            return PLACEHOLDER_RE.sub(replace_pending, draft)
        if state.task_type != "document_generation" or state.document_type != "resolution":
            return draft
        candidate = draft.strip()
        if candidate.startswith("```"):
            first_newline = candidate.find("\n")
            if first_newline >= 0:
                candidate = candidate[first_newline + 1:]
            if candidate.rstrip().endswith("```"):
                candidate = candidate.rstrip()[:-3].rstrip()
        start = candidate.find("{")
        if start < 0:
            return draft
        try:
            payload, _end = json.JSONDecoder().raw_decode(candidate[start:])
        except json.JSONDecodeError:
            return draft
        if not isinstance(payload, dict):
            return draft
        return json.dumps(payload, ensure_ascii=False)

    def verify(self, state: TaskState, ledger: EvidenceLedger, draft: str, strict: bool = False) -> VerificationResult:
        issues: list[ValidationIssue] = []
        for token in ("TODO", "FIXME"):
            # Technical markers are uppercase. Treating normal Spanish "todo"
            # as TODO made valid contracts fail validation.
            if re.search(rf"\b{token}\b", draft):
                issues.append(ValidationIssue("placeholder_leak", "high", f"El borrador contiene {token}."))
        if "lorem ipsum" in draft.casefold():
            issues.append(ValidationIssue("placeholder_leak", "high", "El borrador contiene Lorem ipsum."))
        if PLACEHOLDER_RE.search(draft):
            issues.append(ValidationIssue("placeholder_leak", "high", "El borrador contiene campos sin resolver."))
        issues.extend(self._structured_output_issues(state, draft))
        issues.extend(self._structure_issues(state, draft))
        issues.extend(self._citation_issues(ledger, draft))
        if state.task_type == "correction" and "podrá" in state.user_request.casefold() and "deberá" in draft.casefold():
            issues.append(ValidationIssue("dangerous_modality_change", "high", "La correccion cambio 'podrá' por 'deberá'."))
        if LEGAL_ASSERTION_RE.search(draft) and not ledger.authoritative_items:
            issues.append(ValidationIssue("unsupported_legal_claim", "high", "Afirmacion material de competencia sin evidencia autoritativa."))
        status = "fail" if any(issue.severity == "high" for issue in issues) else "warn" if issues and strict else "pass"
        return VerificationResult(status, issues)

    @staticmethod
    def _structured_output_issues(state: TaskState, draft: str) -> list[ValidationIssue]:
        if state.task_type != "document_generation" or state.document_type != "resolution":
            return []
        try:
            payload = json.loads(draft)
        except (TypeError, json.JSONDecodeError):
            return [ValidationIssue("structured_output_error", "high", "La resolucion final debe ser un objeto JSON valido.")]
        required = {
            "document_type", "title", "number", "place", "date", "visto",
            "resultandos", "considerandos", "atento", "resuelve", "notes",
        }
        if not isinstance(payload, dict) or not required.issubset(payload):
            return [ValidationIssue("structured_output_error", "high", "Faltan campos obligatorios del borrador estructurado.")]
        if not all(isinstance(payload.get(key), list) for key in ("resultandos", "considerandos", "resuelve", "notes")):
            return [ValidationIssue("structured_output_error", "high", "Las secciones repetibles del borrador deben ser listas.")]
        if not payload["resuelve"] or any(
            not isinstance(item, dict)
            or not str(item.get("number", "")).strip()
            or not str(item.get("text", "")).strip()
            for item in payload["resuelve"]
        ):
            return [ValidationIssue("structured_output_error", "high", "Cada numeral resolutivo debe incluir number y text.")]
        return []

    @staticmethod
    def _structure_issues(state: TaskState, draft: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if state.document_type == "resolution":
            for heading in ("VISTO", "ATENTO", "RESUELVE"):
                if heading not in draft.upper():
                    issues.append(ValidationIssue("missing_section", "high", f"Falta {heading}."))
            numerals = [int(value) for value in NUMERAL_RE.findall(draft)]
            if numerals and numerals != list(range(1, len(numerals) + 1)):
                issues.append(ValidationIssue("invalid_numbering", "high", "Numerales no consecutivos."))
        if state.document_type == "decree":
            articles = [int(value) for value in ARTICLE_RE.findall(draft)]
            if not articles or articles != list(range(1, len(articles) + 1)):
                issues.append(ValidationIssue("invalid_articles", "high", "Articulos ausentes o no consecutivos."))
        return issues

    @staticmethod
    def _citation_issues(ledger: EvidenceLedger, draft: str) -> list[ValidationIssue]:
        references = extract_legal_references(draft)
        if not references:
            return []
        corpus = " ".join(
            f"{item.title or ''} {item.citation or ''} {item.fragment}"
            for item in ledger.authoritative_items
        ).casefold()
        issues = []
        for reference in references:
            components = reference.get("components") or {}
            # Numbered clauses/articles inside the generated document are not
            # citations unless they explicitly name an external source.
            if reference.get("kind") == "articulo" and not components.get("reference"):
                continue
            text = str(reference["text"])
            tokens = [token for token in re.findall(r"\w+", text.casefold()) if any(char.isdigit() for char in token)]
            if tokens and not all(token in corpus for token in tokens):
                issues.append(ValidationIssue("citation_not_in_evidence", "high", "Referencia no encontrada en evidencia autoritativa.", text))
        return issues


class QualityGates:
    def evaluate(self, state: TaskState, ledger: EvidenceLedger, verification: VerificationResult) -> list[GateResult]:
        needs_authority = state.task_type in {"legal_research", "document_generation"} and bool(state.legal_questions)
        return [
            GateResult("task_classified", bool(state.task_type), "La tarea requiere clasificacion."),
            GateResult("required_evidence", not needs_authority or bool(ledger.authoritative_items), "Falta evidencia autoritativa."),
            GateResult("unsupported_claims", not any(issue.issue_type == "unsupported_legal_claim" for issue in verification.issues)),
            GateResult("document_structure", not any(issue.issue_type in {"missing_section", "invalid_numbering", "invalid_articles", "structured_output_error"} for issue in verification.issues)),
            GateResult("dangerous_inconsistencies", not any(issue.severity == "high" for issue in verification.issues)),
            GateResult("final_ready", verification.passed),
        ]
