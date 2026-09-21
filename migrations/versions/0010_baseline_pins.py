"""Add frozen baseline identities and enforce catalog pins for seeded workspaces."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_baseline_pins"
down_revision = "0009_work_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_releases", sa.Column("content_sha256", sa.String(64)))
    op.create_table(
        "baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "catalog_release_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_releases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "catalog_release_id", name="uq_baselines_id_release"),
    )
    op.add_column("workspaces", sa.Column("baseline_id", sa.Uuid()))
    op.add_column("workspaces", sa.Column("catalog_release_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_workspaces_catalog_release",
        "workspaces",
        "catalog_releases",
        ["catalog_release_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_workspaces_baseline_release",
        "workspaces",
        "baselines",
        ["baseline_id", "catalog_release_id"],
        ["id", "catalog_release_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_workspaces_baseline_pin_pair",
        "workspaces",
        "(baseline_id IS NULL) = (catalog_release_id IS NULL)",
    )
    # A definer trigger can read the private workspace pin without granting the
    # application role access to workspace administration. Names are qualified.
    op.execute("""
        CREATE FUNCTION public.enforce_workspace_catalog() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
        DECLARE pinned uuid; actual uuid;
        BEGIN
            SELECT catalog_release_id INTO pinned FROM public.workspaces
              WHERE id = NEW.workspace_id FOR SHARE;
            IF pinned IS NULL THEN RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'equipment_units' THEN
                SELECT catalog_release_id INTO actual FROM public.equipment_models
                  WHERE id = NEW.equipment_model_id;
            ELSE
                SELECT catalog_release_id INTO actual FROM public.components
                  WHERE id = NEW.component_id;
            END IF;
            IF actual IS DISTINCT FROM pinned THEN
                RAISE EXCEPTION 'Reference must belong to the workspace catalog release'
                  USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$;
        REVOKE ALL ON FUNCTION public.enforce_workspace_catalog() FROM PUBLIC;
        CREATE TRIGGER equipment_units_catalog_pin BEFORE INSERT OR UPDATE ON public.equipment_units
          FOR EACH ROW EXECUTE FUNCTION public.enforce_workspace_catalog();
        CREATE TRIGGER inventory_items_catalog_pin BEFORE INSERT OR UPDATE ON public.inventory_items
          FOR EACH ROW EXECUTE FUNCTION public.enforce_workspace_catalog();
    """)
    op.execute("""
        CREATE FUNCTION public.protect_workspace_pin() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF ROW(OLD.baseline_id, OLD.catalog_release_id) IS DISTINCT FROM
               ROW(NEW.baseline_id, NEW.catalog_release_id) THEN
                IF OLD.baseline_id IS NOT NULL THEN
                    RAISE EXCEPTION 'Create a new workspace to select another baseline'
                      USING ERRCODE = '23514';
                END IF;
                IF EXISTS (SELECT 1 FROM public.equipment_units WHERE workspace_id = OLD.id)
                   OR EXISTS (SELECT 1 FROM public.inventory_items WHERE workspace_id = OLD.id) THEN
                    RAISE EXCEPTION 'Cannot pin an existing operational workspace'
                      USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        REVOKE ALL ON FUNCTION public.protect_workspace_pin() FROM PUBLIC;
        CREATE TRIGGER workspaces_fixed_pin BEFORE UPDATE ON public.workspaces
          FOR EACH ROW EXECUTE FUNCTION public.protect_workspace_pin();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER workspaces_fixed_pin ON workspaces")
    op.execute("DROP FUNCTION public.protect_workspace_pin()")
    for table in ("inventory_items", "equipment_units"):
        op.execute(f"DROP TRIGGER {table}_catalog_pin ON {table}")
    op.execute("DROP FUNCTION public.enforce_workspace_catalog()")
    op.drop_constraint("ck_workspaces_baseline_pin_pair", "workspaces")
    op.drop_constraint("fk_workspaces_baseline_release", "workspaces")
    op.drop_constraint("fk_workspaces_catalog_release", "workspaces")
    op.drop_column("workspaces", "catalog_release_id")
    op.drop_column("workspaces", "baseline_id")
    op.drop_table("baselines")
    op.drop_column("catalog_releases", "content_sha256")
