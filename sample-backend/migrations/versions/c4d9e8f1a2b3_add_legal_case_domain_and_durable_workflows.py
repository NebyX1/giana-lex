"""Add legal case domain and durable workflows

Revision ID: c4d9e8f1a2b3
Revises: 8a1f6e2d4c70
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d9e8f1a2b3"
down_revision = "8a1f6e2d4c70"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legal_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("task_family", sa.String(length=40), nullable=False),
        sa.Column("resolution_type", sa.String(length=120), nullable=True),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("risk_tier", sa.String(length=16), nullable=False),
        sa.Column("workflow_pack_id", sa.String(length=160), nullable=True),
        sa.Column("workflow_pack_version", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("active_run_id", sa.String(length=36), nullable=True),
        sa.Column("corpus_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("state_version >= 0", name="ck_legal_cases_state_version"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_legal_cases_owner_user_id", ["owner_user_id"]),
        ("ix_legal_cases_task_family", ["task_family"]),
        ("ix_legal_cases_resolution_type", ["resolution_type"]),
        ("ix_legal_cases_jurisdiction", ["jurisdiction"]),
        ("ix_legal_cases_state", ["state"]),
        ("ix_legal_cases_active_run_id", ["active_run_id"]),
        ("ix_legal_cases_corpus_snapshot_id", ["corpus_snapshot_id"]),
        ("ix_legal_cases_updated_at", ["updated_at"]),
    ):
        op.create_index(name, "legal_cases", columns, unique=False)

    op.create_table(
        "case_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("command_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_case_commands_attempts"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_user_id", "command_type", "idempotency_key", name="uq_case_commands_idempotency"
        ),
    )
    op.create_index("ix_case_commands_case_id", "case_commands", ["case_id"])
    op.create_index("ix_case_commands_actor_user_id", "case_commands", ["actor_user_id"])
    op.create_index("ix_case_commands_command_type", "case_commands", ["command_type"])
    op.create_index("ix_case_commands_status", "case_commands", ["status"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("command_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.String(length=120), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("attempt >= 1", name="ck_workflow_runs_attempt"),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["command_id"], ["case_commands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_runs_case_id", "workflow_runs", ["case_id"])
    op.create_index("ix_workflow_runs_command_id", "workflow_runs", ["command_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "workflow_step_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("step_name", sa.String(length=120), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("attempt >= 1", name="ck_workflow_step_runs_attempt"),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_name", name="uq_workflow_step_runs_name"),
    )
    op.create_index("ix_workflow_step_runs_run_id", "workflow_step_runs", ["run_id"])
    op.create_index("ix_workflow_step_runs_case_id", "workflow_step_runs", ["case_id"])
    op.create_index("ix_workflow_step_runs_status", "workflow_step_runs", ["status"])

    op.create_table(
        "case_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("command_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("sequence_number >= 1", name="ck_case_events_sequence"),
        sa.CheckConstraint("schema_version >= 1", name="ck_case_events_schema_version"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["command_id"], ["case_commands.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "sequence_number", name="uq_case_events_sequence"),
    )
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"])
    op.create_index("ix_case_events_event_type", "case_events", ["event_type"])
    op.create_index("ix_case_events_command_id", "case_events", ["command_id"])
    op.create_index("ix_case_events_run_id", "case_events", ["run_id"])
    op.create_index("ix_case_events_actor_user_id", "case_events", ["actor_user_id"])
    op.create_index("ix_case_events_occurred_at", "case_events", ["occurred_at"])

    op.create_table(
        "case_snapshots",
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("last_sequence_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("last_sequence_number >= 0", name="ck_case_snapshots_sequence"),
        sa.CheckConstraint("snapshot_version >= 0", name="ck_case_snapshots_version"),
        sa.ForeignKeyConstraint(["case_id"], ["legal_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_index("ix_case_snapshots_state", "case_snapshots", ["state"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_type", sa.String(length=60), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deduplication_key", name="uq_outbox_events_deduplication"),
    )
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_topic", "outbox_events", ["topic"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])

    with op.batch_alter_table("agent_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("case_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_agent_sessions_case_id", ["case_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_agent_sessions_case_id_legal_cases", "legal_cases", ["case_id"], ["id"], ondelete="SET NULL"
        )
    with op.batch_alter_table("uploaded_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("case_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_uploaded_documents_case_id", ["case_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_uploaded_documents_case_id_legal_cases", "legal_cases", ["case_id"], ["id"], ondelete="SET NULL"
        )


def downgrade():
    with op.batch_alter_table("uploaded_documents", schema=None) as batch_op:
        batch_op.drop_constraint("fk_uploaded_documents_case_id_legal_cases", type_="foreignkey")
        batch_op.drop_index("ix_uploaded_documents_case_id")
        batch_op.drop_column("case_id")
    with op.batch_alter_table("agent_sessions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_agent_sessions_case_id_legal_cases", type_="foreignkey")
        batch_op.drop_index("ix_agent_sessions_case_id")
        batch_op.drop_column("case_id")

    op.drop_table("outbox_events")
    op.drop_table("case_snapshots")
    op.drop_table("case_events")
    op.drop_table("workflow_step_runs")
    op.drop_table("workflow_runs")
    op.drop_table("case_commands")
    op.drop_table("legal_cases")
