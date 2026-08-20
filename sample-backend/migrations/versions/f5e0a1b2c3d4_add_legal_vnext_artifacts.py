"""Add legal vNext workflow artifacts

Revision ID: f5e0a1b2c3d4
Revises: c4d9e8f1a2b3
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "f5e0a1b2c3d4"
down_revision = "c4d9e8f1a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_pack_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pack_id", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("jurisdiction", sa.String(120), nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("pack_id", "version", name="uq_workflow_pack_version"),
    )
    op.create_table(
        "form_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("workflow_pack_id", sa.String(160), nullable=False),
        sa.Column("workflow_pack_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime()),
        sa.UniqueConstraint("case_id", "version", name="uq_form_case_version"),
    )
    op.create_table(
        "human_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_table(
        "fact_assertions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("value_type", sa.String(30), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_ref", sa.String(255)),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("verification_status", sa.String(40), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("supersedes_id", sa.String(36), sa.ForeignKey("fact_assertions.id")),
    )
    op.create_table(
        "example_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stable_key", sa.String(200), nullable=False, unique=True),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "example_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("example_id", sa.String(36), sa.ForeignKey("example_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("act_subtype", sa.String(120), nullable=False),
        sa.Column("jurisdiction", sa.String(120), nullable=False),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("cited_authority_refs_json", sa.JSON(), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("example_id", "version", name="uq_example_version"),
    )
    op.create_table(
        "precedent_selections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_example_version_id", sa.String(36), sa.ForeignKey("example_versions.id")),
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("alternatives_json", sa.JSON(), nullable=False),
        sa.Column("differences_json", sa.JSON(), nullable=False),
        sa.Column("fallback_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "candidate_authorities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_reference", sa.Text(), nullable=False),
        sa.Column("normalized_norm_id", sa.String(160)),
        sa.Column("article", sa.String(80)),
        sa.Column("discovered_in_example_id", sa.String(36), sa.ForeignKey("example_versions.id")),
        sa.Column("discovery_reason", sa.String(20), nullable=False),
        sa.Column("verification_status", sa.String(40), nullable=False),
        sa.Column("verified_source_id", sa.String(160)),
        sa.Column("verified_at", sa.DateTime()),
    )
    op.create_table(
        "authority_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_authority_id", sa.String(36), sa.ForeignKey("candidate_authorities.id")),
        sa.Column("issue_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "evidence_spans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("source_version", sa.String(80), nullable=False),
        sa.Column("source_class", sa.String(40), nullable=False),
        sa.Column("jurisdiction", sa.String(120), nullable=False),
        sa.Column("norm_id", sa.String(160)),
        sa.Column("article", sa.String(80)),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
        sa.Column("verification_method", sa.String(120), nullable=False),
    )
    op.create_table(
        "legal_propositions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.String(160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("applies_to_fact_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
    )
    op.create_table(
        "claim_evidence_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposition_id", sa.String(36), sa.ForeignKey("legal_propositions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidence_spans.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("proposition_id", "evidence_id", name="uq_claim_evidence"),
    )
    op.create_table(
        "corpus_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "draft_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("corpus_snapshot_id", sa.String(36), sa.ForeignKey("corpus_snapshots.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("draft_json", sa.JSON(), nullable=False),
        sa.Column("validation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", "version", name="uq_draft_case_version"),
    )
    op.create_table(
        "review_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_version_id", sa.String(36), sa.ForeignKey("draft_versions.id"), nullable=False),
        sa.Column("reviewer_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("finding_json", sa.JSON(), nullable=False),
        sa.Column("blocks_output", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prompt_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("node_id", sa.String(120), nullable=False),
        sa.Column("policies_json", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(120)),
        sa.Column("model", sa.String(160)),
        sa.Column("prompt_version_id", sa.String(36), sa.ForeignKey("prompt_versions.id")),
        sa.Column("corpus_snapshot_id", sa.String(36), sa.ForeignKey("corpus_snapshots.id")),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("token_usage", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "conversation_digests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("message_refs_json", sa.JSON(), nullable=False),
        sa.Column("pending_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "institutional_profile_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "memory_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("scope_ref", sa.String(160)),
        sa.Column("sources_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("proposed_by_run_id", sa.String(36), sa.ForeignKey("agent_runs.id")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("decision_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime()),
    )
    op.create_table(
        "operational_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("memory_proposals.id"), nullable=False, unique=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("scope_ref", sa.String(160)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    indexed = {
        "workflow_pack_versions": ["pack_id", "status"], "form_instances": ["case_id", "status"],
        "human_tasks": ["case_id", "status"], "fact_assertions": ["case_id", "key", "verification_status"],
        "example_profiles": ["active"], "example_versions": ["example_id", "act_subtype", "jurisdiction", "validation_status"],
        "precedent_selections": ["case_id"], "candidate_authorities": ["case_id", "verification_status"],
        "authority_verifications": ["case_id", "issue_id", "status"], "evidence_spans": ["case_id", "source_id"],
        "legal_propositions": ["case_id", "issue_id", "status"], "claim_evidence_links": ["case_id"],
        "corpus_snapshots": ["case_id"], "draft_versions": ["case_id", "status"],
        "review_findings": ["case_id", "severity"], "prompt_versions": ["node_id"],
        "agent_runs": ["case_id", "node_id"], "conversation_digests": ["case_id"],
        "institutional_profile_versions": ["profile_id", "status"], "memory_proposals": ["case_id", "status"],
        "operational_memories": ["scope", "scope_ref"],
    }
    for table, columns in indexed.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in (
        "operational_memories", "memory_proposals", "institutional_profile_versions",
        "conversation_digests", "agent_runs", "prompt_versions", "review_findings",
        "draft_versions", "corpus_snapshots", "claim_evidence_links", "legal_propositions",
        "evidence_spans", "authority_verifications", "candidate_authorities",
        "precedent_selections", "example_versions", "example_profiles", "fact_assertions",
        "human_tasks", "form_instances", "workflow_pack_versions",
    ):
        op.drop_table(table)
