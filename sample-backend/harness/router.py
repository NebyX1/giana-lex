from __future__ import annotations

import re

from .schemas import RoutingDecision


class HarnessRouter:
    """Closed, deterministic routing before the existing skill prompt is loaded."""

    def route(self, request: str, requested_skills: list[str], available_skills: set[str]) -> RoutingDecision:
        text = request.casefold()
        generation_action = bool(re.search(r"\b(redact|prepar|proyect|crea|arm)\w*", text))
        resolution = bool(re.search(r"\bresoluci[oó]n\w*", text))
        decree = bool(re.search(r"\bdecreto\w*", text))
        legal_report = bool(re.search(r"\binforme\s+jur[ií]dico\w*", text))
        administrative_note = bool(re.search(r"\bnota\s+administrativa\w*", text))
        contract = bool(re.search(
            r"\b(?:contrat(?:o|os|aci[oó]n|aciones)|arrendamiento\s+de\s+obra)\b",
            text,
        ))
        document_generation = generation_action and (resolution or decree or legal_report or administrative_note or contract)
        correction = bool(re.search(r"\b(correg|ortograf|estilo)\w*", text))
        audit = bool(re.search(r"\b(audit|compliance|procedim|revis)\w*", text))
        legal_question = bool(re.search(r"\b(competenc|jur[ií]dic|normativ|ley|decreto|facultad|puede)\w*", text))
        budget_matter = bool(re.search(r"\b(transposici[oó]n|presupuest|partida|rubro|cr[eé]dito|fondos?)\w*", text))
        retrieval = (
            document_generation
            or legal_question
            or budget_matter
            or bool(re.search(r"\b(busca|investig|verific|fuente)\w*", text))
        )

        if correction and not retrieval and not document_generation:
            inferred = "corrector-estilo-ortografia-legal"
            task_type = "correction"
        elif audit and not generation_action:
            inferred = "auditor-compliance"
            task_type = "procedural_review"
        elif document_generation:
            inferred = "redactor-legal"
            task_type = "document_generation"
        elif retrieval:
            inferred = "investigador-normativo"
            task_type = "legal_research"
        else:
            inferred = "analista-legal"
            task_type = "general"

        valid_requested = tuple(dict.fromkeys(name for name in requested_skills if name in available_skills))
        # A stale UI selection must not override an unambiguous legal workflow.
        # Keep explicit user preference only for genuinely general requests.
        if inferred != "analista-legal" and inferred in available_skills:
            primary = inferred
        else:
            primary = valid_requested[0] if valid_requested else inferred
        if primary not in available_skills:
            primary = "analista-legal"
        secondary = valid_requested[1:2] if valid_requested and valid_requested[0] == primary else ()

        subtype = None
        variant = None
        if "adjudic" in text:
            subtype = "adjudicacion"
        elif "exoner" in text:
            subtype = "exoneracion"
            variant = "junta" if "junta" in text else "directa" if "direct" in text else None
        elif "conveni" in text:
            subtype = "convenio"
        elif contract and re.search(r"arrendamiento\s+de\s+obra", text):
            subtype = "arrendamiento_obra"
            variant = "arrendamiento_obra"
        elif "contrat" in text:
            subtype = "contratacion"

        if resolution:
            document_type = "resolution"
        elif decree:
            document_type = "decree"
        elif legal_report:
            document_type = "legal_report"
        elif administrative_note:
            document_type = "administrative_note"
        elif contract:
            document_type = "contract"
        else:
            document_type = None

        high_risk = document_generation or (legal_question and "competenc" in text)
        complex_task = document_generation or (retrieval and (audit or text.count("?") > 1))
        return RoutingDecision(
            primary_skill=primary,
            secondary_skills=secondary,
            needs_retrieval=retrieval,
            needs_template=document_generation and document_type in {"resolution", "decree", "legal_report", "contract"},
            task_type=task_type,
            document_type=document_type,
            subtype=subtype,
            variant=variant,
            complexity="complex" if complex_task else "simple",
            legal_risk="high" if high_risk else "low",
        )

    def plan(self, decision: RoutingDecision) -> list[str]:
        if decision.task_type == "correction":
            return ["correct", "validate"]
        steps = ["classify"]
        if decision.needs_retrieval:
            steps.append("retrieve_authority")
        if decision.needs_template:
            steps.append("select_template")
        steps.append("draft" if decision.needs_template else "answer")
        steps.append("validate")
        return steps
