from datetime import date, datetime
from hashlib import sha256
from json import dumps
from uuid import uuid4
from urllib.parse import urlsplit

from app.extensions import db
from legal.domain.models import LegalIssue, VerifiedAuthorityInput
from legal.infrastructure.models import (
    AuthorityVerificationRecord,
    CandidateAuthorityRecord,
    ClaimEvidenceLinkRecord,
    CorpusSnapshotRecord,
    EvidenceSpanRecord,
    LegalPropositionRecord,
)


CONCLUSIVE_SOURCE_CLASSES = frozenset({"official_primary", "official_secondary", "institutional"})


def create_corpus_snapshot(case_id: str, pack_id: str, pack_version: int) -> CorpusSnapshotRecord:
    manifest = {
        "national_registry": "runtime",
        "departmental_registry": "runtime",
        "workflow_pack_id": pack_id,
        "workflow_pack_version": pack_version,
    }
    serialized = dumps(manifest, sort_keys=True, separators=(",", ":"))
    latest = CorpusSnapshotRecord.query.filter_by(case_id=case_id).order_by(CorpusSnapshotRecord.version.desc()).first()
    record = CorpusSnapshotRecord(
        id=str(uuid4()), case_id=case_id, version=1 if latest is None else latest.version + 1,
        manifest_json=manifest, checksum=sha256(serialized.encode("utf-8")).hexdigest(),
    )
    db.session.add(record)
    db.session.flush()
    return record


def verify_and_record(case_id: str, issues: list[LegalIssue], candidates: list[VerifiedAuthorityInput]) -> tuple[list, list[str]]:
    issue_ids = {item.issue_id for item in issues}
    accepted = []
    rejected = []
    today = date.today()
    for candidate in candidates:
        candidate_record = CandidateAuthorityRecord.query.filter_by(
            case_id=case_id, raw_reference=candidate.source_id
        ).first()
        if candidate_record is None:
            candidate_record = CandidateAuthorityRecord(
                id=str(uuid4()), case_id=case_id, raw_reference=candidate.source_id,
                normalized_norm_id=candidate.norm_id, article=candidate.article,
                discovery_reason="related", verification_status="unverified",
            )
            db.session.add(candidate_record)
            db.session.flush()
        reasons = []
        if candidate.issue_id not in issue_ids:
            reasons.append("unknown_issue")
        if candidate.source_class not in CONCLUSIVE_SOURCE_CLASSES:
            reasons.append("source_class_not_conclusive")
        if not candidate.authenticity_verified:
            reasons.append("authenticity_unverified")
        if not candidate.applicability_verified:
            reasons.append("applicability_unverified")
        if not candidate.active:
            reasons.append("inactive_source")
        if not candidate.source_id.strip() or candidate.source_version in {"", "unknown"}:
            reasons.append("incomplete_source_metadata")
        if not candidate.norm_id or len(candidate.exact_text.strip()) < 20:
            reasons.append("incomplete_official_text")
        if candidate.source_url:
            hostname = (urlsplit(candidate.source_url).hostname or "").lower()
            if not (hostname.endswith("impo.com.uy") or hostname.endswith("lavalleja.gub.uy")
                    or hostname.endswith("juntalavalleja.gub.uy")):
                reasons.append("untrusted_official_origin")
        if candidate.jurisdiction.lower() not in {"lavalleja", "uruguay", "nacional"}:
            reasons.append("wrong_jurisdiction")
        if candidate.effective_from and candidate.effective_from > today:
            reasons.append("not_yet_effective")
        if candidate.effective_to and candidate.effective_to < today:
            reasons.append("superseded")
        verification = AuthorityVerificationRecord(
            id=str(uuid4()), case_id=case_id, candidate_authority_id=candidate_record.id,
            issue_id=candidate.issue_id,
            status="rejected" if reasons else "accepted",
            result_json={"candidate": candidate.model_dump(mode="json"), "limitations": reasons},
        )
        db.session.add(verification)
        if reasons:
            candidate_record.verification_status = "not_found" if "authenticity_unverified" in reasons else "verified_not_applicable"
            candidate_record.verified_at = datetime.utcnow()
            rejected.append(candidate.source_id)
            continue
        checksum = sha256(candidate.exact_text.encode("utf-8")).hexdigest()
        evidence = EvidenceSpanRecord(
            id=str(uuid4()), case_id=case_id, source_id=candidate.source_id,
            source_version=candidate.source_version, source_class=candidate.source_class,
            jurisdiction=candidate.jurisdiction, norm_id=candidate.norm_id, article=candidate.article,
            exact_text=candidate.exact_text, source_url=candidate.source_url, checksum=checksum,
            effective_from=candidate.effective_from, effective_to=candidate.effective_to,
            active=True, verified_at=datetime.utcnow(), verification_method="independent_provider_assertions_v1",
        )
        proposition = LegalPropositionRecord(
            id=str(uuid4()), case_id=case_id, issue_id=candidate.issue_id,
            text=candidate.proposition, applies_to_fact_ids_json=[], confidence="1.0",
            limitations_json=[], status="verified",
        )
        db.session.add_all([evidence, proposition])
        candidate_record.verification_status = "verified_current"
        candidate_record.verified_source_id = evidence.source_id
        candidate_record.verified_at = datetime.utcnow()
        db.session.flush()
        db.session.add(ClaimEvidenceLinkRecord(
            id=str(uuid4()), case_id=case_id, proposition_id=proposition.id, evidence_id=evidence.id
        ))
        accepted.append(proposition)
    db.session.flush()
    covered = {item.issue_id for item in accepted}
    missing = [item.issue_id for item in issues if item.issue_id not in covered]
    return accepted, missing


def citation_gate(case_id: str) -> list[str]:
    errors = []
    propositions = LegalPropositionRecord.query.filter_by(case_id=case_id, status="verified").all()
    for proposition in propositions:
        links = ClaimEvidenceLinkRecord.query.filter_by(case_id=case_id, proposition_id=proposition.id).all()
        if not links:
            errors.append(f"unlinked_proposition:{proposition.id}")
        for link in links:
            evidence = db.session.get(EvidenceSpanRecord, link.evidence_id)
            if evidence is None or evidence.case_id != case_id:
                errors.append(f"foreign_or_missing_evidence:{link.evidence_id}")
                continue
            if evidence.source_class not in CONCLUSIVE_SOURCE_CLASSES or not evidence.active:
                errors.append(f"inadmissible_evidence:{evidence.id}")
            if not evidence.exact_text or sha256(evidence.exact_text.encode("utf-8")).hexdigest() != evidence.checksum:
                errors.append(f"checksum_mismatch:{evidence.id}")
    return errors
