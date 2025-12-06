"""Add factor_weights to harmful_events

Revision ID: f5e5d6c7b8a9
Revises: ebd4d4eb356e
Create Date: 2025-12-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5e5d6c7b8a9"
down_revision: Union[str, Sequence[str], None] = "ebd4d4eb356e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("harmful_events", sa.Column("factor_weights", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("harmful_events", "factor_weights")

