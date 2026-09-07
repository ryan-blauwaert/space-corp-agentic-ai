# Migrations

Alembic revisions in `versions/` define the PostgreSQL schema history.

Use the configured `SPACE_CORP_MIGRATION_DATABASE_URL` with `alembic upgrade head` to apply revisions. The migration role owns schema changes; the separate `SPACE_CORP_DATABASE_URL` is reserved for the restricted application role. The first revision is intentionally empty, and subsequent revisions introduce the workspace, Facility, and row-level-security schema.
