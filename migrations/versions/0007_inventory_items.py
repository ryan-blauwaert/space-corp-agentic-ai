"""Create workspace-scoped Facility component inventory.

Revision ID: 0007_inventory_items
Revises: 0006_components_compatibility
Create Date: 2026-09-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_inventory_items"
down_revision: Union[str, Sequence[str], None] = "0006_components_compatibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workspace-owned component quantities at Facilities."""
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False),
        sa.Column("reorder_point", sa.Integer(), nullable=False),
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
            "quantity_on_hand >= 0",
            name="ck_inventory_items_quantity_on_hand_nonnegative",
        ),
        sa.CheckConstraint(
            "reorder_point >= 0",
            name="ck_inventory_items_reorder_point_nonnegative",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["component_id"], ["components.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "facility_id",
            "component_id",
            name="uq_inventory_items_workspace_facility_component",
        ),
    )
    op.execute("ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY inventory_items_workspace_isolation ON inventory_items
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
    """Remove workspace-scoped Facility component inventory."""
    op.execute("DROP POLICY inventory_items_workspace_isolation ON inventory_items")
    op.execute("ALTER TABLE inventory_items DISABLE ROW LEVEL SECURITY")
    op.drop_table("inventory_items")
