"""add gin index on submissions data

Revision ID: f1f43cb499ad
Revises: ba8a8561050c
Create Date: 2026-09-21 14:29:51.008331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1f43cb499ad'
down_revision: Union[str, None] = 'ba8a8561050c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        op.f('ix_submissions_data_gin'),
        'submissions',
        ['data'],
        unique=False,
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_submissions_data_gin'), table_name='submissions'
    )