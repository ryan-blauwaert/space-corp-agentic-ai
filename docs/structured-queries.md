# Structured Operational Queries

Waypoint 2.2 unit 1 defines contracts and evaluation fixtures. It does not yet
perform model calls, database queries, or answer synthesis. Q1–Q5 are canonical
acceptance examples, not an exhaustive list of legitimate user questions.

## Decision: bounded domain queries

The model proposes a domain query and typed filters. Application code will validate
it, authorize the referenced entities, and construct parameterized SQL using approved
relationships. Novel combinations of supported filters do not require a new question
identifier, prompt example, or executor branch for every natural-language question.

This is a small application-owned semantic surface rather than arbitrary SQL or a
new query framework. Semantic models are an established way to describe approved
business concepts and relationships; see [Snowflake's semantic view overview](https://docs.snowflake.com/en/user-guide/views-semantic/overview).
Our narrower implementation uses existing Pydantic
[discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)
and domain enums, with no new dependencies. A general expression tree, arbitrary
joins, grouped analytics, multi-query planning, and forecasting remain unsupported.
These are capability limits, not a claim that all other questions are unsafe.

## Query language

`app/queries/contracts.py` defines immutable plans with unknown fields forbidden at
every level. `operation` selects an evidence domain, never a Q1–Q5 identifier.

| Operation / plan | Approved filters | Result grain |
| --- | --- | --- |
| `facility_equipment` / `FacilityEquipmentPlan` | Facility, exact model revision, unit statuses, related incident statuses | Facilities containing matching units, with unit/incident evidence |
| `compatible_stock` / `CompatibleStockPlan` | Required unit; optional incident statuses | Exact-model compatible components with local stock, including unknown stock |
| `work_orders` / `WorkOrdersPlan` | Facility, statuses, priorities, target unit, originating incident, overdue flag; required `as_of` | Distinct work orders |
| `incidents` / `IncidentsPlan` | Facility, unit, exact model revision, statuses, severities, fault code, occurrence window | Distinct incidents |
| `inventory` / `InventoryPlan` | Facility, component, compatible model revision, quantity comparison, below-reorder flag | Recorded inventory items |

Facility filters support ID, facility type, and exact stored location. Supplied
filters combine with AND; a status/priority/severity list means membership in ANY
listed value. Lists are nonempty, bounded to 20 entries, and deduplicated. Omitted
or null filters impose no constraint. No hidden degraded/unresolved/high-priority/
shortage defaults remain. `{}` facility selection means the trusted workspace's
facilities, never all workspaces. Explicitly ambiguous language such as “the facility”
still requires clarification; it must not silently become an unfiltered query.

Quantity comparisons are `lt`, `lte`, `eq`, `gte`, or `gt` against a strict
nonnegative integer. `below_reorder_point: true` means quantity < reorder point;
false means quantity >= reorder point. These filters can intersect. Contradictory
but well-formed filters return no matches rather than silently removing a condition.

Occurrence windows are timezone-aware, UTC-normalized, start-inclusive/end-exclusive,
and require start < end. Fault codes are trimmed and uppercased. UUIDs identify exact
entities/revisions; names require later authorized resolution, not guessed IDs.
Work-order `as_of` is explicit so evidence and overdue filtering use the same instant.
Interactive orchestration may supply a single captured server instant when appropriate;
evaluation cases pin time. Overdue means an active order with due_at < as_of;
completed/cancelled and unscheduled orders are never overdue. Blocked means status=blocked.

For example, this plan can express a new combination of location, compatibility,
and a user-selected threshold without adding Q6:

```json
{
  "operation": "inventory",
  "facility": {"facility_type": "lunar_installation"},
  "compatible_model_id": "00000000-0000-0000-0000-000000000001",
  "quantity": {"operator": "lt", "value": 2}
}
```

The UUID is illustrative and must resolve in the pinned catalog before execution.
“Thermal control units” in the roadmap example must be resolved to an actual modeled
component or compatibility relationship; the planner cannot invent a classification
or equate unrecorded inventory with zero.

## Canonical examples remain acceptance requirements

| Scenario | Explicit query meaning |
| --- | --- |
| Q1 | Facility equipment with degraded/offline units and open/investigating incidents on those same units |
| Q2 | Compatible local stock for a unit, requiring open/investigating incident evidence |
| Q3 | Work orders with open/in_progress/blocked statuses and high/critical priorities, with time-based flags |
| Q4 | Incidents for an exact model and fault within the fixed occurrence window; count >= 2 establishes recurrence |
| Q5 | Recorded inventory below its reorder point at the selected facility |

The evaluation fixture now authors these plans explicitly. Business meaning is not
embedded in question identifiers in production contracts. The unchanged baseline
reference SQL remains an independent oracle for canonical scenarios.

## Evidence and interpretation

Results use the same domain operation tags as plans. Each contains a typed evidence
page with rows, total, limit, and offset. Total counts the complete matching result
grain, not the current page: facilities for `facility_equipment`, components for
`compatible_stock`, and distinct records for the other domains. A later empty page
does not mean no matches. No general aggregation language is introduced.

- Facility equipment results contain distinct units and incidents referencing only
  those units. Without an incident-status filter, units without incidents are allowed
  and linked incidents of any status may appear. With the filter, each returned unit
  must have a matching incident and only matching incidents are included.
- Compatible stock always uses the selected unit's exact model and own facility.
  When incident statuses are supplied, `incident_ids` contains the matching evidence;
  no match yields `no_incident_match` and no stock rows. Without the filter, no incident
  prerequisite applies and `incident_ids` is empty. `no_compatibility` means no catalog
  compatibility pairs; `matched` means pairs exist, even if stock is zero or unknown.
  Missing inventory has both ID and quantity null; recorded zero stays zero.
- Work-order evidence preserves originating incident, incident-affected unit, and
  independent target unit. Broader status/priority results are valid.
- Incident evidence includes facility, nullable unit, fault, status, severity, and
  occurrence time. `count` equals the distinct-incident total. A count across mixed
  faults/models is not automatically evidence of same-fault recurrence; Q4 supplies
  the required filters. The old universal `repeated` flag has been removed.
- Inventory evidence includes facility and component IDs. Shortfall is
  max(0, reorder point - quantity), so normal and excess stock have zero shortfall.
  Only recorded stock is queried here; absent inventory is not synthesized as zero.

The future executor must check relationships, catalog pins, entity existence,
filter satisfaction, stable ordering, and complete nested evidence. Local shape
validation alone cannot establish these facts or authorize a request. An unavailable
or out-of-workspace explicit entity fails as `not_found`; a valid filtered query
with no matching records succeeds with empty evidence. Empty results do not prove
facility health, repair suitability, or absence of unrecorded stock.

## Trusted execution boundary

`QueryContext` holds caller-supplied request, operation, and workspace IDs.
`QueryPageRequest` separately controls pagination (default 50, maximum 100).
Neither is model-generated. The plan cannot choose workspace, catalog release,
SQL, table/column names, arbitrary joins, pagination, or execution limits.
Authorization, read-only transactions, timeouts, and result/resource bounds remain
application/database responsibilities for subsequent units. Broad filters must
never bypass those limits; excess nested evidence must fail explicitly rather than
be silently truncated.

`QUERY_PLAN` accepts executable shapes. `PLANNING_OUTCOME` additionally accepts
`declined` with `unsupported_question`, `prohibited_operation`, `missing_input`, or
`ambiguous_input`. Unsupported combinations are capability gaps; prohibited requests
violate policy. Missing/ambiguous inputs must not be guessed, and unsupported requests
must not be silently approximated by a different supported query. These are currently
terminal outcomes, not a multi-turn clarification implementation.

Errors remain `invalid_plan`, `not_found`, `model_failure`, `database_unavailable`,
and `timeout`, with trusted correlation and fixed safe messages. Do not log raw
validation errors, prompts, plans, or results wholesale. Hiding fields in repr is
only a precaution. Schema-valid plans can still be semantically wrong.

## Versioned evaluation cases

`data/evaluations/queries-2.json` replaces the unpublished `queries-1` contract fixture
with a new version because plan/result shapes changed. Git retains the original.
The baseline `demo-1`, its digest, and `demo-catalog-1` are unchanged.

The fixture contains 12 canonical cases, six additional supported combinations,
and six declined cases. Additional cases cover lunar custom stock thresholds,
stock at the reorder point, completed work, resolved incidents without a fault/time
restriction, offline equipment without incidents, and compatibility without an
incident prerequisite. They demonstrate generalization across all five domains.

Supported cases author an expected plan plus either a baseline scenario reference
or an explicit result. The loader resolves `@collection:key` references and validates
both against the production contracts, including matching operation tags. Baseline
adaptation adds record provenance from the baseline and preserves canonical record
sets; it never obtains expectations from a query executor. Q4 recurrence is checked
against the baseline count and represented by the incident count in the new result.
Additional expected rows are authored in the fixture. Never send fixture expectations
to the model as context.

All cases prohibit writes, cross-workspace reads, raw SQL execution, and unvalidated
execution. Shared catalog IDs stay stable across workspaces while operational IDs
change. Dataset identity, digest, coverage, reference validity, and exclusive evidence
sources are checked before model/database work. Template dictionaries exist only to
allow symbolic fixture IDs; resolved execution contracts remain typed and closed.

## Verification and remaining units

The full suite passed: 700 tests, no failures or skips, including 174 query
contract/error/fixture tests. Ruff and mypy passed. One existing Starlette/AnyIO
deprecation warning remains.

Unit tests cover canonical plan mappings, novel filter combinations, omitted-filter
semantics, nested malformed/unsafe fields, domain enums, numeric/time boundaries,
immutable evidence, normal/zero/unknown stock, broader work and incident results,
fixture integrity, and workspace-dependent fixture identities.

Remaining work stays in Waypoint 2.2: read-only query sessions; domain executors that
honor every advertised filter; model planning and authorized entity resolution;
tracing; and repeatable evaluation of both canonical and additional questions.
Executor tests must verify filter intersections and join/count correctness, not just
schema acceptance. Model evaluations must check unfamiliar combinations and silent
question substitution as well as unsafe requests. There is no query runner yet, and
unit tests do not prove model accuracy, authorization, or database enforcement.
Waypoint 2.2 remains in progress; no answer synthesis or later-waypoint infrastructure
is introduced by this rework.
