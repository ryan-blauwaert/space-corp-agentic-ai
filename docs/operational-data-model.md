# Core Operational Data Model

## Purpose and Scope

This document defines the relational model to be implemented in Roadmap
Waypoint 1.4. It extends the existing workspace-scoped Facility model with the
smallest operational world needed for meaningful structured questions, while
preserving clear boundaries for the later dataset, API, AI, reviewer-workspace,
and workflow phases.

This is a design artifact, not a database migration. No new HTTP endpoints,
full synthetic dataset, browser-session behavior, or AI capability is implied by
this document.

## Design Goals

The model must:

- preserve workspace isolation for all mutable operational records
- support deterministic synthetic baseline creation and later workspace cloning
- make invalid cross-workspace relationships impossible at the database boundary
- give the restricted application role only the access it needs
- provide stable, typed concepts for structured queries, grounded answers, and
  later document retrieval
- remain small enough to understand without introducing generic abstractions or
  speculative workflow infrastructure

## Canonical Operational Questions

The following questions define the initial query requirements. Future structured
query evaluation, answer synthesis, and frontend journeys should reuse them as
early deterministic scenarios.

| Question | Required records and relationships |
| --- | --- |
| Which facilities have degraded or offline equipment with unresolved incidents? | Facility, EquipmentUnit, Incident, operational and incident statuses |
| Do we have compatible replacement components at the affected facility for an equipment unit with an open incident? | EquipmentUnit, EquipmentModel, Component, model-component compatibility, InventoryItem, Facility, Incident |
| Which high-priority work orders are open, blocked, or overdue at a facility, and which incidents or units do they address? | WorkOrder, Facility, optional Incident and EquipmentUnit, work-order status, priority, and due timestamp |
| Has an equipment model had repeated incidents across the operational dataset? | EquipmentModel, EquipmentUnit, Incident, Facility |

These are intentionally relational questions. Waypoint 2.2 will later validate
safe structured-query execution against them, Waypoint 2.3 will ground answers
in their returned records, and Waypoint 2.4 will expose selected journeys in the
frontend.

## Ownership and Role Access

Workspace ownership applies to mutable operational data. Shared definitions are
global, immutable reference records that every workspace may read. The
application role must not own any application table and must remain
`NOBYPASSRLS`.

| Record or table | Ownership | Restricted application-role access | Notes |
| --- | --- | --- | --- |
| `workspaces` | migration owner | none | Created and managed by trusted migration, seeding, and future session processes. |
| `facilities` | workspace-owned | read/write subject to RLS | Existing model; each workspace has its own Facility records. |
| `equipment_models` | shared immutable reference data | read only | A model definition is reusable across workspace copies of operational data. |
| `components` | shared immutable reference data | read only | A component definition is reusable across workspaces. |
| `equipment_model_components` | shared immutable reference data | read only | Compatibility association between models and components. |
| `equipment_units` | workspace-owned | read/write subject to RLS | A deployed, individually tracked unit at one Facility. |
| `inventory_items` | workspace-owned | read/write subject to RLS | A component quantity and reorder point at one Facility. |
| `incidents` | workspace-owned | read/write subject to RLS | Operational event associated with a Facility and optionally an EquipmentUnit. |
| `work_orders` | workspace-owned | read/write subject to RLS | Maintenance work associated with a Facility and optionally an Incident or EquipmentUnit. |

The migration owner owns all tables and applies schema changes. The restricted
application role receives explicit grants only; provisioning must be updated as
each table is introduced. Shared reference tables are intentionally read-only to
that role. Workspace creation, baseline seeding, and baseline cloning remain
trusted server-side or migration-owner operations.

## Entity Relationships

```text
Workspace
  └── Facility
        ├── EquipmentUnit ── EquipmentModel
        │                        │
        │                        └── EquipmentModelComponent ── Component
        ├── InventoryItem ───────────────────────────────────── Component
        ├── Incident ───────── optional EquipmentUnit
        └── WorkOrder ──────── optional Incident and EquipmentUnit
```

The relationship cardinalities are:

- A Workspace has many Facilities, EquipmentUnits, InventoryItems, Incidents,
  and WorkOrders.
- A Facility has many EquipmentUnits, InventoryItems, Incidents, and WorkOrders.
- An EquipmentModel has many EquipmentUnits and is compatible with many
  Components through `equipment_model_components`.
- A Component can be compatible with many EquipmentModels and represented by
  many InventoryItems.
- An EquipmentUnit belongs to one Facility and one EquipmentModel.
- An Incident belongs to one Facility and may identify one affected EquipmentUnit.
- A WorkOrder belongs to one Facility and may address one EquipmentUnit and/or
  one Incident. Multiple WorkOrders may address the same Incident.

`equipment_model_components` is an association table rather than a separate
domain entity. It may later carry compatibility notes or replacement priority
only when a real query requires that additional information.

## Identity, Scoping, and Integrity Rules

All records use UUID identities. Application and repository code generates UUIDs
for normal mutable-record creation; seed data supplies deterministic UUIDs. Raw
SQL inserts must therefore provide an `id` explicitly unless a future migration
introduces a server-side default intentionally.

Every workspace-owned table carries a non-null `workspace_id` and is protected by
an RLS policy using the transaction-local `app.workspace_id` setting. The
application role must use `Database.workspace_session()` after trusted server
code selects the workspace. A caller-supplied UUID is not authorization.

Foreign keys between workspace-owned records use composite keys that include
`workspace_id`. For example, an EquipmentUnit references a Facility through
`(workspace_id, facility_id)`, not `facility_id` alone. The referenced parent
therefore exposes a matching unique key such as `(workspace_id, id)`. This rule
applies to Facility, EquipmentUnit, Incident, and WorkOrder relationships where
both sides are workspace-owned.

Initial identifier and uniqueness rules are:

| Record | Identifier or uniqueness rule |
| --- | --- |
| Facility | unique `(workspace_id, code)` (already implemented) |
| EquipmentModel | globally unique `code` |
| Component | globally unique `code` |
| EquipmentUnit | unique `(workspace_id, asset_tag)` |
| InventoryItem | unique `(workspace_id, facility_id, component_id)` |
| Incident | unique `(workspace_id, reference_code)` |
| WorkOrder | unique `(workspace_id, reference_code)` |

When an Incident or WorkOrder references an EquipmentUnit, it must use the
same workspace. When a WorkOrder references an Incident, it must use the same
workspace. The implementation should also enforce a shared Facility when both a
Facility and one of these related records are supplied; the exact composite key
shape belongs in the relevant migration design and tests.

## Lifecycle and Data Rules

These values are constrained in both typed domain definitions and database check
constraints or native enumerations. The initial representation should follow the
existing Facility convention unless a PostgreSQL-native enum gives a concrete
maintenance benefit.

| Record | Lifecycle or numeric rules |
| --- | --- |
| EquipmentUnit | `operational`, `degraded`, `offline`, or `maintenance` |
| InventoryItem | non-negative `quantity_on_hand` and `reorder_point` |
| Incident | severity: `low`, `medium`, `high`, `critical`; status: `open`, `investigating`, `resolved` |
| WorkOrder | priority: `low`, `medium`, `high`, `critical`; status: `open`, `in_progress`, `blocked`, `completed`, `cancelled` |

All mutable records receive `created_at` and `updated_at` timestamps. Incidents
and WorkOrders may additionally record resolved or completed timestamps. If such
a timestamp is present, the migration should enforce the corresponding terminal
state where that rule is unambiguous.

## Planned Query Paths and Indexes

Indexes are driven by the canonical questions rather than added generically.

| Query path | Planned index or constraint |
| --- | --- |
| Units at a Facility by status | `(workspace_id, facility_id, operational_status)` on EquipmentUnit |
| Units of a model in a workspace | `(workspace_id, equipment_model_id)` on EquipmentUnit |
| Inventory for components at a Facility | unique `(workspace_id, facility_id, component_id)` on InventoryItem |
| Open incidents by Facility or unit | `(workspace_id, facility_id, status)` and `(workspace_id, equipment_unit_id, status)` on Incident |
| Active or overdue work by Facility | `(workspace_id, facility_id, status, priority)` and a due-time index appropriate to the final query form on WorkOrder |
| Incidents by model | EquipmentUnit model lookup joined through the scoped unit relationship; do not denormalize model identifiers into Incident without a demonstrated need |

The later structured-query layer must use validated query shapes and bounded
results. These indexes support that layer but do not authorize arbitrary SQL.

## Future-Phase Fit and Deliberate Deferrals

- **Waypoint 1.5:** creates a versioned, internally consistent baseline using
  these relationships. Shared reference records remain shared while workspace
  records are seeded or cloned per workspace.
- **Waypoint 1.6:** adds read-only APIs over these records, with pagination,
  filtering, standard problem responses, and developer smoke requests.
- **Waypoints 2.2–2.4:** use the canonical questions for safe structured-query
  evaluation, grounded answer evidence, and frontend journeys.
- **Waypoints 2.5–2.6:** create server-authorized reviewer workspaces from the
  baseline. Reviewer edits affect workspace-owned operational records only;
  shared reference records remain unchanged. Reset replaces the workspace rather
  than mutating the canonical baseline.
- **Phase 3:** document metadata may later link manuals and procedures to
  EquipmentModel and Component identifiers. No document, embedding, or vector
  table belongs in this waypoint.
- **Phases 5–6:** agent-initiated writes, approvals, idempotency, and durable
  workflow state require their own audit and action-history design. This
  waypoint adds operational records, not speculative action or event tables.
- **Phases 7–8:** traces and evaluations should record stable entity identifiers
  and baseline versions, but no observability or evaluation infrastructure is
  added here.

The following remain intentionally out of scope for Waypoint 1.4: authentication
or browser-session authorization, HTTP write routes, a generic repository or
service layer, soft deletion, document retrieval, embeddings, agent behavior,
and workflow or audit-event infrastructure.
