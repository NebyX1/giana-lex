"""Add archived sessions and structured audit subjects

Revision ID: 8a1f6e2d4c70
Revises: 1df90e753cd5
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa


revision = "8a1f6e2d4c70"
down_revision = "1df90e753cd5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agent_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_agent_sessions_archived_at"), ["archived_at"], unique=False)

    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("subject_type", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("subject_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("details", sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f("ix_audit_events_subject_type"), ["subject_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_events_subject_id"), ["subject_id"], unique=False)


def downgrade():
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_events_subject_id"))
        batch_op.drop_index(batch_op.f("ix_audit_events_subject_type"))
        batch_op.drop_column("details")
        batch_op.drop_column("subject_id")
        batch_op.drop_column("subject_type")

    with op.batch_alter_table("agent_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_sessions_archived_at"))
        batch_op.drop_column("archived_at")
