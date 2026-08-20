from datetime import datetime

from app.extensions import db


def utcnow() -> datetime:
    return datetime.utcnow()


class LegalCaseRecord(db.Model):
    __tablename__ = "legal_cases"
    __table_args__ = (
        db.CheckConstraint("state_version >= 0", name="ck_legal_cases_state_version"),
    )

    id = db.Column(db.String(36), primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    task_family = db.Column(db.String(40), nullable=False, index=True)
    resolution_type = db.Column(db.String(120), index=True)
    jurisdiction = db.Column(db.String(120), nullable=False, index=True)
    risk_tier = db.Column(db.String(16), nullable=False)
    workflow_pack_id = db.Column(db.String(160))
    workflow_pack_version = db.Column(db.Integer)
    state = db.Column(db.String(40), nullable=False, index=True)
    state_version = db.Column(db.Integer, nullable=False, default=0)
    active_run_id = db.Column(db.String(36), index=True)
    corpus_snapshot_id = db.Column(db.String(36), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)
    completed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    owner = db.relationship("User", backref="legal_cases")


class CaseCommandRecord(db.Model):
    __tablename__ = "case_commands"
    __table_args__ = (
        db.UniqueConstraint(
            "actor_user_id", "command_type", "idempotency_key", name="uq_case_commands_idempotency"
        ),
        db.CheckConstraint("attempts >= 0", name="ck_case_commands_attempts"),
    )

    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(
        db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    command_type = db.Column(db.String(64), nullable=False, index=True)
    idempotency_key = db.Column(db.String(255), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)


class WorkflowRunRecord(db.Model):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        db.CheckConstraint("attempt >= 1", name="ck_workflow_runs_attempt"),
    )

    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(
        db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    command_id = db.Column(db.String(36), db.ForeignKey("case_commands.id"), nullable=False, index=True)
    workflow_id = db.Column(db.String(160), nullable=False)
    workflow_version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    attempt = db.Column(db.Integer, nullable=False, default=1)
    current_step = db.Column(db.String(120))
    cancel_requested_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    error = db.Column(db.Text)


class WorkflowStepRunRecord(db.Model):
    __tablename__ = "workflow_step_runs"
    __table_args__ = (
        db.UniqueConstraint("run_id", "step_name", name="uq_workflow_step_runs_name"),
        db.CheckConstraint("attempt >= 1", name="ck_workflow_step_runs_attempt"),
    )

    id = db.Column(db.String(36), primary_key=True)
    run_id = db.Column(
        db.String(36), db.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id = db.Column(
        db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_name = db.Column(db.String(120), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    attempt = db.Column(db.Integer, nullable=False, default=1)
    input_json = db.Column(db.JSON, nullable=False, default=dict)
    output_json = db.Column(db.JSON)
    error = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)


class CaseEventRecord(db.Model):
    __tablename__ = "case_events"
    __table_args__ = (
        db.UniqueConstraint("case_id", "sequence_number", name="uq_case_events_sequence"),
        db.CheckConstraint("sequence_number >= 1", name="ck_case_events_sequence"),
        db.CheckConstraint("schema_version >= 1", name="ck_case_events_schema_version"),
    )

    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(
        db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_number = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(100), nullable=False, index=True)
    schema_version = db.Column(db.Integer, nullable=False, default=1)
    command_id = db.Column(db.String(36), db.ForeignKey("case_commands.id"), nullable=False, index=True)
    run_id = db.Column(db.String(36), db.ForeignKey("workflow_runs.id"), index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    payload_json = db.Column(db.JSON, nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class CaseSnapshotRecord(db.Model):
    __tablename__ = "case_snapshots"
    __table_args__ = (
        db.CheckConstraint("snapshot_version >= 0", name="ck_case_snapshots_version"),
        db.CheckConstraint("last_sequence_number >= 0", name="ck_case_snapshots_sequence"),
    )

    case_id = db.Column(
        db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), primary_key=True
    )
    snapshot_version = db.Column(db.Integer, nullable=False)
    last_sequence_number = db.Column(db.Integer, nullable=False)
    state = db.Column(db.String(40), nullable=False, index=True)
    snapshot_json = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class OutboxEventRecord(db.Model):
    __tablename__ = "outbox_events"
    __table_args__ = (
        db.UniqueConstraint("deduplication_key", name="uq_outbox_events_deduplication"),
        db.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
    )

    id = db.Column(db.String(36), primary_key=True)
    aggregate_type = db.Column(db.String(60), nullable=False)
    aggregate_id = db.Column(db.String(36), nullable=False, index=True)
    topic = db.Column(db.String(100), nullable=False, index=True)
    deduplication_key = db.Column(db.String(255), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    available_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    published_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class WorkflowPackVersionRecord(db.Model):
    __tablename__ = "workflow_pack_versions"
    __table_args__ = (db.UniqueConstraint("pack_id", "version", name="uq_workflow_pack_version"),)
    id = db.Column(db.String(36), primary_key=True)
    pack_id = db.Column(db.String(160), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, index=True)
    jurisdiction = db.Column(db.String(120), nullable=False)
    definition_json = db.Column(db.JSON, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class FormInstanceRecord(db.Model):
    __tablename__ = "form_instances"
    __table_args__ = (db.UniqueConstraint("case_id", "version", name="uq_form_case_version"),)
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    workflow_pack_id = db.Column(db.String(160), nullable=False)
    workflow_pack_version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    schema_json = db.Column(db.JSON, nullable=False)
    answers_json = db.Column(db.JSON, nullable=False, default=dict)
    errors_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    submitted_at = db.Column(db.DateTime)


class HumanTaskRecord(db.Model):
    __tablename__ = "human_tasks"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    task_type = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    payload_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)


class FactAssertionRecord(db.Model):
    __tablename__ = "fact_assertions"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    key = db.Column(db.String(160), nullable=False, index=True)
    value_json = db.Column(db.JSON, nullable=False)
    value_type = db.Column(db.String(30), nullable=False)
    source_type = db.Column(db.String(40), nullable=False)
    source_ref = db.Column(db.String(255))
    confidence = db.Column(db.Numeric(5, 4), nullable=False)
    verification_status = db.Column(db.String(40), nullable=False, index=True)
    recorded_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    supersedes_id = db.Column(db.String(36), db.ForeignKey("fact_assertions.id"))


class IntakeIntentRecord(db.Model):
    __tablename__ = "intake_intents"
    __table_args__ = (db.UniqueConstraint("case_id", name="uq_intake_intents_case"),)
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = db.Column(db.String(36), db.ForeignKey("workflow_runs.id"), index=True)
    step_run_id = db.Column(db.String(36), db.ForeignKey("workflow_step_runs.id"), index=True)
    schema_version = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(24), nullable=False, index=True)
    request_text_hash = db.Column(db.String(64), nullable=False)
    intent_json = db.Column(db.JSON, nullable=False)
    classifier = db.Column(db.String(40), nullable=False)
    classifier_version = db.Column(db.String(80), nullable=False)
    provider = db.Column(db.String(120))
    model = db.Column(db.String(160))
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PrecedentSearchRunRecord(db.Model):
    __tablename__ = "precedent_search_runs"
    __table_args__ = (
        db.CheckConstraint("searched_count >= 0", name="ck_precedent_search_runs_count"),
    )
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = db.Column(db.String(36), db.ForeignKey("workflow_runs.id"), index=True)
    step_run_id = db.Column(db.String(36), db.ForeignKey("workflow_step_runs.id"), index=True)
    status = db.Column(db.String(24), nullable=False, index=True)
    query_json = db.Column(db.JSON, nullable=False)
    collections_json = db.Column(db.JSON, nullable=False)
    index_status_json = db.Column(db.JSON, nullable=False)
    searched_count = db.Column(db.Integer, nullable=False, default=0)
    candidates_json = db.Column(db.JSON, nullable=False)
    selected_example_version_id = db.Column(db.String(36), db.ForeignKey("example_versions.id"), index=True)
    match_label = db.Column(db.String(20), nullable=False, index=True)
    calibrated_confidence = db.Column(db.Numeric(5, 4))
    similarities_json = db.Column(db.JSON, nullable=False)
    differences_json = db.Column(db.JSON, nullable=False)
    errors_json = db.Column(db.JSON, nullable=False)
    fallback_reason = db.Column(db.Text)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)


class IntakeQuestionRequestRecord(db.Model):
    __tablename__ = "intake_question_requests"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    search_run_id = db.Column(db.String(36), db.ForeignKey("precedent_search_runs.id"), index=True)
    workflow_run_id = db.Column(db.String(36), db.ForeignKey("workflow_runs.id"), index=True)
    step_run_id = db.Column(db.String(36), db.ForeignKey("workflow_step_runs.id"), index=True)
    form_id = db.Column(db.String(36), db.ForeignKey("form_instances.id"), unique=True, index=True)
    human_task_id = db.Column(db.String(36), db.ForeignKey("human_tasks.id"), unique=True, index=True)
    status = db.Column(db.String(24), nullable=False, index=True)
    questions_json = db.Column(db.JSON, nullable=False)
    answers_json = db.Column(db.JSON, nullable=False, default=dict)
    errors_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    answered_at = db.Column(db.DateTime)


class FieldProvenanceRecord(db.Model):
    __tablename__ = "field_provenance"
    __table_args__ = (
        db.UniqueConstraint("question_request_id", "field_key", "source_type", name="uq_field_provenance_source"),
    )
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    question_request_id = db.Column(db.String(36), db.ForeignKey("intake_question_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    form_id = db.Column(db.String(36), db.ForeignKey("form_instances.id"), index=True)
    field_key = db.Column(db.String(160), nullable=False, index=True)
    source_type = db.Column(db.String(40), nullable=False, index=True)
    source_ref = db.Column(db.String(255))
    reason = db.Column(db.Text, nullable=False)
    value_json = db.Column(db.JSON)
    requires_confirmation = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ExampleProfileRecord(db.Model):
    __tablename__ = "example_profiles"
    id = db.Column(db.String(36), primary_key=True)
    stable_key = db.Column(db.String(200), nullable=False, unique=True)
    current_version = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ExampleVersionRecord(db.Model):
    __tablename__ = "example_versions"
    __table_args__ = (db.UniqueConstraint("example_id", "version", name="uq_example_version"),)
    id = db.Column(db.String(36), primary_key=True)
    example_id = db.Column(db.String(36), db.ForeignKey("example_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    act_subtype = db.Column(db.String(120), nullable=False, index=True)
    jurisdiction = db.Column(db.String(120), nullable=False, index=True)
    validation_status = db.Column(db.String(40), nullable=False, index=True)
    profile_json = db.Column(db.JSON, nullable=False)
    cited_authority_refs_json = db.Column(db.JSON, nullable=False)
    source_checksum = db.Column(db.String(64), nullable=False)
    source_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PrecedentSelectionRecord(db.Model):
    __tablename__ = "precedent_selections"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_example_version_id = db.Column(db.String(36), db.ForeignKey("example_versions.id"))
    match_type = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.Numeric(5, 4), nullable=False)
    alternatives_json = db.Column(db.JSON, nullable=False)
    differences_json = db.Column(db.JSON, nullable=False)
    fallback_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class CandidateAuthorityRecord(db.Model):
    __tablename__ = "candidate_authorities"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_reference = db.Column(db.Text, nullable=False)
    normalized_norm_id = db.Column(db.String(160))
    article = db.Column(db.String(80))
    discovered_in_example_id = db.Column(db.String(36), db.ForeignKey("example_versions.id"))
    discovery_reason = db.Column(db.String(20), nullable=False)
    verification_status = db.Column(db.String(40), nullable=False, index=True)
    verified_source_id = db.Column(db.String(160))
    verified_at = db.Column(db.DateTime)


class AuthorityVerificationRecord(db.Model):
    __tablename__ = "authority_verifications"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_authority_id = db.Column(db.String(36), db.ForeignKey("candidate_authorities.id"))
    issue_id = db.Column(db.String(160), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, index=True)
    result_json = db.Column(db.JSON, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class EvidenceSpanRecord(db.Model):
    __tablename__ = "evidence_spans"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = db.Column(db.String(200), nullable=False, index=True)
    source_version = db.Column(db.String(80), nullable=False)
    source_class = db.Column(db.String(40), nullable=False)
    jurisdiction = db.Column(db.String(120), nullable=False)
    norm_id = db.Column(db.String(160))
    article = db.Column(db.String(80))
    exact_text = db.Column(db.Text, nullable=False)
    source_url = db.Column(db.Text)
    checksum = db.Column(db.String(64), nullable=False)
    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)
    active = db.Column(db.Boolean, nullable=False, default=True)
    verified_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    verification_method = db.Column(db.String(120), nullable=False)


class LegalPropositionRecord(db.Model):
    __tablename__ = "legal_propositions"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_id = db.Column(db.String(160), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    applies_to_fact_ids_json = db.Column(db.JSON, nullable=False)
    confidence = db.Column(db.Numeric(5, 4), nullable=False)
    limitations_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)


class ClaimEvidenceLinkRecord(db.Model):
    __tablename__ = "claim_evidence_links"
    __table_args__ = (db.UniqueConstraint("proposition_id", "evidence_id", name="uq_claim_evidence"),)
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    proposition_id = db.Column(db.String(36), db.ForeignKey("legal_propositions.id", ondelete="CASCADE"), nullable=False)
    evidence_id = db.Column(db.String(36), db.ForeignKey("evidence_spans.id", ondelete="CASCADE"), nullable=False)


class CorpusSnapshotRecord(db.Model):
    __tablename__ = "corpus_snapshots"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    manifest_json = db.Column(db.JSON, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class DraftVersionRecord(db.Model):
    __tablename__ = "draft_versions"
    __table_args__ = (db.UniqueConstraint("case_id", "version", name="uq_draft_case_version"),)
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    corpus_snapshot_id = db.Column(db.String(36), db.ForeignKey("corpus_snapshots.id"), nullable=False)
    status = db.Column(db.String(40), nullable=False, index=True)
    draft_json = db.Column(db.JSON, nullable=False)
    validation_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ReviewFindingRecord(db.Model):
    __tablename__ = "review_findings"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    draft_version_id = db.Column(db.String(36), db.ForeignKey("draft_versions.id"), nullable=False)
    reviewer_type = db.Column(db.String(30), nullable=False)
    severity = db.Column(db.String(20), nullable=False, index=True)
    category = db.Column(db.String(120), nullable=False)
    finding_json = db.Column(db.JSON, nullable=False)
    blocks_output = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PromptVersionRecord(db.Model):
    __tablename__ = "prompt_versions"
    id = db.Column(db.String(36), primary_key=True)
    prompt_hash = db.Column(db.String(64), nullable=False, unique=True)
    node_id = db.Column(db.String(120), nullable=False, index=True)
    policies_json = db.Column(db.JSON, nullable=False)
    content = db.Column(db.Text, nullable=False)
    token_estimate = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class AgentRunRecord(db.Model):
    __tablename__ = "agent_runs"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = db.Column(db.String(120), nullable=False, index=True)
    provider = db.Column(db.String(120))
    model = db.Column(db.String(160))
    prompt_version_id = db.Column(db.String(36), db.ForeignKey("prompt_versions.id"))
    corpus_snapshot_id = db.Column(db.String(36), db.ForeignKey("corpus_snapshots.id"))
    parameters_json = db.Column(db.JSON, nullable=False)
    result_json = db.Column(db.JSON)
    error = db.Column(db.Text)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)
    token_usage = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ConversationDigestRecord(db.Model):
    __tablename__ = "conversation_digests"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    digest = db.Column(db.Text, nullable=False)
    message_refs_json = db.Column(db.JSON, nullable=False)
    pending_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class InstitutionalProfileVersionRecord(db.Model):
    __tablename__ = "institutional_profile_versions"
    id = db.Column(db.String(36), primary_key=True)
    profile_id = db.Column(db.String(120), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    profile_json = db.Column(db.JSON, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class MemoryProposalRecord(db.Model):
    __tablename__ = "memory_proposals"
    id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(db.String(36), db.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    statement = db.Column(db.Text, nullable=False)
    scope = db.Column(db.String(30), nullable=False)
    scope_ref = db.Column(db.String(160))
    sources_json = db.Column(db.JSON, nullable=False)
    confidence = db.Column(db.Numeric(5, 4), nullable=False)
    proposed_by_run_id = db.Column(db.String(36), db.ForeignKey("agent_runs.id"))
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True)
    decision_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    decision_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    decided_at = db.Column(db.DateTime)


class OperationalMemoryRecord(db.Model):
    __tablename__ = "operational_memories"
    id = db.Column(db.String(36), primary_key=True)
    proposal_id = db.Column(db.String(36), db.ForeignKey("memory_proposals.id"), nullable=False, unique=True)
    statement = db.Column(db.Text, nullable=False)
    scope = db.Column(db.String(30), nullable=False, index=True)
    scope_ref = db.Column(db.String(160), index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
