"""add audit fields to tool_executions

Revision ID: f1a2b3c4d5e6
Revises: c0c487d5e8e7
Create Date: 2026-09-06 03:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'c0c487d5e8e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tool_executions', sa.Column('request_id', sa.Text(), nullable=False, server_default=''))
    op.add_column('tool_executions', sa.Column('user_id', sa.Text(), nullable=False, server_default='local'))
    op.add_column('tool_executions', sa.Column('arguments_hash', sa.Text(), nullable=False, server_default=''))
    op.add_column(
        'tool_executions',
        sa.Column('permission_status', sa.Text(), nullable=False, server_default='not_required'),
    )
    # NOTE: as with every prior migration touching this metadata, autogenerate
    # would also try to drop ix_memories_embedding_hnsw here -- it's raw-SQL
    # created and isn't represented in SQLAlchemy's index metadata. Since this
    # migration is hand-written (Docker/Postgres wasn't up to autogenerate
    # against), that spurious drop was never emitted in the first place.


def downgrade() -> None:
    op.drop_column('tool_executions', 'permission_status')
    op.drop_column('tool_executions', 'arguments_hash')
    op.drop_column('tool_executions', 'user_id')
    op.drop_column('tool_executions', 'request_id')
