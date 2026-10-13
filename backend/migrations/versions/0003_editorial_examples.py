"""Editorial examples, immutable imported source and versioned local revisions.

Revision ID: 0003_editorial_examples
Revises: 0002_auth_identity_otp_rbac
"""
from alembic import op

from example_catalog import ExampleAudit, ExampleDocument, ExampleImportBatch, ExampleRevision, ExampleSourceVersion


revision = "0003_editorial_examples"
down_revision = "0002_auth_identity_otp_rbac"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for table in (ExampleDocument.__table__, ExampleRevision.__table__, ExampleSourceVersion.__table__,
                  ExampleAudit.__table__, ExampleImportBatch.__table__):
        table.create(connection, checkfirst=True)


def downgrade():
    raise RuntimeError("Editorial history is retained; destructive downgrade is not automatic")
