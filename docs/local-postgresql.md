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

Create a distinct local database role and separate development and test databases. The test database name intentionally begins with `space_corp_test`; the integration suite rejects other names as a safety guard.

```bash
createuser --login --pwprompt space_corp
createdb --owner=space_corp space_corp
createdb --owner=space_corp space_corp_test
```

Store the local password outside the repository. A per-user `.pgpass` file with mode `0600`, or a password manager with shell environment injection, avoids committing credentials. Use URLs with the explicit project driver:

```bash
export SPACE_CORP_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp"
export SPACE_CORP_TEST_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp_test"
```

If PostgreSQL requires password authentication, configure the password through your local credential mechanism before running non-interactive commands. For `.pgpass`, add one line for each database in your user home directory, then restrict the file permissions:

```text
localhost:5432:space_corp:space_corp:<local-password>
localhost:5432:space_corp_test:space_corp:<local-password>
```

```bash
chmod 600 ~/.pgpass
```

## Migration and Test Commands

Apply the schema baseline to the development database:

```bash
alembic upgrade head
```

Run the integration checks against the dedicated test database:

```bash
pytest -m integration
```

The initial migration is intentionally empty. It records the migration baseline and creates Alembic's version table; Facility tables arrive in Waypoint 1.2.

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
```

Docker documents both the PostgreSQL setup flow and named-volume behavior in its [PostgreSQL guide](https://docs.docker.com/guides/postgresql/) and [Compose volume reference](https://docs.docker.com/reference/compose-file/volumes/).

Do not run `docker compose down -v` unless you intentionally want to delete the local database volume. Docker's documentation notes that named volumes persist across ordinary `down` and `up` cycles, while `-v` removes them.
