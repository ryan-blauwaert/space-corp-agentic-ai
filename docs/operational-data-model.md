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

| ID | Question | Inputs and exact meaning | Evidence and empty-result behavior |
| --- | --- | --- | --- |
| Q1 | Which facilities have degraded or offline equipment with unresolved incidents? | Trusted workspace; optional Facility. Match units in `degraded` or `offline` with an incident on that **same unit** in `open` or `investigating`. | Return each Facility once, with matching unit and incident IDs/statuses. An unrelated facility-level incident does not qualify the unit. No matches means no records satisfy these conditions, not proof the facility is healthy. |
| Q2 | Which components compatible with this affected equipment model are stocked at the unit's facility? | Trusted workspace and EquipmentUnit ID. Require an unresolved incident on that unit. Join its exact model revision to compatible components, then left-join local inventory. | Return model/component IDs, compatibility pairs, inventory quantities, and supporting incident IDs. Distinguish no unresolved incident, no listed compatibility, recorded zero stock, and missing inventory data. Compatibility does not establish that a part repairs this fault. |
| Q3 | Which high-priority work orders are active at this facility, and which are blocked or overdue? | Trusted workspace, Facility ID, and `as_of`. High priority means `high` or `critical`; active means `open`, `in_progress`, or `blocked`. Overdue means active with non-null `due_at < as_of`; due exactly at `as_of` is not overdue. | Return work-order IDs, status, priority, due time, overdue flag, and separately labeled originating-incident, incident-affected-unit, and work-target-unit IDs. Blocked and overdue may both apply to one order. A null due time means unscheduled, not overdue. No matches means no active high-priority orders. |
| Q4 | Has the same reported fault recurred for this equipment model within this workspace and time window? | Trusted workspace, exact EquipmentModel revision, normalized `fault_code`, `window_start`, and `as_of`. Count distinct incidents on units of that model with the same code and `window_start <= occurred_at < as_of`, regardless of current incident status. Repeated means at least two incidents. | Return the count and incident/unit/Facility IDs and occurrence times. One incident is not recurrence; zero means no recorded matches. Missing fault classification is unknown and is excluded, not treated as another occurrence of the requested fault. |
| Q5 | Which recorded component stocks are below their reorder points at this facility? | Trusted workspace and Facility ID. Select InventoryItems where `quantity_on_hand < reorder_point`; equality does not qualify. | Return component and inventory IDs, quantity, reorder point, and shortfall. No matches means no recorded stock is below its threshold. It makes no claim about components without inventory records. |

All five questions operate within one authorized workspace. “Across facilities”
never means across reviewers' copies of the world. Facility/unit inputs outside
that workspace follow the existing not-found contract; unavailable inputs are
not silently interpreted as an empty successful query.

Results use stable entity ordering and bounded pagination; evidence links retain
all applicable ownership and catalog-revision context. Counts use distinct
incident IDs so joins to multiple work orders or compatible parts cannot inflate
recurrence. Baseline scenarios record exact expected record identities, not only
plausible answer text.

Time inputs are timezone-aware UTC instants. Evaluation scenarios supply a fixed
`as_of` and, for Q4, a `window_start` earlier than `as_of`. Interactive callers
may default `as_of` to one server-captured request time. These are queries over
current records: an `as_of` comparison does not reconstruct historical equipment
or work-order states. Historical state reconstruction remains deferred.

These are intentionally relational questions. Waypoint 1.4 establishes fields,
relationships, and repository tests; Waypoint 1.5 supplies complete deterministic
scenarios. Waypoint 2.2 later validates safe structured-query execution,
Waypoint 2.3 grounds answers in the returned evidence, and Waypoint 2.4 exposes
selected frontend journeys. Fault-code meaning and recommended procedures remain
later document-retrieval concerns.

## Ownership and Role Access

Workspace ownership applies to mutable operational data. Shared definitions are
global reference records whose published revisions are immutable. Every workspace
may read the catalog, but its operational queries use its pinned catalog release.
The application role must not own any application table and must remain
`NOBYPASSRLS`.

| Record or table | Ownership | Restricted application-role access | Notes |
| --- | --- | --- | --- |
| `workspaces` | migration owner | none | Created and managed by trusted migration, seeding, and future session processes. |
| `facilities` | workspace-owned | scoped read/insert; approved-column updates only; no delete | Existing model; each workspace has its own Facility records. Tighten existing grants during 1.4. |
| `catalog_releases` | shared reference data | read only | Stable release identity referenced by models, components, and later baseline/workspace pins. |
| `equipment_models` | shared immutable reference data | read only | A model definition is reusable across workspace copies of operational data. |
| `components` | shared immutable reference data | read only | A component definition is reusable across workspaces. |
| `equipment_model_components` | shared immutable reference data | read only | Compatibility association between models and components. |
| `equipment_units` | workspace-owned | scoped read/insert; approved-column updates only; no delete | A deployed, individually tracked unit at one Facility. |
| `inventory_items` | workspace-owned | scoped read/insert; approved-column updates only; no delete | A component quantity and reorder point at one Facility. |
| `incidents` | workspace-owned | scoped read/insert; approved-column updates only; no delete | Operational event associated with a Facility and optionally an EquipmentUnit. |
| `work_orders` | workspace-owned | scoped read/insert; approved-column updates only; no delete | Maintenance work at a Facility, with an optional originating Incident and optional target EquipmentUnit; both are allowed. |

The migration owner owns all tables and applies schema changes. The restricted
application role receives explicit grants only; provisioning must be updated as
each table is introduced. Shared reference tables are intentionally read-only to
that role. Workspace creation, baseline seeding, and baseline cloning remain
trusted server-side or migration-owner operations.

## Shared Catalog, Baseline, and Workspace Copies

These are three different concepts:

| Concept | Meaning | Example |
| --- | --- | --- |
| Shared catalog | Versioned equipment and part definitions, including compatibility. Reviewer actions cannot change these definitions. | Catalog release `catalog-1` says filter F-12 fits model ECS-4. |
| Canonical baseline | A frozen starting scenario, with its own version and a reference to one catalog release. It includes initial operational values. | Baseline `demo-1` starts with three F-12 filters at Lunar Operations One. |
| Workspace | One reviewer's editable copy of those operational values, potentially spanning many facilities. | Reviewer A consumes a filter and has two left; reviewer B still has three. |

Workspace records share physical PostgreSQL tables, not operational ownership.
Facilities are copied because their status and related operational data may vary
between reviewers. EquipmentModel and Component represent reusable catalog
**types**; EquipmentUnit is a particular installed asset and InventoryItem is a
local stock count of a component type.

Published catalog releases are append-only: corrections produce a new release
and new revision identities, rather than updating or deleting published rows.
This rule also applies to compatibility associations. Application-role read-only
grants are necessary but do not prevent an administrator from changing records;
trusted publication/seeding must compare existing content and reject attempted
rewrites. Schema-owner recovery is a privileged exception, not a reviewer API.

Waypoint 1.4 introduces the small shared `catalog_releases` reference table with
`id` (UUID primary key), `code` (unique nonblank release label, such as
`catalog-1`), and `created_at`. Models and components each have a required
`catalog_release_id` foreign key and unique `(catalog_release_id, code)`.
Each also exposes unique `(catalog_release_id, id)` for composite references.

Compatibility associations carry one `catalog_release_id` and reference both
`(catalog_release_id, equipment_model_id)` and
`(catalog_release_id, component_id)` against the respective parent composite
keys. This rejects nonexistent releases and mixed-release compatibility through
foreign keys. The association's model/component pair remains unique. A release
row supplies relational identity; its existence alone does not enforce publication
immutability or prevent additions to an already published catalog.

Add CatalogRelease with the EquipmentModel/EquipmentUnit increment. The first
smoke fixtures use one fixed release. Waypoint 1.5 implements release and baseline
manifests, publication validation, and workspace pinning, using foreign keys to
`catalog_releases` rather than unrelated version strings. Each workspace records
its baseline version and catalog release. Queries and operational references must
stay within that release even when newer catalog rows exist. Existing workspaces
remain pinned; choosing a new baseline creates a new workspace rather than
silently changing its reference facts. Full publication administration or migration
of live workspaces is not required now.

## Inventory Interpretation

Components initially represent interchangeable, discrete parts counted in whole
units. `quantity_on_hand` and `reorder_point` are non-negative integers. A stock
row with zero quantity means a known stockout; an absent row means unrecorded
inventory. Never convert an absent row into a factual claim of zero stock.

The initial synthetic scenario explicitly assumes recorded stock is usable and
unreserved. Therefore positive on-hand stock may be presented as locally stocked
under that assumption. It is not a guarantee of repair suitability, a parts
reservation, or authorization to perform maintenance. Damaged stock, reserved
quantities, serialized parts, units of measure, and fault-specific repair
requirements remain deferred until a scenario needs them.

## Entity Relationships

```text
CatalogRelease ── EquipmentModel / Component revisions

Workspace
  └── Facility
        ├── EquipmentUnit ── EquipmentModel
        │                        │
        │                        └── EquipmentModelComponent ── Component
        ├── InventoryItem ───────────────────────────────────── Component
        ├── Incident ───────── optional EquipmentUnit
        └── WorkOrder ──────── optional originating Incident
                      └── optional target EquipmentUnit
```

The relationship cardinalities are:

- A CatalogRelease contains many EquipmentModel and Component revisions.
- A Workspace has many Facilities, EquipmentUnits, InventoryItems, Incidents,
  and WorkOrders.
- A Facility has many EquipmentUnits, InventoryItems, Incidents, and WorkOrders.
- An EquipmentModel has many EquipmentUnits and is compatible with many
  Components through `equipment_model_components`.
- A Component can be compatible with many EquipmentModels and represented by
  many InventoryItems.
- An EquipmentUnit belongs to one Facility and one EquipmentModel.
- An Incident belongs to one Facility and may identify one affected EquipmentUnit.
- A WorkOrder belongs to one Facility and may name an originating Incident
  (`originating_incident_id`) and a work target (`target_equipment_unit_id`).
  Either, both, or neither may be supplied. Multiple work orders may originate
  from the same incident and may target different units.

`equipment_model_components` is an association table rather than a separate
domain entity. It may later carry compatibility notes or replacement priority
only when a real query requires that additional information.

## Identity, Scoping, and Integrity Rules

All records use UUID identities. Application and repository code generates UUIDs
for normal mutable-record creation. Seeded operational UUIDs are deterministic
per workspace: derive [UUIDv5 identities](https://docs.python.org/3/library/uuid.html#uuid.uuid5)
using the workspace UUID as namespace and
a stable name containing the baseline version, entity type, and baseline entity
key. Use a specified, unambiguous encoding of that name in the Waypoint 1.5 seed
contract. The same seed in the same workspace yields the same IDs; a new workspace
yields different IDs. Stable codes and asset tags may repeat across workspaces.
Seed relationships are resolved through this mapping, not copied UUIDs from the
source workspace. Shared catalog revisions keep their own globally unique IDs.

The existing Facility smoke seed uses fixed global UUIDs and deliberately refuses
to reuse them in another workspace. It remains a single-workspace smoke helper;
Waypoint 1.5 must adapt or replace that strategy before baseline cloning.

Raw SQL inserts must provide an `id` explicitly because existing tables use
application-side UUID defaults; server-side defaults require a deliberate migration.

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
| CatalogRelease | globally unique UUID; globally unique `code` |
| EquipmentModel | globally unique revision UUID; unique `(catalog_release_id, code)` |
| Component | globally unique revision UUID; unique `(catalog_release_id, code)` |
| EquipmentModelComponent | unique model/component revision pair; both revisions belong to the same catalog release |
| EquipmentUnit | unique `(workspace_id, asset_tag)` |
| InventoryItem | unique `(workspace_id, facility_id, component_id)` |
| Incident | unique `(workspace_id, reference_code)` |
| WorkOrder | unique `(workspace_id, reference_code)` |

An Incident's optional `equipment_unit_id` identifies the affected unit. A
WorkOrder's optional `originating_incident_id` explains why work was requested;
its optional `target_equipment_unit_id` identifies the asset on which work will
be performed. These references express different facts.

| Originating incident | Target unit | Meaning |
| --- | --- | --- |
| Absent | Absent | Facility-level work, such as inspecting access corridors. |
| Absent | Present | Unit-specific work, such as scheduled pump maintenance. |
| Present | Absent | Incident investigation without a selected work target, including facility-level incidents. |
| Present | Present | Work on a specified unit in response to an incident. The target may be the incident's affected unit or a different unit at the same Facility. |

For example, an overheating incident affecting controller C-4 can originate a
work order to inspect fan F-2. Both units and the incident belong to the work
order's Facility and workspace. The link records the requested response; it does
not prove the fan caused the fault or that the proposed work will repair it.

An Incident and its affected unit must share workspace and Facility. A WorkOrder
must share workspace and Facility with each of its supplied references. Enforce
these relationships through composite foreign keys to parent keys such as
`(workspace_id, facility_id, id)`, with restrictive update/delete behavior. There
is no mutual-exclusion constraint and no equality rule between incident-affected
and work-target units. No cross-table equality trigger is required. This replaces
the earlier same-unit agreement proposal because the references have distinct
domain meanings. PostgreSQL supports these composite relationships through
[foreign-key constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).

Read APIs and answer evidence must label `originating_incident_id`,
`incident_equipment_unit_id` (derived from the incident), and
`target_equipment_unit_id` separately. An absent target remains null even if the
incident has an affected unit; do not silently substitute one for the other.
Multiple work orders may originate from one incident without multiplying the
incident count in Q4. Cross-Facility work remains outside the initial scope.

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

All mutable records receive `created_at` and `updated_at` timestamps. The query
contract additionally requires:

- Incident: required `occurred_at`, optional normalized `fault_code`, and nullable
  `resolved_at`. Codes are trimmed, nonblank uppercase identifiers when supplied;
  equality is interpreted within one model revision. A null code means unknown.
  No separate fault taxonomy table is required for the initial recurrence query.
- WorkOrder: nullable `due_at` and `completed_at`; null due time means unscheduled.
- `resolved_at` is present exactly when incident status is `resolved`, and cannot
  precede `occurred_at`. `completed_at` is present exactly when work-order status
  is `completed`, and cannot precede its creation time. A cancelled order is not
  a completed order. Reopening and full transition history remain future work.

Occurrence time records the operational event; creation time records database
insertion and may be much later for seeded or imported history. Do not use seed
execution time as an incident occurrence time.

## Restricted-Role Updates and Deletion Policy

The historical-meaning guarantee applies to the restricted application role:
ordinary application operations cannot rewrite identities or relationships.
From creation, that role cannot update primary IDs, `workspace_id`, human
identity keys (codes, asset tags, reference codes), `created_at`, Facility
assignments, model revisions, component references, incident occurrence/fault
classification, or Incident/WorkOrder relationship keys. EquipmentUnit Facility
and model assignments are fixed even before any incident references the unit.
Controlled migration-owner repair remains a separate administrative capability.

The initial update allowlist is:

| Workspace-owned record | Application-updatable columns |
| --- | --- |
| Facility | `name`, `location`, `operational_status`, `updated_at` |
| EquipmentUnit | `operational_status`, `updated_at` |
| InventoryItem | `quantity_on_hand`, `reorder_point`, `updated_at` |
| Incident | `severity`, `status`, `resolved_at`, `updated_at` |
| WorkOrder | `priority`, `status`, `due_at`, `completed_at`, `updated_at` |

Grant `SELECT` and required `INSERT` access subject to RLS, then grant `UPDATE`
only for the listed columns. Repository update interfaces accept only those
fields, and the later editing API follows the same restriction. Creation still
accepts initial relationship keys, with RLS and foreign keys validating them.
Timestamp/status constraints apply to updates as well as inserts. This does not
introduce HTTP write endpoints in 1.4.

Remove existing broad table-level UPDATE grants before applying column-level
grants, including any inherited or PUBLIC privileges that would defeat the
allowlist. Ensure ORM-generated updates, including `updated_at`, stay within it.
PostgreSQL privileges are additive: a column-level restriction cannot cancel a
table-level grant. See the [GRANT documentation](https://www.postgresql.org/docs/current/sql-grant.html).

The application role receives no DELETE or TRUNCATE privileges on the operational
tables, including existing Facilities. It cannot delete and recreate a row to
bypass fixed-field rules. Use status changes for ordinary lifecycle operations;
physical deletion and workspace cleanup remain trusted administrative work.
References use restrictive deletion rather than automatic cascades. Future reset
retires a workspace and creates another; a later privileged cleanup process may
remove retired data in dependency order, under its own documented checks.

Tests must exercise real SQL as the restricted role, not only repository methods.
The migration owner may perform controlled repair or schema changes, preserving
relationship consistency and recording the purpose and affected records in the
maintenance change. These permissions do not protect against an administrator
who can alter schema or grants. No immutability trigger or audit-event service
is introduced for this guarantee; stronger administrative guardrails require a
separate demonstrated need. Transfers, retargeting, and historical reconstruction
remain deliberately deferred.

## Planned Query Paths and Indexes

Indexes are driven by the canonical questions rather than added generically.

| Query path | Planned index or constraint |
| --- | --- |
| Units at a Facility by status | `(workspace_id, facility_id, operational_status)` on EquipmentUnit |
| Units of a model in a workspace | `(workspace_id, equipment_model_id)` on EquipmentUnit |
| Inventory for components at a Facility | unique `(workspace_id, facility_id, component_id)` on InventoryItem |
| Open incidents by Facility or unit | `(workspace_id, facility_id, status)` and `(workspace_id, equipment_unit_id, status)` on Incident |
| Active or overdue work by Facility | `(workspace_id, facility_id, status, priority)` and a due-time index appropriate to the final query form on WorkOrder |
| Repeated faults by model and time | EquipmentUnit model lookup joined to Incident through the scoped unit relationship, with `(workspace_id, equipment_unit_id, fault_code, occurred_at)` as the initial Incident index candidate |
| Below-reorder stock | Start with the existing workspace/Facility inventory access path and filter quantity against reorder point; avoid an additional index until realistic data demonstrates a need |

Confirm index usefulness with representative Q1–Q5 queries and query plans as
data arrives; avoid indexes already provided by unique constraints. The later
structured-query layer must use validated query shapes and bounded
results. These indexes support that layer but do not authorize arbitrary SQL.

## Future-Phase Fit and Deliberate Deferrals

- **Waypoint 1.5:** creates a versioned, internally consistent baseline using
  these relationships. Shared reference records remain shared while workspace
  records are seeded or cloned per workspace. It implements the catalog-release
  and baseline manifests, workspace pins, per-workspace UUID mapping, and fixed
  evaluation times defined above.
- **Waypoint 1.6:** adds read-only APIs over these records, with pagination,
  filtering, standard problem responses, and developer smoke requests. Work-order
  evidence distinguishes originating incidents, affected units, and target units.
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

## Verification Plan and Current Coverage

This document satisfies the design portion of Waypoint 1.4 only. It does not
establish that new tables, constraints, repositories, or questions already work.
The implementation slices must add automated coverage for:

| Requirement | Required success and edge cases |
| --- | --- |
| Q1–Q5 semantics | Expected evidence IDs; no matches; unrelated incidents; join duplication; same fault versus different faults; recurrence threshold; missing classification; inclusive window start/exclusive end; due-time equality; blocked-and-overdue; completed/cancelled exclusion; zero versus absent stock; equality at reorder point. |
| Ownership and references | Two workspaces with matching human codes; rejected cross-workspace and cross-Facility links; all four WorkOrder reference combinations; allowed different incident-affected/work-target units at one Facility; no implicit target fallback; denied application writes to shared catalog rows; nonexistent release and mixed-release compatibility rejected. |
| Historical meaning and permissions | Approved updates succeed as the restricted role; direct SQL identity/model/Facility/reference updates fail even for unreferenced records; DELETE/TRUNCATE fail; old broad grants are removed; controlled owner repair remains possible without breaking constraints; occurrence time differs from seed insertion time; terminal timestamps remain consistent with status. |
| Waypoint 1.5 baseline contract | Repeated seed is stable; two workspace copies have disjoint operational UUIDs; foreign keys remap correctly; published catalog rewrites are rejected; old workspaces retain their release after a new baseline is published. |

The existing Facility tests cover the implemented foundation only. New behavior
remains an intentional coverage gap until its owning implementation slice; no
waypoint is marked complete by this documentation change. Live workspace reset,
reservations, and complete historical reconstruction are deferred scenarios.
