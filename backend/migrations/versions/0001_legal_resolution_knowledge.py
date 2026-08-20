"""Create legal resolution knowledge tables.

Revision ID: 0001_legal_resolution_knowledge
Revises: None
"""
from alembic import op

from legal_knowledge.models import Base


revision = "0001_legal_resolution_knowledge"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # create_all is intentionally idempotent and preserves the existing conversations table.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    raise RuntimeError("La migración de conocimiento jurídico no admite downgrade destructivo automático")
