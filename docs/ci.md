# Pull Request Checks

Waypoint 1.7 runs two required checks on pull requests and pushes to `main`:

- **Quality**: Ruff formatting, a small lint rule set (basic errors, unused names,
  and import ordering), and mypy over all `app/` and `scripts/` modules.
- **Tests**: the complete pytest suite, including PostgreSQL integration,
  migrations, role provisioning, bootstrap, and API acceptance tests.

CI uses Python 3.14.6 on Ubuntu 24.04 and PostgreSQL 17. `pyproject.toml` still
permits Python 3.12+, but the initial CI guarantee is the single tested version.
Ruff targets Python 3.12 syntax to avoid introducing newer syntax through fixes.
Mypy requires typed functions, checks function bodies, uses Pydantic's plugin,
and reports stale suppressions. Test and migration modules are linted/formatted
and executed, but are not part of this initial static-type gate.

## Reproduce locally

Use a Python 3.14.6 virtual environment in the repository:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest --require-integration -q
```

Prepare the dedicated test database and ignored `.env.test` using
[the local PostgreSQL guide](local-postgresql.md). Both test URLs must point to
a database whose name starts with `space_corp_test`. The application URL must
use the restricted role; the migration URL uses its owner. Set
`SPACE_CORP_TEST_POSTGRES_BIN` to the directory containing `initdb`, `pg_ctl`, and
`psql`. Required mode fails on missing configuration/binaries or any skipped test.
Ordinary local pytest runs retain optional integration skips. Tests run serially:
migration round trips recreate tables and cannot share a database concurrently.

Apply formatting locally with `.venv/bin/python -m ruff format .`; CI only checks
and never rewrites submitted code. Lint fixes should be reviewed before committing.

## Dependency updates

`pyproject.toml` defines acceptable dependencies and the development tools.
`requirements-dev.lock` pins their resolved transitive and build dependencies,
with hashes. The development inputs explicitly include `greenlet`, SQLAlchemy’s
conditional Linux dependency, so a lock generated on macOS also covers Linux.
Regenerate under the documented Python version after input changes:

```bash
.venv/bin/python -m piptools compile pyproject.toml --extra dev --all-build-deps \
  --allow-unsafe --generate-hashes --strip-extras --output-file requirements-dev.lock
```

Add `--upgrade` for a deliberate dependency refresh. Review the lock diff, install
it, and run the checks. The historical pip-tools option `--allow-unsafe` includes
pip/setuptools in the lock; it does not disable hash verification. The project
install uses `--no-deps --no-build-isolation` so it cannot silently resolve fresh
runtime or build dependencies outside that lock. `pip check` verifies the installed
project's declared requirements. The lock is verified on macOS ARM64 locally and
Linux x86_64 in CI; other platforms/Python versions are not guaranteed by this lock.

## Isolated CI database

`scripts/ci_postgresql.sh` is for disposable Actions runners only. It initializes
a fresh PostgreSQL cluster with a private Unix socket and TCP disabled, creates
both databases expected by the existing provisioning script, migrates them, and
provisions the application role. Trust authentication is confined to this disposable
runner cluster; it is not a production or shared-server configuration. Tests use
the restricted role, not the PostgreSQL administrator. The cluster is stopped in
an always-run cleanup step and the hosted runner is discarded afterward.

The workflow supplies all configuration. It needs no `.env`, production secrets,
model-provider keys, external model calls, Docker, or persistent database service.
Actions are pinned to commit hashes and the workflow token has read-only contents
permission. Pull requests use `pull_request`, not `pull_request_target`.

## Merge enforcement and acceptance

The GitHub protection rule for `main` requires **Quality** and **Tests** from
GitHub Actions, requires the branch to be up to date, and enforces the rule for
administrators. No mandatory
reviewer count is needed for this single-contributor project. Keep check names
stable because protection refers to them by name.

Workflow files alone do not enforce merging: the repository rule must be configured
and read back. Acceptance requires a real PR run, confirmation that failed required
checks block merging, and a passing run on the final PR revision. Never mark the
waypoint complete based only on local checks.

References: [Ruff](https://docs.astral.sh/ruff/formatter/),
[mypy adoption](https://mypy.readthedocs.io/en/stable/existing_code.html),
[pip repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/),
and [GitHub branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

Verified in [PR #10](https://github.com/ryan-blauwaert/space-corp-agentic-ai/pull/10):
370 tests passed without skips on a clean Linux runner; Quality passed with 47
modules checked by mypy. A temporary lint failure blocked merging while Tests
passed; removing it restored a CLEAN merge state. The probe is absent from the
final tree. One existing Starlette/AnyIO deprecation warning remains.
