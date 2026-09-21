"""Expose only the current workspace catalog pin to restricted query sessions."""

from alembic import op

revision = "0011_query_catalog_pin"
down_revision = "0010_baseline_pins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION public.current_workspace_catalog_release() RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
            SELECT catalog_release_id FROM public.workspaces
            WHERE id = NULLIF(current_setting('app.workspace_id', true), '')::uuid
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.current_workspace_catalog_release() FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION public.current_workspace_catalog_release()")
