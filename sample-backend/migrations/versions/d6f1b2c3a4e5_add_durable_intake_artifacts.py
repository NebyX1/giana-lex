"""Add durable intake, precedent search and question artifacts

Revision ID: d6f1b2c3a4e5
Revises: a9b8c7d6e5f4
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "d6f1b2c3a4e5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "intake_intents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id")),
        sa.Column("step_run_id", sa.String(36), sa.ForeignKey("workflow_step_runs.id")),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("request_text_hash", sa.String(64), nullable=False),
        sa.Column("intent_json", sa.JSON(), nullable=False),
        sa.Column("classifier", sa.String(40), nullable=False),
        sa.Column("classifier_version", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(120)),
        sa.Column("model", sa.String(160)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("case_id", name="uq_intake_intents_case"),
        sa.CheckConstraint("schema_version >= 1", name="ck_intake_intents_schema_version"),
        sa.CheckConstraint("status IN ('compiled','needs_clarification','failed')", name="ck_intake_intents_status"),
    )
    op.create_table(
        "precedent_search_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id")),
        sa.Column("step_run_id", sa.String(36), sa.ForeignKey("workflow_step_runs.id")),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("query_json", sa.JSON(), nullable=False),
        sa.Column("collections_json", sa.JSON(), nullable=False),
        sa.Column("index_status_json", sa.JSON(), nullable=False),
        sa.Column("searched_count", sa.Integer(), nullable=False),
        sa.Column("candidates_json", sa.JSON(), nullable=False),
        sa.Column("selected_example_version_id", sa.String(36), sa.ForeignKey("example_versions.id")),
        sa.Column("match_label", sa.String(20), nullable=False),
        sa.Column("calibrated_confidence", sa.Numeric(5, 4)),
        sa.Column("similarities_json", sa.JSON(), nullable=False),
        sa.Column("differences_json", sa.JSON(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("fallback_reason", sa.Text()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.CheckConstraint("searched_count >= 0", name="ck_precedent_search_runs_count"),
        sa.CheckConstraint("status IN ('pending','completed','unavailable','failed')", name="ck_precedent_search_runs_status"),
        sa.CheckConstraint("match_label IN ('exact','strong','partial','none')", name="ck_precedent_search_runs_match"),
    )
    op.create_table(
        "intake_question_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_run_id", sa.String(36), sa.ForeignKey("precedent_search_runs.id")),
        sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.id")),
        sa.Column("step_run_id", sa.String(36), sa.ForeignKey("workflow_step_runs.id")),
        sa.Column("form_id", sa.String(36), sa.ForeignKey("form_instances.id"), unique=True),
        sa.Column("human_task_id", sa.String(36), sa.ForeignKey("human_tasks.id"), unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime()),
        sa.CheckConstraint("status IN ('pending','partial','answered','cancelled')", name="ck_intake_question_requests_status"),
    )
    op.create_table(
        "field_provenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("legal_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_request_id", sa.String(36), sa.ForeignKey("intake_question_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_id", sa.String(36), sa.ForeignKey("form_instances.id")),
        sa.Column("field_key", sa.String(160), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_ref", sa.String(255)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("value_json", sa.JSON()),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("question_request_id", "field_key", "source_type", name="uq_field_provenance_source"),
    )
    indexes = {
        "intake_intents": ["case_id", "run_id", "step_run_id", "status"],
        "precedent_search_runs": ["case_id", "run_id", "step_run_id", "status", "selected_example_version_id", "match_label"],
        "intake_question_requests": ["case_id", "search_run_id", "workflow_run_id", "step_run_id", "form_id", "human_task_id", "status"],
        "field_provenance": ["case_id", "question_request_id", "form_id", "field_key", "source_type"],
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    op.drop_table("field_provenance")
    op.drop_table("intake_question_requests")
    op.drop_table("precedent_search_runs")
    op.drop_table("intake_intents")
