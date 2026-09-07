"""Create the initial migration baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-07

"""

from typing import Sequence, Union


revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Record the initial schema baseline without creating domain tables."""


def downgrade() -> None:
    """Return to the pre-migration baseline."""
