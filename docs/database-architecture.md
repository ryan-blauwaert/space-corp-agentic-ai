# Database Architecture

## Purpose and Scope

This document records the PostgreSQL direction through the first Waypoint 1.4
slice. Workspace records, Facility persistence, catalog releases, equipment
models, workspace-scoped equipment units, and their row-level security are now
implemented. Reviewer sessions, editable baseline copies, and reset remain
future work. The complete planned relational model is defined in the
[operational data model](operational-data-model.md).

## Data Isolation Direction

Mutable operational records will use shared PostgreSQL tables and carry a workspace identifier. A workspace is the ownership boundary for a reviewer or other authorized application context. The planned canonical synthetic baseline is versioned and never modified by workspace edits. It is distinct from the shared equipment catalog and from each workspace copy.

Isolation will be enforced in layers:

1. A future application authorization or reviewer-session boundary derives the permitted workspace from trusted server-side context rather than an arbitrary client-supplied identifier.
2. Repository operations require an explicit workspace scope so ownership is visible at the persistence boundary.
3. PostgreSQL row-level security (RLS) provides database enforcement for
   `facilities` and `equipment_units`, including direct queries that bypass
   repository filtering.

Foreign keys and uniqueness constraints introduced with domain entities must include workspace scope where required. This prevents cross-workspace relationships and allows the same baseline identifiers to be used in separate workspaces.

## Shared Reference Data and Reproducible Copies

The [operational model](operational-data-model.md) defines three boundaries:
a shared versioned catalog of equipment/part definitions, a frozen baseline of
initial operational values that references one catalog release, and a separate
editable operational copy per workspace. A workspace can contain many facilities.
Reviewer edits to inventory, asset condition, or maintenance records affect only
that workspace, while published catalog facts stay fixed.

Read-only application grants do not make administrator edits impossible.
Published catalog content must also be protected by trusted publication checks:
changes create new releases rather than rewriting old definitions or compatibility
pairs. This slice adds `catalog_releases` (`id`, unique `code`, `created_at`) and
the required `catalog_release_id` reference from equipment-model revisions.
The Component/compatibility slice will add its matching same-release composite
foreign keys. Waypoint 1.5 implements manifests, publication checks, and
baseline/catalog foreign-key pins to those release records for workspaces. Future
queries use those pins so a new release cannot silently change an existing
workspace's answers.

Operational rows retain globally unique UUIDs, but their human codes may repeat
between workspace copies. Waypoint 1.5 derives seeded UUIDs from the workspace
and stable baseline entity identity and remaps relationships consistently.
The existing fixed-ID Facility seed is a limited smoke helper, not the general
cloning implementation. Shared catalog revision IDs are reused across copies.

Authorization, repository scoping, and [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
protect operational access; composite foreign keys protect relationship integrity.
Shared catalog readability never permits cross-workspace operational aggregation.

## Database Roles

The migration role and the application role have different responsibilities:

- The migration role owns schema changes and may create or alter tables, policies, and roles as required by migrations.
- The application role receives only the privileges required for application reads and writes. It must not have `BYPASSRLS` and must not own workspace-scoped tables.

The local migration role is `space_corp`; the local application role is
`space_corp_app`. The latter is explicitly `NOBYPASSRLS`, owns none of
`workspaces`, `facilities`, `catalog_releases`, `equipment_models`, or
`equipment_units`, has no role memberships, and has no superuser,
database-creation, or role-creation capability. RLS behavior is verified using
that application role, including cross-workspace reads, writes, unscoped access,
approved-column updates, and connection reuse.

### Planned Operational Write Permissions (Waypoint 1.4)

Operational tables allow scoped reads/inserts and column-level updates only for
the allowlist in the [operational model](operational-data-model.md). Identity,
workspace, Facility assignment, model revision, and relationship keys are fixed
for the application role from creation. Remove broad UPDATE grants before
installing these column grants, because privileges are additive. Repositories
and future editing APIs follow the same allowlist; direct restricted-role SQL
must also be tested. [PostgreSQL GRANT](https://www.postgresql.org/docs/current/sql-grant.html)
supports this enforcement without an immutability trigger.

The application role receives no DELETE or TRUNCATE on operational tables,
including Facilities, preventing delete/reinsert as a way to change fixed fields.
Controlled repair and dependency-ordered deletion are migration-owner or future
trusted cleanup responsibilities, with restrictive foreign keys still preserving
relationships. This is a guarantee against ordinary application writes, not
against an administrator able to change schema or grants. This slice's
provisioning script applies the Facility and EquipmentUnit grants; later
operational tables must extend the same policy deliberately.

WorkOrder references have independent meanings: `originating_incident_id`
records the reason for work, and `target_equipment_unit_id` records its target.
Both are optional and may coexist, with the work target differing from the
incident's affected unit. Composite foreign keys require the same workspace and
Facility; no same-unit equality rule or equality trigger is required. Read
contracts keep these identities distinct, including null targets.

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
- the full versioned baseline, catalog publication checks, and workspace pinning
  (the small Facility development smoke seed already exists)
- Components, inventory, incidents, work orders, and compatibility associations
  defined in the [operational data model](operational-data-model.md)

Core operational schema implementation belongs to Waypoint 1.4, full baseline
creation to Waypoint 1.5, and reviewer session/reset behavior to Waypoint 2.5.
The design contract is documented now without introducing those later services.

## Application Role Hardening

Provisioning uses `ON_ERROR_STOP` and a transaction per database, as described in the [psql documentation](https://www.postgresql.org/docs/current/app-psql.html). Failure stops subsequent commands; an earlier database transaction may already have committed. Correct the reported condition and rerun the idempotent script. It removes legacy table/sequence grants and default grants, then grants `SELECT`/`INSERT` plus approved column-level `UPDATE` permissions for Facilities and EquipmentUnits. Catalog releases and equipment models are read-only to the application role; workspace creation and Alembic bookkeeping remain migration-owner operations. Future domain tables require explicit privilege decisions.

Migration `0004_facility_required_text` rejects whitespace-only required Facility text using the same whitespace set as Python's `str.strip()`, including Unicode whitespace. It does not rewrite existing data: invalid rows must be corrected explicitly before the migration can succeed. The migration is transactional and reversible.

The API uses synchronous routes with synchronous SQLAlchemy sessions. Expected HTTP failures use FastAPI exception handlers; validation errors retain FastAPI's existing format. These are supported [FastAPI patterns](https://fastapi.tiangolo.com/tutorial/handling-errors/). No service layer is added because these read operations need no separate business orchestration.
