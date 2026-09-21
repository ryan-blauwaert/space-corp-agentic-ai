"""Safety checks shared by dataset publication, validation, and bootstrap."""

from sqlalchemy import text
from sqlalchemy.orm import Session


class SeedConfigurationError(RuntimeError):
    """Dataset operations cannot proceed safely with the supplied configuration."""


SEED_TABLES = (
    "baselines",
    "workspaces",
    "facilities",
    "catalog_releases",
    "equipment_models",
    "components",
    "equipment_model_components",
    "equipment_units",
    "inventory_items",
    "incidents",
    "work_orders",
)


def require_migration_owner(session: Session) -> str:
    """Require the connected role to own every table used by dataset seeding."""
    rows = session.execute(
        text("""
            SELECT current_user, relation.relname, owner.rolname
            FROM pg_class AS relation
            JOIN pg_namespace AS schema ON schema.oid = relation.relnamespace
            JOIN pg_roles AS owner ON owner.oid = relation.relowner
            WHERE schema.nspname = 'public'
              AND relation.relname = ANY(:tables)
              AND relation.relkind = 'r'
        """),
        {"tables": list(SEED_TABLES)},
    ).all()
    owners = {name: owner for _, name, owner in rows}
    if set(owners) != set(SEED_TABLES):
        raise SeedConfigurationError("All dataset migrations must be applied before seeding.")
    current_user = str(rows[0][0])
    if any(owner != current_user for owner in owners.values()):
        raise SeedConfigurationError(
            "SPACE_CORP_MIGRATION_DATABASE_URL must connect as the owner "
            "of all dataset tables, including baselines."
        )
    return current_user
