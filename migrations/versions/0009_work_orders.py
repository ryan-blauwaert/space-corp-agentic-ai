"""Create workspace-scoped work orders.

Revision ID: 0009_work_orders
Revises: 0008_incidents
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_work_orders"
down_revision: Union[str, Sequence[str], None] = "0008_incidents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workspace-owned maintenance work with scoped relationships."""
    op.create_table(
        "work_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("originating_incident_id", sa.Uuid(), nullable=True),
        sa.Column("target_equipment_unit_id", sa.Uuid(), nullable=True),
        sa.Column("reference_code", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("char_length(btrim(reference_code, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')) > 0", name="ck_work_orders_reference_code_not_blank"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_work_orders_priority"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'blocked', 'completed', 'cancelled')", name="ck_work_orders_status"),
        sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="ck_work_orders_completed_at_matches_status"),
        sa.CheckConstraint("completed_at IS NULL OR completed_at >= created_at", name="ck_work_orders_completed_at_after_created_at"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id", "facility_id"], ["facilities.workspace_id", "facilities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id", "facility_id", "originating_incident_id"], ["incidents.workspace_id", "incidents.facility_id", "incidents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id", "facility_id", "target_equipment_unit_id"], ["equipment_units.workspace_id", "equipment_units.facility_id", "equipment_units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "reference_code", name="uq_work_orders_workspace_reference_code"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_work_orders_workspace_id"),
        sa.UniqueConstraint("workspace_id", "facility_id", "id", name="uq_work_orders_workspace_facility_id"),
    )
    op.create_index("ix_work_orders_workspace_facility_status_priority", "work_orders", ["workspace_id", "facility_id", "status", "priority"])
    op.create_index("ix_work_orders_workspace_facility_due_at", "work_orders", ["workspace_id", "facility_id", "due_at"])
    op.execute("ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY work_orders_workspace_isolation ON work_orders FOR ALL USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid) WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)""")


def downgrade() -> None:
    """Remove workspace-scoped work orders."""
    op.execute("DROP POLICY work_orders_workspace_isolation ON work_orders")
    op.execute("ALTER TABLE work_orders DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_work_orders_workspace_facility_due_at", table_name="work_orders")
    op.drop_index("ix_work_orders_workspace_facility_status_priority", table_name="work_orders")
    op.drop_table("work_orders")
