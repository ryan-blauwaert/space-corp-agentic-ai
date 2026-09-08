# Database Architecture

## Purpose and Scope

This document records the PostgreSQL direction through Waypoint 1.3. Workspace records and Facility row-level security are now implemented; reviewer sessions, editable baseline copies, and reset remain future work.

## Data Isolation Direction

Mutable operational records will use shared PostgreSQL tables and carry a workspace identifier. A workspace is the ownership boundary for a reviewer or other authorized application context. The canonical synthetic baseline remains versioned and is never modified by workspace edits.

Isolation will be enforced in layers:

1. A future application authorization or reviewer-session boundary derives the permitted workspace from trusted server-side context rather than an arbitrary client-supplied identifier.
2. Repository operations require an explicit workspace scope so ownership is visible at the persistence boundary.
3. PostgreSQL row-level security (RLS) provides database enforcement for `facilities`, including direct queries that bypass repository filtering.

Foreign keys and uniqueness constraints introduced with domain entities must include workspace scope where required. This prevents cross-workspace relationships and allows the same baseline identifiers to be used in separate workspaces.

## Database Roles

The migration role and the application role have different responsibilities:

- The migration role owns schema changes and may create or alter tables, policies, and roles as required by migrations.
- The application role receives only the privileges required for application reads and writes. It must not have `BYPASSRLS` and must not own workspace-scoped tables.

The local migration role is `space_corp`; the local application role is `space_corp_app`. The latter is explicitly `NOBYPASSRLS`, owns neither `workspaces` nor `facilities`, has no role memberships, and has no superuser, database-creation, or role-creation capability. RLS behavior is verified using that application role, including cross-workspace reads, writes, unscoped access, and connection reuse.

## Connection and Workspace Context

`Database.workspace_session()` sets a caller-supplied workspace identifier with `set_config('app.workspace_id', ..., true)`. It is a lower-level persistence mechanism, not an authorization decision: the current local API resolves it from server configuration. Future reviewer sessions must authorize it before calling this method. The Facility policy reads that setting with `current_setting`; absent context denies access.

The setting must be transaction-local. A persistent connection-level setting can leak a previous workspace into a reused pooled connection. Connection management must therefore:

- open a transaction before establishing workspace context
- set workspace context for every scoped transaction
- use a transaction-local setting, which PostgreSQL resets before a pooled connection is reused
- reject workspace-scoped operations when trusted context is absent

The future request/session layer must not establish this context from an untrusted request field alone.

## Local Development and Testing

The project uses PostgreSQL for local development and a dedicated PostgreSQL database for integration tests. The test database must be explicitly configured and must never be a production database. Each environment supplies separate application and migration URLs, even when they point to the same database.

Unit tests remain independent of a running database. Integration tests verify real connections, migrations, restricted application-role attributes, RLS policies, and transaction-local workspace context against the dedicated test database.

Docker is not required for this waypoint. Startup, migration, and provisioning commands are in [the local PostgreSQL guide](local-postgresql.md).

## Deferred Work

The following are intentionally deferred:

- browser sessions, editable reviewer data, reset, and expiration
- baseline seeding
- other domain tables

Deferring these items keeps Waypoint 1.2 focused on the first workspace-scoped domain entity while preserving the requirements for subsequent work.

## Facility API Hardening

Provisioning uses `ON_ERROR_STOP` and a transaction per database, as described in the [psql documentation](https://www.postgresql.org/docs/current/app-psql.html). Failure stops subsequent commands; an earlier database transaction may already have committed. Correct the reported condition and rerun the idempotent script. It removes legacy table/sequence grants and default grants, then grants only Facility `SELECT`, `INSERT`, `UPDATE`, and `DELETE`. Workspace creation and Alembic bookkeeping remain migration-owner operations. Future domain tables require explicit privilege decisions.

Migration `0004_facility_required_text` rejects whitespace-only required Facility text using the same whitespace set as Python's `str.strip()`, including Unicode whitespace. It does not rewrite existing data: invalid rows must be corrected explicitly before the migration can succeed. The migration is transactional and reversible.

The API uses synchronous routes with synchronous SQLAlchemy sessions. Expected HTTP failures use FastAPI exception handlers; validation errors retain FastAPI's existing format. These are supported [FastAPI patterns](https://fastapi.tiangolo.com/tutorial/handling-errors/). No service layer is added because these read operations need no separate business orchestration.
