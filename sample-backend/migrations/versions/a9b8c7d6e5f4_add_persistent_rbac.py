"""Add persistent RBAC roles

Revision ID: a9b8c7d6e5f4
Revises: f5e0a1b2c3d4
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = "a9b8c7d6e5f4"
down_revision = "f5e0a1b2c3d4"
branch_labels = None
depends_on = None

ROLES = (
    "legal_user", "legal_drafter", "legal_reviewer", "corpus_curator",
    "auditor", "technical_admin", "superuser",
)


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    op.create_index("ix_user_roles_granted_by_user_id", "user_roles", ["granted_by_user_id"])

    roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String))
    op.bulk_insert(roles, [{"id": index, "name": name} for index, name in enumerate(ROLES, 1)])
    connection = op.get_bind()
    now = datetime.utcnow()
    connection.execute(sa.text(
        "INSERT INTO user_roles (user_id, role_id, granted_by_user_id, granted_at) "
        "SELECT id, 1, NULL, :now FROM users WHERE is_active = :active"
    ), {"now": now, "active": True})
    connection.execute(sa.text(
        "INSERT INTO user_roles (user_id, role_id, granted_by_user_id, granted_at) "
        "SELECT users.id, roles.id, NULL, :now FROM users CROSS JOIN roles "
        "WHERE users.is_superuser = :superuser AND roles.id <> 1"
    ), {"now": now, "superuser": True})


def downgrade():
    op.drop_table("user_roles")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
