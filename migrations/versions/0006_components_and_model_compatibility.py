"""Create catalog components and model compatibility associations.

Revision ID: 0006_components_compatibility
Revises: 0005_catalog_equipment_units
Create Date: 2026-09-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_components_compatibility"
down_revision: Union[str, Sequence[str], None] = "0005_catalog_equipment_units"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Match Python str.strip(), including Unicode whitespace.
_REQUIRED_TEXT_WHITESPACE = (
    "\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020"
    "\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006"
    "\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000"
)


def upgrade() -> None:
    """Create immutable component revisions and same-release compatibility."""
    op.create_table(
        "components",
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
            name="ck_components_code_not_blank",
        ),
        sa.CheckConstraint(
            f"char_length(btrim(name, U&'{_REQUIRED_TEXT_WHITESPACE}')) > 0",
            name="ck_components_name_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_release_id"], ["catalog_releases.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_release_id", "code", name="uq_components_release_code"),
        sa.UniqueConstraint("catalog_release_id", "id", name="uq_components_release_id"),
    )
    op.create_table(
        "equipment_model_components",
        sa.Column("catalog_release_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_model_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_release_id", "equipment_model_id"],
            ["equipment_models.catalog_release_id", "equipment_models.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_release_id", "component_id"],
            ["components.catalog_release_id", "components.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "equipment_model_id",
            "component_id",
            name="pk_equipment_model_components",
        ),
    )


def downgrade() -> None:
    """Remove component catalog and compatibility persistence records."""
    op.drop_table("equipment_model_components")
    op.drop_table("components")
