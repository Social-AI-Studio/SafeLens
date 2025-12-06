"""add download_progress and download_error_code columns to videos table

Revision ID: a1b2c3d4e5f6
Revises: ebd4d4eb356e
Create Date: 2025-08-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2630dbdc9f54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add download_progress and download_error_code columns."""
    op.add_column('videos', sa.Column('download_error_code', sa.String(50), nullable=True))
    op.add_column('videos', sa.Column('download_progress', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove download_progress and download_error_code columns."""
    op.drop_column('videos', 'download_progress')
    op.drop_column('videos', 'download_error_code')
