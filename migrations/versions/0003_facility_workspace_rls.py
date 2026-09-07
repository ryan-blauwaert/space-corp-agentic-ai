"""Enforce workspace isolation for facilities with PostgreSQL RLS.

Revision ID: 0003_facility_workspace_rls
Revises: 0002_workspace_and_facility
Create Date: 2026-09-07

"""

from typing import Sequence, Union

from alembic import op


revision: str = "0003_facility_workspace_rls"
down_revision: Union[str, Sequence[str], None] = "0002_workspace_and_facility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Require a transaction-local workspace setting for Facility access."""
    op.execute("ALTER TABLE facilities ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY facilities_workspace_isolation ON facilities
        FOR ALL
        USING (
            workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid
        )
        WITH CHECK (
            workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    """Remove Facility row-level security enforcement."""
    op.execute("DROP POLICY facilities_workspace_isolation ON facilities")
    op.execute("ALTER TABLE facilities DISABLE ROW LEVEL SECURITY")
