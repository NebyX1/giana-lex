"""Add identity, email OTP, audit, RBAC and conversation ownership.

Revision ID: 0002_auth_identity_otp_rbac
Revises: 0001_legal_resolution_knowledge
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_auth_identity_otp_rbac"
down_revision = "0001_legal_resolution_knowledge"
branch_labels = None
depends_on = None

ROLES = ("legal_user", "legal_drafter", "legal_reviewer", "corpus_curator", "auditor", "technical_admin", "superuser")


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)
    op.create_table("email_otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_otp_codes_user_id", "email_otp_codes", ["user_id"])
    op.create_table("audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("event", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("subject_type", sa.String(40)),
        sa.Column("subject_id", sa.String(64)),
        sa.Column("details", sa.Text()),
        sa.Column("request_id", sa.String(36)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("user_id", "event", "subject_type", "subject_id", "created_at"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])
    op.create_table("user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    for column in ("user_id", "role_id", "granted_by_user_id"):
        op.create_index(f"ix_user_roles_{column}", "user_roles", [column])
    roles = sa.table("roles", sa.column("name", sa.String))
    op.bulk_insert(roles, [{"name": name} for name in ROLES])
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch.create_index("ix_conversations_owner_user_id", ["owner_user_id"])


def downgrade():
    raise RuntimeError("Identity migration does not support destructive automatic downgrade")
