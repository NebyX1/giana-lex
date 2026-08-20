"""Add tool call actor and sources

Revision ID: 1df90e753cd5
Revises: b17725ee13fa
Create Date: 2026-08-13 16:52:22.637916

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1df90e753cd5'
down_revision = 'b17725ee13fa'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tool_calls', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sources', sa.Text(), nullable=False, server_default='[]'))

    op.execute(sa.text(
        "UPDATE tool_calls SET user_id = "
        "(SELECT agent_sessions.user_id FROM agent_sessions WHERE agent_sessions.id = tool_calls.session_id)"
    ))

    with op.batch_alter_table('tool_calls', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f('ix_tool_calls_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_tool_calls_user_id_users', 'users', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('tool_calls', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tool_calls_user_id_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_tool_calls_user_id'))
        batch_op.drop_column('sources')
        batch_op.drop_column('user_id')
