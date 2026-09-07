# Local PostgreSQL Setup

## Recommendation

For this macOS development environment, use a native PostgreSQL installation for the current waypoint. Postgres.app is the quickest graphical option; Homebrew is a good choice when PostgreSQL should run as a background service and be managed from the terminal.

Do not add a Docker configuration solely for this waypoint. Docker Compose becomes attractive when the repository needs a reproducible multi-service stack for contributors, CI, or the hosted demo. If it is introduced later, use a named volume and treat volume deletion as a deliberate data-reset operation.

## Native macOS Setup

Postgres.app can start a local server from the macOS menu bar. PostgreSQL lists it, the EDB installer, and Homebrew as supported macOS installation paths. See the [PostgreSQL macOS download options](https://www.postgresql.org/download/macosx/).

If you use Homebrew, install a supported PostgreSQL version and start it as a user service:

```bash
brew install postgresql@17
brew services start postgresql@17
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
pg_isready
```

The Homebrew formula documents the corresponding service command. The PostgreSQL server data directory must be initialized before the server can run; Homebrew's formula provides the initialization command if it is needed on a new installation. See the [Homebrew PostgreSQL formula](https://formulae.brew.sh/formula/postgresql%4017) and [Homebrew services documentation](https://docs.brew.sh/Manpage.html).

Create the schema-owner migration role and separate development and test databases. The test database name intentionally begins with `space_corp_test`; the integration suite rejects other names as a safety guard.

```bash
createuser --login --pwprompt space_corp
createdb --owner=space_corp space_corp
createdb --owner=space_corp space_corp_test
```

Apply migrations as the schema owner, then provision the restricted application login. The provisioning script creates `space_corp_app` with `NOBYPASSRLS`, grants its data privileges for both local databases, and grants matching defaults for future tables owned by `space_corp`.

```bash
export SPACE_CORP_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp"
alembic upgrade head
psql -d postgres -f scripts/provision_postgresql_application_role.sql
psql -d postgres -c '\password space_corp_app'
```

The final command prompts for the application-role password without placing it in shell history or a tracked file. Store both local passwords outside the repository. A per-user `.pgpass` file with mode `0600`, or a password manager with shell environment injection, avoids committing credentials. Configure separate application and migration URLs with the explicit project driver:

```bash
export SPACE_CORP_DATABASE_URL="postgresql+psycopg://space_corp_app@localhost:5432/space_corp"
export SPACE_CORP_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp"
export SPACE_CORP_TEST_DATABASE_URL="postgresql+psycopg://space_corp_app@localhost:5432/space_corp_test"
export SPACE_CORP_TEST_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp_test"
```

If PostgreSQL requires password authentication, configure the password through your local credential mechanism before running non-interactive commands. For `.pgpass`, add one line for each database in your user home directory, then restrict the file permissions:

```text
localhost:5432:space_corp:space_corp:<local-password>
localhost:5432:space_corp_test:space_corp:<local-password>
localhost:5432:space_corp:space_corp_app:<application-role-password>
localhost:5432:space_corp_test:space_corp_app:<application-role-password>
```

```bash
chmod 600 ~/.pgpass
```

## Migration and Test Commands

Apply schema migrations with the migration-owner URL configured:

```bash
alembic upgrade head
```

Run the integration checks with both test URLs configured. The suite uses the restricted application URL for ordinary data access and the migration-owner URL only for schema setup and cleanup:

```bash
pytest -m integration
```

The initial migration is intentionally empty. It records the migration baseline and creates Alembic's version table; Waypoint 1.2 adds workspace and Facility tables plus Facility RLS.

## Docker Alternative

Choose Docker when reproducibility across machines outweighs the overhead of Docker Desktop. Keep the database data in a named volume, use a non-production local password supplied outside tracked files, and create the dedicated test database in the container:

```bash
export SPACE_CORP_POSTGRES_PASSWORD="<local-password>"
docker volume create space-corp-postgres-data
docker run --detach --name space-corp-postgres \
  --env POSTGRES_USER=space_corp \
  --env POSTGRES_PASSWORD="$SPACE_CORP_POSTGRES_PASSWORD" \
  --env POSTGRES_DB=space_corp \
  --publish 5432:5432 \
  --volume space-corp-postgres-data:/var/lib/postgresql/data \
  postgres:17
docker exec space-corp-postgres createdb -U space_corp space_corp_test
docker exec -i space-corp-postgres psql -U space_corp -d postgres \
  < scripts/provision_postgresql_application_role.sql
docker exec -it space-corp-postgres psql -U space_corp -d postgres \
  -c '\password space_corp_app'
```

Docker documents both the PostgreSQL setup flow and named-volume behavior in its [PostgreSQL guide](https://docs.docker.com/guides/postgresql/) and [Compose volume reference](https://docs.docker.com/reference/compose-file/volumes/).

Do not run `docker compose down -v` unless you intentionally want to delete the local database volume. Docker's documentation notes that named volumes persist across ordinary `down` and `up` cycles, while `-v` removes them.
