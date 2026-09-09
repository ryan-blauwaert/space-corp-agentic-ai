"""Create catalog releases, equipment models, and workspace equipment units.

Revision ID: 0005_catalog_equipment_units
Revises: 0004_facility_required_text
Create Date: 2026-09-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_catalog_equipment_units"
down_revision: Union[str, Sequence[str], None] = "0004_facility_required_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Match Python str.strip(), including Unicode whitespace.
_REQUIRED_TEXT_WHITESPACE = (
    '\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020'
    '\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006'
    '\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000'
)


def upgrade() -> None:
    """Create the first catalog and workspace-scoped equipment records."""
    op.create_unique_constraint(
        "uq_facilities_workspace_id", "facilities", ["workspace_id", "id"]
    )
    op.create_table(
        "catalog_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"char_length(btrim(code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_catalog_releases_code_not_blank",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_catalog_releases_code"),
    )
    op.create_table(
        "equipment_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_release_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"char_length(btrim(code, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_equipment_models_code_not_blank",
        ),
        sa.CheckConstraint(
            f"char_length(btrim(name, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_equipment_models_name_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_release_id"], ["catalog_releases.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_release_id", "code", name="uq_equipment_models_release_code"
        ),
        sa.UniqueConstraint(
            "catalog_release_id", "id", name="uq_equipment_models_release_id"
        ),
    )
    op.create_table(
        "equipment_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_model_id", sa.Uuid(), nullable=False),
        sa.Column("asset_tag", sa.String(length=64), nullable=False),
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
        sa.CheckConstraint(
            f"char_length(btrim(asset_tag, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_equipment_units_asset_tag_not_blank",
        ),
        sa.CheckConstraint(
            "operational_status IN ('operational', 'degraded', 'offline', 'maintenance')",
            name="ck_equipment_units_operational_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "facility_id"],
            ["facilities.workspace_id", "facilities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_model_id"], ["equipment_models.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "asset_tag", name="uq_equipment_units_workspace_asset_tag"
        ),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_equipment_units_workspace_id"
        ),
    )
    op.create_index(
        "ix_equipment_units_workspace_facility_status",
        "equipment_units",
        ["workspace_id", "facility_id", "operational_status"],
    )
    op.create_index(
        "ix_equipment_units_workspace_model",
        "equipment_units",
        ["workspace_id", "equipment_model_id"],
    )
    op.execute("ALTER TABLE equipment_units ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY equipment_units_workspace_isolation ON equipment_units
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
    """Remove catalog and equipment-unit persistence records."""
    op.execute("DROP POLICY equipment_units_workspace_isolation ON equipment_units")
    op.execute("ALTER TABLE equipment_units DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_equipment_units_workspace_model", table_name="equipment_units")
    op.drop_index(
        "ix_equipment_units_workspace_facility_status", table_name="equipment_units"
    )
    op.drop_table("equipment_units")
    op.drop_table("equipment_models")
    op.drop_table("catalog_releases")
    op.drop_constraint("uq_facilities_workspace_id", "facilities", type_="unique")
