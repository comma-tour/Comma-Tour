"""create api_cache table

Revision ID: f2f9ce186c66
Revises: a1c2e3f4b5d6
Create Date: 2026-09-05 21:14:00.236903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2f9ce186c66'
down_revision: Union[str, Sequence[str], None] = '5f2e6c1600a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('api_cache',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cache_key', sa.String(length=255), nullable=False),
    sa.Column('payload_json', sa.Text(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_cache_id'), 'api_cache', ['id'], unique=False)
    op.create_index(op.f('ix_api_cache_cache_key'), 'api_cache', ['cache_key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_api_cache_cache_key'), table_name='api_cache')
    op.drop_index(op.f('ix_api_cache_id'), table_name='api_cache')
    op.drop_table('api_cache')
