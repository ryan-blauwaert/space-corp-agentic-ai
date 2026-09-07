# Database Architecture

## Purpose and Scope

This document records the PostgreSQL direction through Waypoint 1.2. Workspace records and Facility row-level security are now implemented; reviewer sessions, editable baseline copies, and reset remain future work.

## Data Isolation Direction

Mutable operational records will use shared PostgreSQL tables and carry a workspace identifier. A workspace is the ownership boundary for a reviewer or other authorized application context. The canonical synthetic baseline remains versioned and is never modified by workspace edits.

Isolation will be enforced in layers:

1. Application authorization derives the permitted workspace from trusted server-side context rather than an arbitrary client-supplied identifier.
2. Repository operations require an explicit workspace scope so ownership is visible at the persistence boundary.
3. PostgreSQL row-level security (RLS) provides database enforcement for `facilities`, including direct queries that bypass repository filtering.

Foreign keys and uniqueness constraints introduced with domain entities must include workspace scope where required. This prevents cross-workspace relationships and allows the same baseline identifiers to be used in separate workspaces.

## Database Roles

The migration role and the application role have different responsibilities:

- The migration role owns schema changes and may create or alter tables, policies, and roles as required by migrations.
- The application role receives only the privileges required for application reads and writes. It must not have `BYPASSRLS` and must not own workspace-scoped tables.

The local migration role is `space_corp`; the local application role is `space_corp_app`. The latter is explicitly `NOBYPASSRLS` and has no schema ownership, superuser, database-creation, or role-creation capability. RLS behavior is verified using that application role, including cross-workspace reads, writes, unscoped access, and connection reuse.

## Connection and Workspace Context

Each application workspace transaction sets the trusted workspace identifier with `set_config('app.workspace_id', ..., true)`. The Facility policy reads that setting with `current_setting`; absent context denies access.

The setting must be transaction-local. A persistent connection-level setting can leak a previous workspace into a reused pooled connection. Connection management must therefore:

- open a transaction before establishing workspace context
- set workspace context for every scoped transaction
- use a transaction-local setting, which PostgreSQL resets before a pooled connection is reused
- reject workspace-scoped operations when trusted context is absent

Application code must not rely on an untrusted request field to establish this context.

## Local Development and Testing

The project uses PostgreSQL for local development and a dedicated PostgreSQL database for integration tests. The test database must be explicitly configured and must never be a production database. Each environment supplies separate application and migration URLs, even when they point to the same database.

Unit tests remain independent of a running database. Integration tests verify real connections, migrations, restricted application-role attributes, RLS policies, and transaction-local workspace context against the dedicated test database.

Docker is not part of this waypoint. Local PostgreSQL startup and migration commands will be documented when connection management and migrations are introduced.

## Deferred Work

The following are intentionally deferred:

- browser sessions, editable reviewer data, reset, and expiration
- baseline seeding
- other domain tables

Deferring these items keeps Waypoint 1.1 focused on connectivity and migration foundations while preserving the requirements for subsequent work.
