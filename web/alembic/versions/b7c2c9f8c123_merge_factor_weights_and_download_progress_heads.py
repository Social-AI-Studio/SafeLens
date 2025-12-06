"""Merge heads after factor_weights addition

Revision ID: b7c2c9f8c123
Revises: a1b2c3d4e5f6, f5e5d6c7b8a9
Create Date: 2025-12-06 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "b7c2c9f8c123"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f6", "f5e5d6c7b8a9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads; no schema changes."""
    pass


def downgrade() -> None:
    """Downgrade not supported for merge revisions."""
    pass

