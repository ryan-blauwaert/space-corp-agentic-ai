# Structured Operational Queries

Waypoint 2.2 unit 1 defines contracts and evaluation fixtures; unit 2 adds the
read-only workspace session boundary. Unit 3 implements facility-equipment and
compatible-stock execution; unit 4 adds work-order, incident, and inventory
execution. Unit 5 adds model-guided planning, exact scoped entity resolution, and
query tracing. Repeatable live evaluation remains unit 6 work; answer synthesis
belongs to Waypoint 2.3. Q1–Q5 are canonical
acceptance examples, not an exhaustive list of legitimate user questions.

## Decision: bounded domain queries

The model proposes a domain query and typed filters. Application code validates
it, checks referenced entity visibility, and constructs parameterized SQL using approved
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

Each executor must check relationships, catalog pins, entity existence,
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
Unit 2 implements read-only transactions and statement timeouts. Units 3–4 validate
entity references/catalog pins and bound returned evidence. User/session authorization
and total orchestration deadlines remain caller/later-orchestration responsibilities. Broad filters must
never bypass those limits; excess nested evidence must fail explicitly rather than
be silently truncated.

`QUERY_PLAN` accepts executable shapes. `PLANNING_OUTCOME` additionally accepts
`declined` with `unsupported_question`, `prohibited_operation`, `missing_input`, or
`ambiguous_input`. Unsupported combinations are capability gaps; prohibited requests
violate policy. Missing/ambiguous inputs must not be guessed, and unsupported requests
must not be silently approximated by a different supported query. These are currently
terminal outcomes, not a multi-turn clarification implementation.

Errors remain `invalid_plan`, `not_found`, `model_failure`, `database_unavailable`,
`timeout`, and `resource_limit`, with trusted correlation and fixed safe messages. Do not log raw
validation errors, prompts, plans, or results wholesale. Hiding fields in repr is
only a precaution. Schema-valid plans can still be semantically wrong.

## Read-only workspace sessions (unit 2)

`Database.query_session(workspace_id, statement_timeout_ms=5000)` uses the existing
application engine and restricted application role. A fresh session begins an explicit
`REPEATABLE READ, READ ONLY` transaction before establishing transaction-local workspace
and statement-timeout settings. A UUID is required; the caller-owned timeout must be
an integer from 1 to 60000 milliseconds. Invalid inputs fail before connecting.

Repeatable read keeps evidence rows and their counts in one snapshot even if another
transaction changes records. PostgreSQL rejects writes to operational tables,
including explicit ORM flushes and writes flushed on context exit. The session and
transaction contexts roll back failures and close the session; transaction-local
settings reset on success and failure. Automatic transaction restart is disabled,
so accidental session use after commit, rollback, or context exit cannot silently
start an unscoped writable transaction. Ordinary `workspace_session` retains its
existing write behavior for operational code.

This follows [PostgreSQL transaction modes](https://www.postgresql.org/docs/current/sql-set-transaction.html),
[statement timeout behavior](https://www.postgresql.org/docs/current/runtime-config-client.html),
and [SQLAlchemy's explicit transaction lifecycle](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#disabling-autobegin-to-prevent-implicit-transactions).
The timeout bounds each statement, including lock waits, after setup; it is not a
connection timeout, total request deadline, row limit, or nested-result budget.

This helper is for trusted application-generated queries, not arbitrary SQL. Its
protection assumes the configured restricted role and trusted code that does not
replace transaction settings or deliberately start another transaction. It does
not authorize a supplied workspace, check workspace existence/catalog pins, or
sandbox all PostgreSQL functions and temporary-table effects. The model never
receives the session. Unit 2 introduced no new role, grant, environment variable,
or dependency; unit 3 adds the scoped pin-function grant described below.

Tests use the restricted application login and actual PostgreSQL to verify scoped
reads, cross-workspace invisibility, rejected SQL/ORM writes, snapshot consistency,
statement cancellation, setup/caller failures, early transaction closure, and
restoration of pooled settings. Ordinary operational writes still succeed afterward.

## Equipment execution (unit 3)

`app/queries/equipment.py` exposes `EquipmentQueryExecutor.execute(context, plan, page)`.
It revalidates input shapes before connecting and implements **all** documented
filters for `facility_equipment` and `compatible_stock`. Plans for the other three
domains go to `OperationsQueryExecutor`; submitting them to the equipment executor
returns `invalid_plan`. Neither executor interprets natural-language questions. The caller must authorize
the context; accepting a UUID is not user/session authorization.

The executor opens `Database.query_session`, resolves the pinned release, and checks
explicit Facility/unit/model identities. Missing, foreign-workspace, unpinned, or
wrong-release inputs fail as `not_found`. Facility results include only units of
models in the pinned release. The database's existing catalog-pin triggers enforce
this consistency on writes. Compatibility uses the unit's exact model and own
facility, preserving positive, zero, and unknown stock. An incident requirement is
applied only when incident statuses are supplied.

Queries use [SQLAlchemy SELECT expressions](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html)
with bound values and application-owned relationships. Facility matching uses an
incident EXISTS predicate to avoid duplicate units/facilities. Pagination applies
to distinct facilities or compatibility pairs, with separate totals in the same
snapshot. Ordering is Facility code/ID, unit asset tag/ID, incident reference/ID,
and component code/ID, matching the baseline oracle while adding stable tie-breakers.

The default evidence budget is 1000, configurable by trusted code from 1 to 10000.
For facilities it counts units plus incidents across the selected page; for stock
it counts supporting incident IDs plus returned components. Fetches use a bounded
sentinel row to detect excess nested evidence and return `resource_limit` rather
than silently truncating it. Top-level pagination remains caller-owned. The two
paths issue at most nine and seven statements respectively, including setup;
each data statement uses the session's five-second timeout. This bounds database
work without a model-driven query loop, but is not a wall-clock deadline for
connection establishment or future multi-operation orchestration.

Database statement cancellations map to `timeout`; other SQLAlchemy failures map
to `database_unavailable`, with fixed messages and no SQL/parameters in the exposed
error. Input validation failures are `invalid_plan`. No model call, HTTP endpoint,
answer synthesis, query telemetry, or retry loop is added in this unit.

### Catalog-pin access and local use

The application role cannot read `workspaces` directly. Migration
`0011_query_catalog_pin` adds `public.current_workspace_catalog_release()`, a no-argument
read-only SQL function returning only the pin for `app.workspace_id`. It uses
`SECURITY DEFINER`, a fixed `pg_catalog` search path, fully qualified table access,
and revoked PUBLIC execution; provisioning grants execution to `space_corp_app`.
This follows [PostgreSQL security-definer guidance](https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).
No workspace listing or administrative write access is granted. Like RLS, it trusts
the application's transaction workspace setting, not arbitrary model SQL.

Before using unit 3 locally, migrate **both** development and test databases to
head and rerun the provisioning script using the existing
[local setup steps](local-postgresql.md). Migration alone does not grant function
execution. The integration suite validates the migration and disposable-cluster
provisioning; it does not upgrade your development database.

After bootstrapping the documented dataset and configuring `.env`, a direct Python
smoke check (no model call) is:

```bash
.venv/bin/python - <<'PYTHON'
from uuid import uuid4
from app.config import Settings
from app.database import create_database
from app.queries.contracts import QueryContext
from app.queries.equipment import EquipmentQueryExecutor
settings = Settings()
assert settings.default_workspace_id is not None, "Configure the seeded workspace."
database = create_database(settings)
try:
    context = QueryContext(request_id=uuid4(), operation_id=uuid4(),
                           workspace_id=settings.default_workspace_id)
    response = EquipmentQueryExecutor(database).execute(
        context, {"operation": "facility_equipment",
                  "facility": {"facility_type": "lunar_installation"}})
    print(response.model_dump_json(indent=2))
finally:
    database.dispose()
PYTHON
```

## Operational execution (unit 4)

`app/queries/operations.py` exposes `OperationsQueryExecutor.execute(context, plan, page)`
for `work_orders`, `incidents`, and `inventory`. It honors every filter listed in the
query-language table, including unfiltered queries within the authorized workspace.
It uses the existing schema, catalog-pin function, and read-only sessions; unit 4
requires no additional migration, provisioning, dependency, endpoint, or role.

Both executors use `app/queries/execution.py` for request revalidation, pinned
workspace sessions, and safe database-error translation. The shared functions do
not route domains or perform model planning. Their extraction preserves the unit 3
public executor entry point and its evidence-budget behavior.

- Work queries apply status/priority membership, exact originating incident and
  target-unit filters independently, and facility selectors. Overdue filtering and
  returned flags use the same explicit `as_of`: active status, a non-null due time,
  and due time strictly before `as_of`. Completed/cancelled/unscheduled work is not
  overdue. Left-joined incident evidence preserves facility-level work, missing
  targets, and different incident-affected versus target units.
- Incident queries combine facility/unit/exact-model, status, severity, normalized
  fault, and half-open occurrence-window filters. An omitted model/unit filter
  preserves facility-level incidents; omitted fault filters preserve unknown fault
  classifications. Model filtering uses an EXISTS condition, with no work-order or
  compatibility join that could multiply incidents. `count` and page total reflect
  all matching distinct incidents, including when the selected page is empty.
- Inventory queries combine facility, component, exact-model compatibility, all five
  numeric comparison operators, and the below-reorder flag. Compatibility uses
  EXISTS so a component compatible with multiple models does not duplicate stock.
  The pinned catalog is enforced on components and explicit model references.
  Only recorded rows appear; zero, equality, and surplus remain distinguishable,
  with shortfall clamped at zero for equality/surplus.

Explicit entity references are checked independently of other filters. Missing or
foreign-workspace facilities/units/incidents, and missing or wrong-release catalog
references, return `not_found` even if another filter would yield no records.
Individually valid but incompatible filters produce an empty result. Existing
workspace-scoped foreign keys and catalog-pin triggers preserve relationship
integrity; the executor does not guess alternative entities or revisions.

Work and incident pages order by reference code then UUID. Inventory pages order
by Facility code, Component code, then inventory UUID. Each result uses a separate
count and row query in the same snapshot, and materializes at most the caller's
100-row page limit. These flat evidence results need no nested-evidence budget.
Each path executes at most eight statements including setup and optional reference
checks, with the existing five-second data-statement timeout. Connection time and
future multi-operation orchestration still need their own deadline policy.

For a direct smoke check, reuse the setup/context from the unit 3 example and call:

```python
from app.queries.operations import OperationsQueryExecutor

response = OperationsQueryExecutor(database).execute(
    context,
    {
        "operation": "inventory",
        "facility": {"facility_type": "lunar_installation"},
        "quantity": {"operator": "lt", "value": 2},
    },
)
print(response.model_dump_json(indent=2))
```

This retrieves recorded low-stock rows at lunar installations without requiring
that they also be below their reorder point. Model-generated plans, entity-name
resolution, query tracing, and a standalone evaluation command remain later work.

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

After unit 5, the full PostgreSQL-enabled suite passed: 916 tests, no failures or
skips, in 49.52 seconds. The 82 new tests cover strict proposal parsing, all 18
supported fixtures through the complete workflow in two workspaces, six controlled
decline responses, exact scoped references, ambiguous and unavailable references,
model failures, and correlated content-free traces. Ruff lint/format, mypy, and
whitespace checks passed. One existing Starlette/AnyIO deprecation warning remains.
No live model calls were made; these checks verify application behavior, not actual
model interpretation or decline accuracy. That coverage remains unit 6 work.

After unit 4, the full suite passed: 834 tests, no failures or skips, including
70 additional tests for operational queries and the shared execution boundary.
Ruff and mypy passed. One existing Starlette/AnyIO deprecation warning remains.
Integration coverage includes every canonical/extended fixture case in two workspaces,
all approved filters, boundary and contradictory conditions, independent work targets,
null references, count/page correctness, compatibility deduplication, and foreign or
wrong-release references. The existing equipment, session, migration, and provisioning
checks remain passing. No live model calls were made.

Unit tests cover canonical plan mappings, novel filter combinations, omitted-filter
semantics, nested malformed/unsafe fields, domain enums, numeric/time boundaries,
immutable evidence, normal/zero/unknown stock, broader work and incident results,
fixture integrity, and workspace-dependent fixture identities.

Remaining work stays in Waypoint 2.2: repeatable model/query evaluations, including
actual model intent and decline verification. Unit 5 tests the full application
workflow with controlled model responses for all 18 supported cases in two isolated
workspaces and all six declined cases. This does not measure natural-language
planning accuracy or answer quality. Waypoint 2.2 remains incomplete.

## Model-guided query workflow (unit 5)

`QueryService.ask(context, question, page)` returns a `QueryOutcome`: a validated
plan plus `QueryResponse` evidence, or a `DeclinedPlan` with no response. It does not
write an answer or expose an HTTP endpoint. `QueryContext` must come from trusted
caller authorization, never from model output. `page` remains caller-owned.

The implementation consists of three small modules:

- `app/queries/planning.py` owns the `bounded-query` version `1` prompt and strict
  JSON parser. Its schema is derived from the existing query contracts, widening
  UUID fields to literal reference strings only for the model proposal.
- `app/queries/resolution.py` resolves exact references through fixed parameterized
  statements inside a read-only workspace transaction. No entity directory or
  operational records are sent to the model.
- `app/queries/service.py` invokes the existing `ModelService`, validates and resolves
  the proposal, dispatches one existing executor, and records safe stage metadata.

The model receives only the question, schema, supported semantics, and current UTC
instant. Work orders require `as_of`: the prompt asks for the explicit question time,
otherwise the captured current instant. No active-status filters are silently added.
All supplied filters intersect; omitted filters retain the existing executor semantics.
The service makes one logical planning call (existing bounded retries may repeat an
attempt), with no repair loop, secondary planner, tools, or additional dependencies.

Before reference lookup, the parser rejects malformed JSON, duplicate keys,
non-JSON numeric constants, extra fields, invalid filters and invented references.
Each reference must occur literally in the question, ignoring case. References are
limited to 256 characters; names and codes use exact case-insensitive matching:

| Entity | Accepted references | Scope |
| --- | --- | --- |
| Facility | UUID, code, name | Authorized workspace |
| Equipment unit | UUID, asset tag | Workspace and pinned model release |
| Incident | UUID, reference code | Authorized workspace |
| Equipment model | UUID, code, name | Pinned catalog release |
| Component | UUID, code, name | Pinned catalog release |

Each lookup retrieves at most two matches. Multiple matches return `ambiguous_input`;
no match produces the safe `not_found` error. Neither reaches evidence execution.
A name matching one record and another record's code is also ambiguous. There is
no fuzzy matching, alias dictionary, conversation memory, or automatic disambiguation.
The final plan contains UUIDs and is revalidated by the selected executor. Resolution
and execution use separate transactions; the executor rechecks visibility and pins,
so resolution does not grant lasting access to a record.

This deliberately retains the existing text-only provider interface. OpenAI recommends
[native Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
for schema adherence; prompt-provided JSON plus strict application validation is our
incremental choice for this unit. Invalid output fails closed instead of being repaired.
This may increase format failures and does not guarantee correct interpretation.
Unit 6 must measure intent, records, and refusal behavior; native output constraints
can be considered if those results justify a provider-interface change.

### Bounds, failures, and traces

Questions are limited to 4,000 characters, returned plan text to 32,768 characters,
and model output to 4,096 tokens. The model timeout is 30 seconds per attempt;
`ModelService` permits at most three attempts with bounded retry delay. Existing
five-second SQL statement timeouts, bounded statement counts, 100-row page limit,
and equipment evidence limits remain in force. These are bounded individual stages,
not a hard wall-clock deadline including pool waits and all network activity.

Expected model errors, provider refusals, and incomplete output become `model_failure`.
Malformed plans become `invalid_plan`; database errors retain the existing safe query
categories. Programming errors propagate after a content-free `internal_error` trace.
No raw provider or SQL error is added to application telemetry.

The `app.queries.service` logger emits JSON `query_planning`, `query_resolution`, and,
only for executable plans, `query_execution` events. They share the request ID and
root `query_operation_id`; planning and resolution each receive a distinct operation
ID. Existing model attempt/operation events use the planning operation ID. Events
include duration, outcome, safe error category, approved operation, prompt/model
configuration on planning, and counts on successful execution. They exclude question
text, reference values, plans, workspace IDs, SQL, evidence, and exception bodies.
Declines do not open an evidence transaction. A model-supplied decline also needs no
reference lookup. See [model telemetry](llm-integration.md) for logging scope limits.

Read-only enforcement and scope limits remain deterministic even if the model
misinterprets a question. They cannot establish that a valid in-scope plan faithfully
answers that question, or that every prohibited request is correctly classified.
Those are explicitly separate evaluation responsibilities.

### Direct local usage

After migrating, provisioning, and seeding as documented, use the restricted
application database URL and a trusted seeded workspace in `.env`. This example
makes a paid model call; automatic tests use controlled providers instead.

```python
from uuid import uuid4

from app.config import Settings
from app.database import Database
from app.llm.configuration import configured_provider
from app.llm.service import ModelService
from app.queries.contracts import QueryContext
from app.queries.service import QueryService

settings = Settings()
assert settings.database_url is not None
assert settings.default_workspace_id is not None
assert settings.llm_model_id is not None

database = Database(str(settings.database_url))
try:
    with configured_provider(settings) as provider:
        outcome = QueryService(database, ModelService(provider), settings.llm_model_id).ask(
            QueryContext(
                request_id=uuid4(),
                operation_id=uuid4(),
                workspace_id=settings.default_workspace_id,
            ),
            "Which recorded stocks are below their reorder points at LUN-OPS-01?",
        )
        print(outcome.model_dump_json(indent=2))
finally:
    database.dispose()
```

Inspect `plan` before consuming `response`; a decline has `response=null`. The
output includes evidence and is for intentional local inspection, not routine logs.
Enable the existing application logging configuration if stage traces are desired.
A repeatable evaluation CLI is the next unit; this example is not that harness.
