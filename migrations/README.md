# Migrations

Alembic revisions in `versions/` define the PostgreSQL schema history.

Use the configured `SPACE_CORP_DATABASE_URL` with `alembic upgrade head` to apply revisions. The first revision is intentionally empty: it verifies the migration path before Waypoint 1.2 introduces the Facility schema.
