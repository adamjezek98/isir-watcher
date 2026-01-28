"""Add silent column to watched_entities

Revision ID: c3a8f5d12e9b
Revises: 2b095b93b020
Create Date: 2026-01-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a8f5d12e9b'
down_revision: Union[str, None] = '2b095b93b020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add silent column with default False
    op.add_column('watched_entities', sa.Column('silent', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('watched_entities', 'silent')
