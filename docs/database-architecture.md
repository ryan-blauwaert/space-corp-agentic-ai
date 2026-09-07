# Database Architecture

## Purpose and Scope

This document records the PostgreSQL direction for Waypoint 1.1. It establishes the isolation and connection-management decisions that later schema work must follow. It does not create workspace records, row-level security policies, or reviewer sessions; those capabilities begin in Waypoints 1.2 and 2.5.

## Data Isolation Direction

Mutable operational records will use shared PostgreSQL tables and carry a workspace identifier. A workspace is the ownership boundary for a reviewer or other authorized application context. The canonical synthetic baseline remains versioned and is never modified by workspace edits.

Isolation will be enforced in layers:

1. Application authorization derives the permitted workspace from trusted server-side context rather than an arbitrary client-supplied identifier.
2. Repository operations require an explicit workspace scope so ownership is visible at the persistence boundary.
3. PostgreSQL row-level security (RLS) provides database enforcement for workspace-owned tables.

Foreign keys and uniqueness constraints introduced with domain entities must include workspace scope where required. This prevents cross-workspace relationships and allows the same baseline identifiers to be used in separate workspaces.

## Database Roles

The migration role and the application role have different responsibilities:

- The migration role owns schema changes and may create or alter tables, policies, and roles as required by migrations.
- The application role receives only the privileges required for application reads and writes. It must not have `BYPASSRLS` and must not own workspace-scoped tables.

RLS policy behavior must be verified using the application role, not only a migration or database-owner role. Tests in Waypoint 1.2 will exercise cross-workspace reads, writes, and connection reuse with that role.

## Connection and Workspace Context

When RLS is introduced, each application transaction will set the trusted workspace identifier with a transaction-local PostgreSQL setting, such as `set_config('app.workspace_id', ..., true)`. RLS policies can then read that setting with `current_setting`.

The setting must be transaction-local. A persistent connection-level setting can leak a previous workspace into a reused pooled connection. Connection management must therefore:

- open a transaction before establishing workspace context
- set workspace context for every scoped transaction
- clear or discard connections that cannot be returned to a known-safe state
- reject workspace-scoped operations when trusted context is absent

Application code must not rely on an untrusted request field to establish this context.

## Local Development and Testing

Waypoint 1.1 uses PostgreSQL for local development and a dedicated PostgreSQL database for integration tests. The test database must be explicitly configured and must never be a production database.

Unit tests remain independent of a running database. Integration tests will verify a real connection and migration application against the dedicated test database. Later pull-request checks will run the same integration path in an isolated environment.

Docker is not part of this waypoint. Local PostgreSQL startup and migration commands will be documented when connection management and migrations are introduced.

## Deferred Work

The following are intentionally deferred:

- workspace persistence models and workspace creation
- RLS policies and database-role provisioning
- facility and other domain tables
- baseline seeding
- browser sessions, editable reviewer data, reset, and expiration

Deferring these items keeps Waypoint 1.1 focused on connectivity and migration foundations while preserving the requirements for subsequent work.
