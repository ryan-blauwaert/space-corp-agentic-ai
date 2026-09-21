#!/usr/bin/env bash
# Disposable CI runner only. Exports test configuration through GITHUB_ENV.
set -euo pipefail
: "${RUNNER_TEMP:?This script requires a disposable GitHub Actions runner}"
: "${GITHUB_ENV:?GitHub Actions environment file is required}"
: "${SPACE_CORP_TEST_POSTGRES_BIN:?Set the PostgreSQL server binary directory}"
export PGHOST="$RUNNER_TEMP/space-corp-pg"
export PGPORT=55438 PGUSER=postgres
mkdir -p "$PGHOST"
"$SPACE_CORP_TEST_POSTGRES_BIN/initdb" -D "$PGHOST/data" -U postgres -A trust --no-locale -E UTF8
"$SPACE_CORP_TEST_POSTGRES_BIN/pg_ctl" -D "$PGHOST/data" -l "$PGHOST/server.log" \
  -o "-k $PGHOST -h '' -p $PGPORT" -w start
psql -X -v ON_ERROR_STOP=1 -d postgres <<'SQL'
CREATE ROLE space_corp LOGIN;
CREATE DATABASE space_corp OWNER space_corp;
CREATE DATABASE space_corp_test OWNER space_corp;
SQL
for database in space_corp space_corp_test; do
  SPACE_CORP_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost/$database?host=$PGHOST&port=$PGPORT" \
    .venv/bin/python -m alembic upgrade head
done
psql -X -v ON_ERROR_STOP=1 -d postgres -f scripts/provision_postgresql_application_role.sql
cat >> "$GITHUB_ENV" <<EOF
SPACE_CORP_TEST_DATABASE_URL=postgresql+psycopg://space_corp_app@localhost/space_corp_test?host=$PGHOST&port=$PGPORT
SPACE_CORP_TEST_MIGRATION_DATABASE_URL=postgresql+psycopg://space_corp@localhost/space_corp_test?host=$PGHOST&port=$PGPORT
EOF
