"""Add explicit body/system context without changing existing location semantics."""

import sqlalchemy as sa
from alembic import op

revision = "0012_facility_body_or_system"
down_revision = "0011_query_catalog_pin"
branch_labels = None
depends_on = None

_WHITESPACE = (
    "\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020"
    "\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006"
    "\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000"
)
# Frozen migration data. Require the complete known identity/location tuple; custom
# or edited facilities remain unspecified. The schema owner bypasses table RLS.
_BACKFILL = (
    ("LUN-OPS-01", "Lunar Operations One", "Mare Imbrium", "Earth’s Moon"),
    ("LUN-OPS-02", "South Pole Research Station", "Shackleton Crater", "Earth’s Moon"),
    ("MCC-OPS-01", "Mission Control Center", "Houston", "Earth"),
    ("ORB-OPS-01", "Orbital Operations Station", "Low Earth Orbit", "Earth"),
    ("LOG-OPS-01", "Cislunar Logistics Depot", "Earth-Moon L1", "Earth–Moon system"),
)


def upgrade() -> None:
    op.add_column("facilities", sa.Column("body_or_system", sa.String(128), nullable=True))
    op.create_check_constraint(
        "ck_facilities_body_or_system_not_blank",
        "facilities",
        f"body_or_system IS NULL OR char_length(btrim(body_or_system, U&'{_WHITESPACE}')) > 0",
    )
    facilities = sa.table(
        "facilities",
        *(
            sa.column(name, sa.String())
            for name in (
                "code",
                "name",
                "location",
                "body_or_system",
            )
        ),
    )
    for code, name, location, body in _BACKFILL:
        op.execute(
            facilities.update()
            .where(
                facilities.c.code == op.inline_literal(code),
                facilities.c.name == op.inline_literal(name),
                facilities.c.location == op.inline_literal(location),
                facilities.c.body_or_system.is_(None),
            )
            .values(body_or_system=op.inline_literal(body))
        )


def downgrade() -> None:
    op.drop_constraint("ck_facilities_body_or_system_not_blank", "facilities", type_="check")
    op.drop_column("facilities", "body_or_system")
