from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.extensions import db
from legal.infrastructure.models import (
    FactAssertionRecord,
    ConversationDigestRecord,
    InstitutionalProfileVersionRecord,
    LegalPropositionRecord,
    MemoryProposalRecord,
    OperationalMemoryRecord,
)
import yaml


def assemble_context(case_id: str) -> dict:
    facts = FactAssertionRecord.query.filter_by(case_id=case_id, verification_status="confirmed_by_user").all()
    propositions = LegalPropositionRecord.query.filter_by(case_id=case_id, status="verified").all()
    return {
        "relevant_facts": [{"id": item.id, "key": item.key, "value": item.value_json} for item in facts],
        "verified_propositions": [{"id": item.id, "issue_id": item.issue_id, "text": item.text} for item in propositions],
        "operational_memory_is_citable": False,
    }


def decide_proposal(proposal: MemoryProposalRecord, user_id: int, approve: bool, reason: str | None = None):
    if proposal.status != "pending":
        if approve and proposal.status == "approved":
            return OperationalMemoryRecord.query.filter_by(proposal_id=proposal.id).one()
        if not approve and proposal.status == "rejected":
            return None
        raise ValueError("Memory proposal has already been decided differently")
    proposal.status = "approved" if approve else "rejected"
    proposal.decision_by_user_id = user_id
    proposal.decision_reason = reason
    proposal.decided_at = datetime.utcnow()
    if approve:
        memory = OperationalMemoryRecord(
            id=str(uuid4()), proposal_id=proposal.id, statement=proposal.statement,
            scope=proposal.scope, scope_ref=proposal.scope_ref, active=True, approved_by_user_id=user_id,
        )
        db.session.add(memory)
        db.session.flush()
        return memory
    db.session.flush()
    return None


def create_conversation_digest(case_id: str, digest: str, message_refs: list[str], pending: list[str]):
    latest = ConversationDigestRecord.query.filter_by(case_id=case_id).order_by(
        ConversationDigestRecord.version.desc()
    ).first()
    record = ConversationDigestRecord(
        id=str(uuid4()), case_id=case_id, version=1 if latest is None else latest.version + 1,
        digest=digest, message_refs_json=message_refs, pending_json=pending,
    )
    db.session.add(record)
    db.session.flush()
    return record


def load_institutional_profile(path: Path | None = None):
    profile_path = path or Path(__file__).with_name("profiles") / "idl_lavalleja.yaml"
    raw = profile_path.read_bytes()
    data = yaml.safe_load(raw)
    existing = InstitutionalProfileVersionRecord.query.filter_by(
        profile_id=data["id"], version=data["version"]
    ).first()
    checksum = sha256(raw).hexdigest()
    if existing:
        if existing.checksum != checksum:
            raise ValueError("Immutable institutional profile version changed")
        return existing
    record = InstitutionalProfileVersionRecord(
        id=str(uuid4()), profile_id=data["id"], version=data["version"], status=data["status"],
        profile_json=data, checksum=checksum,
    )
    db.session.add(record)
    db.session.flush()
    return record
