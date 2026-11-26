"""Add consecutive_failures column to watched_entities

Revision ID: d4b7e1a9c2f0
Revises: c3a8f5d12e9b
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b7e1a9c2f0'
down_revision: Union[str, None] = 'c3a8f5d12e9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Count of consecutive invalid-link failures, reset on successful check
    op.add_column('watched_entities', sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('watched_entities', 'consecutive_failures')
