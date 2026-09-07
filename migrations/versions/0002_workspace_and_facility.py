"""Create workspace and facility tables.

Revision ID: 0002_workspace_and_facility
Revises: 0001_initial
Create Date: 2026-09-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_workspace_and_facility"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workspace ownership and Facility persistence tables."""
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "facilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("facility_type", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=256), nullable=False),
        sa.Column("operational_status", sa.String(length=32), nullable=False),
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
        sa.CheckConstraint("char_length(code) > 0", name="ck_facilities_code_not_blank"),
        sa.CheckConstraint("char_length(name) > 0", name="ck_facilities_name_not_blank"),
        sa.CheckConstraint(
            "char_length(location) > 0",
            name="ck_facilities_location_not_blank",
        ),
        sa.CheckConstraint(
            "facility_type IN "
            "('lunar_installation', 'orbital_station', 'logistics_depot', "
            "'mission_control_center')",
            name="ck_facilities_type",
        ),
        sa.CheckConstraint(
            "operational_status IN ('operational', 'degraded', 'offline')",
            name="ck_facilities_operational_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "code", name="uq_facilities_workspace_code"),
    )
    op.create_index("ix_facilities_workspace_id", "facilities", ["workspace_id"])


def downgrade() -> None:
    """Remove Facility and workspace tables."""
    op.drop_index("ix_facilities_workspace_id", table_name="facilities")
    op.drop_table("facilities")
    op.drop_table("workspaces")
