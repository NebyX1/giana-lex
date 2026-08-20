import re
from uuid import uuid4

from app.extensions import db
from legal.domain.models import DraftParagraph, ResolutionDraft
from legal.evidence.service import citation_gate
from legal.infrastructure.models import (
    ClaimEvidenceLinkRecord,
    DraftVersionRecord,
    FactAssertionRecord,
    HumanTaskRecord,
    LegalPropositionRecord,
    ReviewFindingRecord,
)
from legal.workflows.loader import WorkflowPack


def compose_draft(case_id: str, pack: WorkflowPack, corpus_snapshot_id: str) -> DraftVersionRecord:
    facts = FactAssertionRecord.query.filter_by(case_id=case_id, verification_status="confirmed_by_user").all()
    propositions = LegalPropositionRecord.query.filter_by(case_id=case_id, status="verified").all()
    fact_ids = [item.id for item in facts]
    proposition_ids = [item.id for item in propositions]
    evidence_ids = []
    for proposition in propositions:
        evidence_ids.extend(
            item.evidence_id for item in ClaimEvidenceLinkRecord.query.filter_by(
                case_id=case_id, proposition_id=proposition.id
            ).all()
        )
    values = {item.key: item.value_json.get("value") for item in facts}
    legal_text = " ".join(item.text for item in propositions)
    grounded = DraftParagraph(
        text=legal_text, fact_ids=fact_ids, proposition_ids=proposition_ids, evidence_ids=evidence_ids
    )
    draft = ResolutionDraft(
        title="BORRADOR - Proyecto de resolucion",
        expediente=str(values.get("expediente")) if values.get("expediente") else None,
        issuing_body="Intendencia Departamental de Lavalleja",
        vistos=[DraftParagraph(text="Vistas las actuaciones del expediente.", fact_ids=fact_ids)],
        resultandos=[DraftParagraph(text="Resultan los hechos confirmados incorporados al expediente.", fact_ids=fact_ids)],
        considerandos=[grounded], legal_basis=[grounded],
        operative_articles=[DraftParagraph(
            text="Articulo 1. Someter el presente proyecto a revision humana, sin adoptar decision administrativa.",
            fact_ids=fact_ids, proposition_ids=proposition_ids, evidence_ids=evidence_ids,
        )],
        notifications=["Notificaciones sujetas a determinacion y revision humana."],
        signature_block=None,
    )
    errors = validate_draft(draft, pack, case_id)
    latest = DraftVersionRecord.query.filter_by(case_id=case_id).order_by(DraftVersionRecord.version.desc()).first()
    record = DraftVersionRecord(
        id=str(uuid4()), case_id=case_id, version=1 if latest is None else latest.version + 1,
        corpus_snapshot_id=corpus_snapshot_id, status="grounded_draft" if not errors else "blocked",
        draft_json=draft.model_dump(mode="json"), validation_json={"errors": errors},
    )
    db.session.add(record)
    db.session.flush()
    return record


def validate_draft(draft: ResolutionDraft, pack: WorkflowPack, case_id: str) -> list[str]:
    errors = citation_gate(case_id)
    data = draft.model_dump()
    for section in pack.required_sections:
        if not data.get(section):
            errors.append(f"missing_section:{section}")
    serialized = draft.model_dump_json()
    if re.search(r"\[[A-Z][A-Z _/-]+\]", serialized):
        errors.append("unresolved_placeholder")
    if not draft.title.startswith("BORRADOR"):
        errors.append("missing_draft_mark")
    proposition_ids = {item.id for item in LegalPropositionRecord.query.filter_by(case_id=case_id, status="verified")}
    for paragraph in draft.considerandos + draft.legal_basis + draft.operative_articles:
        if paragraph.proposition_ids and not set(str(item) for item in paragraph.proposition_ids).issubset(proposition_ids):
            errors.append("unknown_proposition")
    return errors


def compliance_review(case_id: str, draft: DraftVersionRecord) -> list[ReviewFindingRecord]:
    findings = []
    for error in draft.validation_json.get("errors", []):
        finding = ReviewFindingRecord(
            id=str(uuid4()), case_id=case_id, draft_version_id=draft.id, reviewer_type="deterministic",
            severity="critical", category="validation", blocks_output=True,
            finding_json={"description": error, "suggested_action": "Corregir antes de continuar."},
        )
        db.session.add(finding)
        findings.append(finding)
    if not findings:
        db.session.add(HumanTaskRecord(
            id=str(uuid4()), case_id=case_id, task_type="review_draft", status="open",
            payload_json={"draft_version_id": draft.id},
        ))
    db.session.flush()
    return findings
