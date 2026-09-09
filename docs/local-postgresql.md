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

Apply migrations as the schema owner, then provision the restricted application login. The provisioning script creates `space_corp_app` with `NOBYPASSRLS`, grants read-only access to catalog releases and equipment models, and grants scoped Facility/EquipmentUnit reads, inserts, and approved column-level updates for both local databases. It removes legacy broad/default grants and does not grant access to `workspaces` or `alembic_version`. It rejects a pre-existing application role with role memberships or required application tables not owned by `space_corp`; resolve those conditions before rerunning it.

```bash
export SPACE_CORP_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp"
alembic upgrade head
SPACE_CORP_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp_test" alembic upgrade head
psql -X -d postgres -f scripts/provision_postgresql_application_role.sql
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

## Local Application Configuration

Copy the repository template to the ignored local configuration file:

```bash
cp .env.example .env
```

The migration-owner connection is the URL whose PostgreSQL login owns the schema—in this setup, `space_corp`. It is separate from the restricted `space_corp_app` URL used by the running API. Administrative development tasks need the owner connection because `space_corp_app` intentionally cannot create or inspect workspace records and is constrained by row-level security. The seed command verifies table ownership rather than trusting the username written in the URL.

After applying migrations and provisioning the application role, populate the
configured workspace with the repeatable catalog, Facility, and equipment-unit
smoke dataset:

```bash
python -m scripts.seed_development_data
```

The command reads `SPACE_CORP_MIGRATION_DATABASE_URL` and
`SPACE_CORP_DEFAULT_WORKSPACE_ID` from `.env`. It creates the workspace when
necessary and creates or restores one catalog release, two equipment models,
three deterministic Facilities, and two deployed equipment units. Re-running it
is safe and restores their canonical smoke values without adding duplicates. It
refuses non-development environments and databases whose names begin with
`space_corp_test`.

Verify the running API against the seeded data:

```bash
curl http://127.0.0.1:8000/facilities
```

`.env` is ignored. Its database URLs use the restricted `space_corp_app` login for the running API and the `space_corp` migration-owner login for Alembic; passwords remain in `~/.pgpass`, not in `.env`. The application loads `.env` automatically, validates the database URL and workspace ID, and checks database reachability before it begins serving requests. Process environment variables override `.env` values for deployment or temporary command-level changes.

## Migration and Test Commands

Apply schema migrations with the migration-owner URL configured:

```bash
alembic upgrade head
```

Copy the tracked test template once to the ignored `.env.test` file. Pytest loads it automatically; exported variables retain precedence for CI or temporary overrides. The template includes the optional PostgreSQL binary directory used by the disposable provisioning tests. Replace that path if your installation is not Homebrew PostgreSQL 17, or remove the line to skip only those optional tests.

```bash
cp .env.test.example .env.test
pytest
```

The suite uses the restricted application URL for ordinary data access and the migration-owner URL only for schema setup and cleanup. It rejects database names that do not begin with `space_corp_test`.

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
# Apply migrations to both databases using the host Alembic command before provisioning.
docker exec -i space-corp-postgres psql -U space_corp -d postgres \
  < scripts/provision_postgresql_application_role.sql
docker exec -it space-corp-postgres psql -U space_corp -d postgres \
  -c '\password space_corp_app'
```

Docker documents both the PostgreSQL setup flow and named-volume behavior in its [PostgreSQL guide](https://docs.docker.com/guides/postgresql/) and [Compose volume reference](https://docs.docker.com/reference/compose-file/volumes/).

Do not run `docker compose down -v` unless you intentionally want to delete the local database volume. Docker's documentation notes that named volumes persist across ordinary `down` and `up` cycles, while `-v` removes them.

## Additional Verification

The integration suite prepares the schema through explicit fixture dependencies, so individual repository and API files can be run independently after initial role provisioning. The catalog/equipment migration round-trip test removes and reapplies only that migration slice, preserving existing Facility grants. Use a dedicated test database with no valuable data; do not run parallel suites against the same database.

To include provisioning success, repeatability, legacy-grant removal, and failed-precondition tests, set `SPACE_CORP_TEST_POSTGRES_BIN` in `.env.test` to your installed PostgreSQL server-binary directory (for example, `$(pg_config --bindir)`).

```bash
pytest
```

Those provisioning tests initialize disposable clusters in temporary directories with private Unix sockets and TCP disabled, then stop and remove them. They never provision your existing development server. Without this optional variable, provisioning tests explicitly skip. The ordinary database integration tests still require both documented test URLs.

After applying migrations, rerun the provisioning script once to remove older broad grants. Future schema changes must explicitly provision any new required privileges. The script stops at the first error; it does not automatically repair role memberships or table ownership.
