"""Reject whitespace-only Facility text, matching domain validation."""

from alembic import op

revision: str = "0004_facility_required_text"
down_revision: str = "0003_facility_workspace_rls"
branch_labels: None = None
depends_on: None = None

# Python str.strip() whitespace, frozen so future domain changes cannot alter history.
WHITESPACE = (
    '\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020'
    '\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006'
    '\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000'
)


def upgrade() -> None:
    # Existing invalid records cause an explicit failure; do not rewrite user data.
    for field in ("code", "name", "location"):
        name = f"ck_facilities_{field}_not_blank"
        op.drop_constraint(name, "facilities", type_="check")
        op.create_check_constraint(
            name, "facilities", f"char_length(btrim({field}, U&'{WHITESPACE}')) > 0"
        )


def downgrade() -> None:
    for field in ("code", "name", "location"):
        name = f"ck_facilities_{field}_not_blank"
        op.drop_constraint(name, "facilities", type_="check")
        op.create_check_constraint(name, "facilities", f"char_length({field}) > 0")
