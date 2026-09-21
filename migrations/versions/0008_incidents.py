"""Create workspace-scoped operational incidents.

Revision ID: 0008_incidents
Revises: 0007_inventory_items
Create Date: 2026-09-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_incidents"
down_revision: Union[str, Sequence[str], None] = "0007_inventory_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create incidents and enforce their workspace and Facility ownership."""
    op.create_unique_constraint(
        "uq_equipment_units_workspace_facility_id",
        "equipment_units",
        ["workspace_id", "facility_id", "id"],
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_unit_id", sa.Uuid(), nullable=True),
        sa.Column("reference_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fault_code", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(reference_code, U&'\\0009\\000A\\000B\\000C\\000D\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')) > 0",
            name="ck_incidents_reference_code_not_blank",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'resolved')",
            name="ck_incidents_status",
        ),
        sa.CheckConstraint(
            "fault_code IS NULL OR (char_length(btrim(fault_code, U&'\\0009\\000A\\000B\\000C\\000D\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')) > 0 AND fault_code = upper(btrim(fault_code, U&'\\0009\\000A\\000B\\000C\\000D\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')))",
            name="ck_incidents_fault_code_normalized",
        ),
        sa.CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)",
            name="ck_incidents_resolved_at_matches_status",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= occurred_at",
            name="ck_incidents_resolved_at_after_occurred_at",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "facility_id", "equipment_unit_id"],
            ["equipment_units.workspace_id", "equipment_units.facility_id", "equipment_units.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "reference_code", name="uq_incidents_workspace_reference_code"
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_incidents_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id", "facility_id", "id", name="uq_incidents_workspace_facility_id"
        ),
    )
    op.create_index(
        "ix_incidents_workspace_facility_status",
        "incidents",
        ["workspace_id", "facility_id", "status"],
    )
    op.create_index(
        "ix_incidents_workspace_equipment_unit_status",
        "incidents",
        ["workspace_id", "equipment_unit_id", "status"],
    )
    op.create_index(
        "ix_incidents_workspace_unit_fault_occurred",
        "incidents",
        ["workspace_id", "equipment_unit_id", "fault_code", "occurred_at"],
    )
    op.execute("ALTER TABLE incidents ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY incidents_workspace_isolation ON incidents
        FOR ALL
        USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)
        WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    """Remove workspace-scoped incidents."""
    op.execute("DROP POLICY incidents_workspace_isolation ON incidents")
    op.execute("ALTER TABLE incidents DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_incidents_workspace_unit_fault_occurred", table_name="incidents")
    op.drop_index("ix_incidents_workspace_equipment_unit_status", table_name="incidents")
    op.drop_index("ix_incidents_workspace_facility_status", table_name="incidents")
    op.drop_table("incidents")
    op.drop_constraint(
        "uq_equipment_units_workspace_facility_id", "equipment_units", type_="unique"
    )
