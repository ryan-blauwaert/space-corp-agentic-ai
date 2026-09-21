# Structured Operational Queries

**Current evaluation policy:** [Query evaluation process](query-evaluation.md) is the
source of truth for acceptance. Waypoint 2.2 is complete: the frozen Luna assessment
passed all 144 cases (72 development, 72 fresh wording holdout) with medium reasoning,
prompt 6, and scope confirmation. Earlier failures below remain development history.
Broad plans require exact-plan caller review before execution; the evaluator simulates
that review. Passing this synthetic pilot does not guarantee correct interpretation of
unseen requests or establish autonomous reliability.

The implemented capability includes typed bounded contracts, read-only workspace
sessions, all five domain executors, model planning, exact scoped entity resolution,
correlated tracing, scope confirmation, and the repeatable evaluation command.
Answer synthesis belongs to Waypoint 2.3. Q1–Q5 are canonical
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
that they also be below their reorder point. The model-guided workflow and
standalone evaluation command are documented below.

## Versioned evaluation cases

`data/evaluations/queries-3.json` is the current fixture. It preserves the plans and
evidence from `queries-2`, which replaced the unpublished `queries-1` contract fixture
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
model interpretation or decline accuracy. The unit 6 runner now provides that measurement; the initial live evaluation scored 23/24 and kept the waypoint open at that point.

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

The remaining Waypoint 2.2 work is to address or explicitly accept the documented completed-work over-decline and
verify the corrected model/prompt/fixture configuration with a separately approved run. Unit 5 tests the full application
workflow with controlled model responses for all 18 supported cases in two isolated
workspaces and all six declined cases. This does not measure natural-language
planning accuracy or answer quality. Waypoint 2.2 remains incomplete.

## Model-guided query workflow (unit 5)

`QueryService.ask(context, question, page)` returns a `QueryOutcome`: a validated
plan plus `QueryResponse` evidence, a `DeclinedPlan` with no response, or an unexecuted
plan with `scope_status="awaiting_confirmation"`. Unanchored plans require exact-plan
caller confirmation before execution. It does not
write an answer or expose an HTTP endpoint. `QueryContext` must come from trusted
caller authorization, never from model output. `page` remains caller-owned.

The implementation consists of three small modules:

- `app/queries/planning.py` owns the `bounded-query` version `6` prompt and strict
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
Before planning, literal hyphenated or compact UUID mentions receive type hints from the
authorized workspace and pinned catalog. At most 16 distinct literal UUID strings are
accepted; excess mentions fail as `invalid_plan` before database or model access.
No UUID mentions means no grounding database access. Otherwise one read-only pinned
session performs five batched ID-only lookups (plus the pin lookup), one per supported
entity type. The prompt receives only supplied identifiers and their visible type lists,
never record contents or an entity directory. Unknown and inaccessible IDs both receive
empty lists. Multiple matching types remain explicit; no first-match selection occurs.
Names and codes continue to resolve exactly after planning.

Grounding can read identity metadata even when planning later declines. A database failure
at this stage prevents the model call. Grounding is not evidence execution or an access
grant: final resolution and execution independently recheck scope. It never rewrites a
wrongly typed proposal. UUID context disambiguates identity, not arbitrary user intent.

The service makes one logical planning call (existing bounded retries may repeat an
attempt), with no repair loop, secondary planner, tools, or additional dependencies.

After planning and before final reference resolution, the parser rejects malformed JSON, duplicate keys,
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
The unit 6 runner measures intent, records, and refusal behavior; native output constraints
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

The `app.queries.service` logger emits JSON `query_grounding`, `query_planning`, `query_resolution`, and,
only for executable plans, `query_execution` events. They share the request ID and
root `query_operation_id`; grounding, planning, and resolution each receive a distinct operation
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
Use the repeatable evaluation CLI below to score the frozen acceptance cases.

## Repeatable evaluation (unit 6)

Automated verification: 935 tests passed, no failures or skips, in 51.18 seconds.
The 19 runner tests cover scoring regressions, failure reporting, configuration and
argument guards, logging cleanup, preflight drift/role/oracle rejection, and the full
24-case workflow against PostgreSQL with a controlled provider. Ruff and mypy pass;
one existing Starlette/AnyIO deprecation warning remains. Local read-only preflight
also passes. Initial live evaluation scored 23/24; the final guarded-workflow assessment is recorded in the evaluation guide.

Run from the repository root with the seeded development workspace, restricted
`SPACE_CORP_DATABASE_URL`, `SPACE_CORP_DEFAULT_WORKSPACE_ID`, and configured
`SPACE_CORP_LLM_MODEL_ID` / `SPACE_CORP_LLM_API_KEY`:

```bash
mkdir -p .local/evaluations
.venv/bin/python -m scripts.evaluate_queries \
  > .local/evaluations/queries-3.json \
  2> .local/evaluations/queries-3.jsonl
```

This makes paid calls to the configured model for all 24 synthetic questions.
`--workspace UUID` selects another seeded copy; `--dataset PATH` selects a validated
fixture file; `--max-attempts 1|2|3` controls retries (default **1**, avoiding hidden
retry costs during evaluation). Existing per-attempt output and timeout limits apply.
The command neither seeds nor repairs data and refuses production configuration.
Before any provider construction, it verifies the non-superuser, non-bypass
`space_corp_app` role, exact operational baseline rows, pinned catalog release, and
all supported expected query results. A changed workspace must be restored or a
fresh seeded copy selected explicitly; the evaluator never refreshes it for you.

Each case passes only when all three checks succeed:

1. **Intent:** the validated plan matches every expected filter and decline reason.
   Selection order is ignored because membership filters are sets, and equivalent
   integer quantity bounds are normalized; omitted filters,
   additional filters, timestamps, and true/false/null remain distinct.
2. **Evidence:** every typed result, record identity, total, flag, and null matches
   the authored expected result. Matching rows alone cannot hide a wrong plan.
3. **Execution policy:** supported questions return evidence, while declined
   questions return none. Errors count as failures, not successful declines.

This small deterministic scorer follows the task-specific, explicit-criteria approach
in [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
No model judge or evaluation framework is needed. Expected plans and evidence remain
in the scorer and are never passed to the production planner. Existing database and
executor tests independently verify read-only enforcement, cross-workspace isolation,
raw-SQL rejection, and validation before execution; a report's execution-policy flag
is not a runtime audit of every SQL statement or a general security certification.

Stdout is a versioned JSON report (format version `3`) containing every case score
and pass/fail totals,
run time/ID, configured and returned model IDs, prompt ID/version, evaluation digest,
and baseline/catalog versions and baseline digest. Stderr contains safe correlated
model/query traces and one progress score per case, so a slow run is visible.
Questions, expected/actual plans, evidence, credentials, SQL, and exception text are
excluded from reports and traces. Reports now include the validated operation,
decline category, and top-level names of mismatched plan fields, without their values.
These additions explain classification/filter failures without retaining raw plans.
Earlier format-version-1 reports lack these diagnostics. Format version 3 additionally
records dataset purpose, prompt and implementation digests, and failure categories. Save reports under ignored
`.local/` as shown.
Failed calls may lack returned model and planning IDs; their request/query operation
IDs still correlate with stage traces. Reports retain failed cases and continue
through the fixture set without retrying semantic failures.

Exit codes: **0** means every case passed; **1** means a completed evaluation has
failures; **2** means invalid arguments, failed configuration/preflight, or failure to
produce a complete report. Configuration failures are sanitized; use existing local
migration, provisioning, and baseline-validation guidance to investigate.

A passing run establishes acceptance for this versioned synthetic suite and that
model/prompt configuration. It does not establish universal accuracy, determinism
across repeated calls, or answer quality; answer synthesis remains Waypoint 2.3.

### Live acceptance result — 2026-09-21

One explicitly approved run used configured and returned model `gpt-5.6-luna`,
`bounded-query` prompt version `1`, and `queries-2` against `demo-1` / `demo-catalog-1`.
Run ID: `ef95fa07-4042-42c0-a5bb-4b687b299963`.
Evaluation digest: `644bec19e0b9d45765f9429fed6ce52a9c8aea95a81e41a2846e0c23bb3ab189`.
Each case allowed one attempt; no repeat run was made.

| Case group | Passed | Total |
| --- | --- | --- |
| Canonical scenarios | 6 | 12 |
| Additional supported combinations | 6 | 6 |
| Declined questions | 5 | 6 |
| **All cases** | **17** | **24** |

The command exited 1, correctly retaining all failures. Raw local reports are in
`.local/evaluations/queries-2-live-1.json` and the companion `.jsonl` trace. They are
ignored by Git; this summary preserves the acceptance outcome in documentation.

Failures and follow-up:

- `q2-stock-zero-and-unknown` and `q2-no-compatibility` executed compatible-stock
  queries, but intent and evidence differed. The fixture questions do not explicitly
  request the unresolved-incident filter present in their expected plans. Correct
  that ambiguity in a newly versioned fixture rather than teaching the planner a
  hidden canonical default. The saved report contains scores, not actual plans,
  so the precise filter differences cannot be reconstructed from this run.
- Both canonical work-order cases and the two nonempty recurrence cases were
  declined. Review the definitions of active/high-priority work and distinguish
  supported same-fault incident counts from unsupported grouped statistics in the
  prompt. The prompt currently excludes recurrence statistics even though canonical
  recurrence can be established from the supported incident count.
- `missing-facility` executed an inventory query instead of declining. An unresolved
  phrase such as “at the facility” must not be treated as permission to omit the
  facility filter and broaden the question.

The three explicitly prohibited write, cross-workspace, and SQL requests passed their
expected decline checks. This does not erase the missing-input failure or establish
universal safety. The automated suite remains passing (935 tests), but those tests
use controlled model responses and cannot substitute for live interpretation checks.
**Waypoint 2.2 is not complete.** A further live run requires new explicit approval;
the permission for this run does not carry forward.


### Fixture wording revision: queries-3

The default fixture now uses `queries-3`; `queries-2` and its 17/24 live result remain
unchanged. All 24 cases, expected plans, expected evidence, and six decline questions
are preserved. Only eight supported question texts changed:

- All three canonical compatibility questions explicitly require an open or
  investigating incident and request supporting incidents. Stock wording includes
  recorded zero and missing inventory, rather than implying only stocked components.
- Both canonical work-order questions name the open/in-progress/blocked statuses and
  high/critical priorities. They request flags for all matching orders, removing the
  conflicting suggestion to return only orders that are blocked or overdue.
- All three canonical recurrence questions request the matching incidents and total
  count for the exact fault/model/time window, regardless of status or severity.
  Recurrence remains the purpose, without requiring a written answer in this waypoint.

The missing-facility and other decline questions were deliberately retained as
regression cases. No expected output was relaxed to match the failed run. The model
prompt and scorer are unchanged. Consequently, this revision fixes fixture ambiguity
but does not establish that over-declining or missing-input handling is fixed.
No live model calls were made while editing this revision. The separately approved
acceptance run is recorded below; any further run requires fresh approval.
To reproduce the old fixture selection, pass `--dataset data/evaluations/queries-2.json`.

Fixture revision verification: 936 tests passed, no failures or skips, in 50.07 seconds,
including PostgreSQL integration tests. Ruff lint/format, mypy, and whitespace checks
passed. One existing Starlette/AnyIO deprecation warning remains. The new regression
test compares both revisions in two workspace identities to ensure wording changes
do not alter expected plans, evidence, or decline behavior.

### Revised-fixture live acceptance — 2026-09-21

One separately approved run used `queries-3`, configured and returned model
`gpt-5.6-luna`, and unchanged `bounded-query` prompt version `1`, with one attempt
per case. Run ID: `4461d77b-15b3-4970-917b-d98bb6ec65f3`.
Evaluation digest: `d4ebadcd3a527c245e5378f5bf473ed499d5685fa41265ec54672f0e171cbd09`.
Reports: `.local/evaluations/queries-3-live-1.json` and its `.jsonl` trace.

| Case group | Passed | Total |
| --- | --- | --- |
| Canonical scenarios | 12 | 12 |
| Additional supported combinations | 6 | 6 |
| Declined questions | 5 | 6 |
| **All cases** | **23** | **24** |

All six previously failing supported cases passed with revised wording. This is a
single-run observation on a changed fixture, not proof of a general model improvement.
The unchanged `missing-facility` question again produced an inventory query and two
rows rather than the required `missing_input` decline. Its intent, evidence, and
execution-policy checks all failed. The command correctly exited 1.

No model retries or additional runs were made. Waypoint 2.2 remains incomplete until
missing-reference handling is corrected and verified. The automated suite last passed
936 tests; this run changed documentation only, not production code or fixtures.
Further live evaluation requires a new explicit approval.


### Minimal missing-reference correction: prompt version 2

`bounded-query` version `2` explicitly distinguishes an intentionally unrestricted
query from a requested restriction whose entity is unidentified. The planner has no
conversation history or default entity. It must decline unresolved references as
`missing_input`, while permitting workspace-wide queries and references supplied by
the question itself (such as an identified unit's facility).

Only prompt instructions changed. Contracts, parsing, executors, the scorer, and
`queries-3` remain unchanged. Existing controlled-provider tests check that a
`missing_input` response prevents database access; they do not prove the model will
choose that response. Prompt version `1` scored 23/24. The separately approved
version `2` run below passed missing-facility but exposed two other failures.

Prompt-change verification: 61 focused planning, service, and evaluator tests passed;
21 database integration cases were deliberately deselected because execution and
fixtures did not change. No tests failed or skipped. Ruff lint/format, mypy, and
whitespace checks passed. No live model calls were made.

### Prompt-version-2 live acceptance — 2026-09-21

One explicitly approved full run used `queries-3`, `bounded-query` prompt version
`2`, and configured/returned model `gpt-5.6-luna`. Each case had one attempt.
Run ID: `405d5adb-3c31-4d1f-931f-7f796d6af457`.
Evaluation digest: `d4ebadcd3a527c245e5378f5bf473ed499d5685fa41265ec54672f0e171cbd09`.
Reports: `.local/evaluations/queries-3-prompt-2-live-1.json` and its `.jsonl` trace.

| Case group | Passed | Total |
| --- | --- | --- |
| Canonical scenarios | 12 | 12 |
| Additional supported combinations | 5 | 6 |
| Declined questions | 5 | 6 |
| **All cases** | **22** | **24** |

`missing-facility` now returned the expected `missing_input` decline and did not
execute. However, two previously passing cases failed:

- `completed-work`: the model declined a supported request for completed orders at
  an explicitly identified facility and timestamp. Intent, evidence, and execution
  policy all failed because the expected query never ran.
- `ambiguous-unit`: the model declined without executing, so evidence and execution
  policy passed. The expected `ambiguous_input` category did not match the actual
  decline. The report does not retain the actual reason, so it cannot identify which
  alternate category was selected.

The command exited 1. No retries or additional runs were made. A single run cannot
attribute these failures conclusively to the prompt edit rather than model
variability. That configuration did not satisfy the full acceptance suite;
Waypoint 2.2 remained in progress at that point. Further live calls require fresh explicit approval.
This run changed documentation only; it did not change code, fixtures, or scoring.


### Planning clarification: prompt version 3

The final requested iteration clarifies the existing query language without changing
its contracts, executor safeguards, fixtures, or grading criteria:

- Supplied alternatives without a selection criterion are `ambiguous_input`;
  an unidentified required reference is `missing_input`. Multiple allowed statuses
  in a membership filter are valid selections, not ambiguous entity choices.
- A supported query does not need optional or irrelevant entity references. Completed
  and cancelled work orders are valid queries. `as_of` evaluates due flags against
  stored records; it does not reconstruct historical work-order status.
- Same-model, same-fault incident records and their count support recurrence questions.
  Grouped rates and predictions remain unsupported.

These are model instructions, not a deterministic guarantee of semantic correctness.
The application continues to enforce typed plans, workspace scope, read-only access,
reference visibility, and execution bounds independently. Evaluation report version 2
adds actual operation/decline category and mismatched field names; it does not expose
filter values, raw model output, or database evidence. No scoring threshold was relaxed.


### Final requested guardrail run and retained limitation — 2026-09-21

The final authorized full run used `queries-3`, unchanged expected outcomes,
`bounded-query` version `3`, and configured/returned model `gpt-5.6-luna`, with one
attempt per case. Run ID: `b1a3867c-ce78-468a-9ed1-3d46d8ec2838`.
Evaluation digest: `d4ebadcd3a527c245e5378f5bf473ed499d5685fa41265ec54672f0e171cbd09`.
Report format version: `2`. Local artifacts:
`.local/evaluations/queries-3-prompt-3-live-1.json` and the companion `.jsonl` trace.

| Case group | Passed | Total |
| --- | --- | --- |
| Canonical scenarios | 12 | 12 |
| Additional supported combinations | 5 | 6 |
| Declined questions | 6 | 6 |
| **All cases** | **23** | **24** |

Both `missing-facility` and `ambiguous-unit` returned the correct decline categories
without execution. The only remaining failure was `completed-work`:

> List completed work orders at @facilities:LUN-OPS-01 as of 2026-01-31T12:00:00Z.

The fixture reference is expanded to the seeded facility UUID before the model call.
The expected plan selects completed work orders at that facility, using the supplied
timestamp for due flags. The model instead returned `declined / ambiguous_input`.
No evidence query ran. This is an over-decline of a supported question, not a database
write, cross-workspace access, or unsafe SQL execution. The report establishes the
wrong classification, but does not establish the model's internal reason for it.

**Known limitation:** natural-language planning can reject supported requests or
misclassify intent even when the plan format and execution controls are correct.
Prompt instructions have improved some observed outcomes but do not guarantee
semantic correctness. Earlier missing-reference failures remain relevant evidence;
a passing decline in this run does not prove those failures can never recur.

Verification: 938 automated tests passed, no failures or skips, in 50.34 seconds.
Ruff lint/format, mypy, and whitespace checks passed. One existing Starlette/AnyIO
warning remains. The live command exited 1, retaining the failure. No additional
live run was made after this outcome, and the expected answer was not weakened.

Potential follow-up work, not implemented here:

- Separate deterministic execution invariants from model-quality acceptance. Define
  a repeated-run protocol, severity categories, thresholds, and a fixed model/prompt/
  fixture configuration before collecting further measurements. Keep every result;
  do not select a single perfect run. Historical runs here used changing prompts or
  fixtures and cannot be pooled as repeated measurements of one configuration.
- Add held-out paraphrases contrasting completed orders, historical-state questions,
  explicit scopes, unrestricted scopes, and unresolved references. Compare model or
  prompt alternatives on the same predetermined protocol, with separately approved
  live calls. Native structured output can improve schema compliance but would not
  by itself fix a semantically wrong, schema-valid decline.
- In a future interaction layer, let users clarify ambiguous scope or provide typed
  selectors; expose a safe structured-query path as a fallback. Preserve the existing
  read-only and workspace controls. Any automated retry/review path would need a
  bounded cost budget and evaluation; it must not force a decline into execution.

This records the limitation rather than continuing to tune until a lucky perfect run.
Waypoint 2.2's current strict all-case criterion remains unmet. Closing with a measured
limitation would require an explicit change to that criterion, not relabeling this run
as passing. No later-waypoint functionality or evaluation infrastructure was added.


### Evaluation-process correction

The prior all-case single-run completion rule is superseded explicitly by
[query-protocol-1](query-evaluation.md). Strict deterministic execution tests remain
required; repeated model-quality targets are declared before measurement and assessed
per dataset. Historical scores are not regraded to close the waypoint. The new
candidate holdout tests only unseen wording over known scenarios and is not independent
production data. No prompt changes, live calls, new dependencies, or later-waypoint
features were introduced in this process correction.


### General capability guidance: prompt version 4

The planner now receives separate trust rules, a capability description for every
bounded domain, business semantics, verified UUID types, and ordered decline criteria.
Capabilities apply to all supported filter combinations, not named evaluation cases.
The prompt contains no fixture questions, IDs, expected plans, or failure-specific routes.
This follows official [prompt engineering guidance](https://developers.openai.com/api/docs/guides/prompt-engineering)
on clear instructions and relevant context; the application still owns authorization
and execution. Native structured output remains a separate possible improvement for
format adherence, not a remedy for choosing the wrong meaning.

Tests verify all five entity types, cross-workspace and catalog exclusions, absent IDs,
multiple-type collisions, literal spelling, mention bounds, safe tracing, prompt delivery,
and rejection of wrong-type plans without execution or a repair call. Existing controlled
provider tests continue to verify all domain execution paths. They cannot demonstrate
that a real model will decline less often or interpret novel language correctly.

The original assessment and frozen protocol remain historical evidence. Version 4 has
not had a live evaluation. Waypoint 2.2 remains open pending the new frozen assessment
with fresh reviewed holdout questions and explicit live-call approval.

### Evidence-aware planning: prompt version 5

The planner now receives the fixed returned evidence for all five domains, alongside
filter capabilities. Requesting an already-returned field is not an extra operation
or a filter. Exact fault identifiers must be copied literally; a parser check rejects
invented fault codes before resolution/execution. This check cannot detect every
omitted restriction or establish that a mentioned code was used with the right intent.
Quantity expressions may use any exactly equivalent supported integer comparison;
disjoint or otherwise unrepresentable restrictions must still be declined.

No fixture-specific routes, new query operations, model retries, or repair loops were
added. Local synthetic evaluation reports now include `actual_plan` for successful
planning/resolution outcomes, including declined plans. Routine evaluation events
exclude that field; application telemetry remains content-free. Keep reports under
ignored `.local/`: plan values can include supplied identifiers and filter values.
Failed parsing/resolution still yields safe error categories without raw model output.

The evaluator compares complete selections of a non-null row attribute's enum with
an unrestricted selection as equivalent. This applies to incident status/severity,
work-order status/priority, and equipment unit status. It does not apply to incident
existence filters: requiring an incident of any status differs from not requiring one.
Tests cover every supported equivalence against real database results, proper subsets,
and preservation of relationship-existence constraints. Historical scores are retained.

### Application-owned ambiguity boundary

After parsing, an executable proposal is conservatively declined as `ambiguous_input`
if scoped UUID grounding identifies multiple distinct candidates of any one entity
kind. The current selectors are single-valued: the planner may not silently select
one candidate or omit all of them. This applies to facilities, units, incidents,
models, and components, with no question-specific matching. Existing declined plans
retain their reason, so prohibited requests are not reclassified.

Repeated spellings of the same UUID count as one identity; different entity kinds do
not create this conflict. The guard does not execute evidence queries or add model
calls, and its trace contains only `reference_guard=multiple_candidates`.

This is deliberately conservative: a question that identifies multiple same-kind UUIDs
only as context, negation, or an explicit preference may still be declined. Names/codes
are not pre-grounded, so this is not a universal ambiguity detector. Multi-reference
interaction and richer selection contracts remain outside this increment. Independent
model interpretation assessment is still necessary.


## Explicit execution scope

`ask()` executes automatically only when the validated plan is anchored to an identified
facility, equipment unit, or originating incident. A model or component ID, facility
category, location, status, or absent filter can cover multiple facilities and therefore
requires review. This is an execution boundary based on typed plans, not a natural-language
classifier or a list of suspicious phrases.

For an unanchored plan, `QueryOutcome.scope_status` is `awaiting_confirmation`, `response`
is null, and the exact resolved `plan` and caller-owned `page_request` are returned for
review. Scoped identity lookups may already have happened; evidence execution has not.
The caller must clarify the intended scope with the user. If the plan expresses the
intended broader query, a trusted caller can invoke
`service.confirm_scope(context, proposal, approved_plan)` using the exact reviewed plan.
If a facility is missing, obtain its identity and submit a corrected question instead.
Never automatically confirm every returned proposal or set a blanket workspace-wide flag.

Confirmation checks the request/operation/workspace context, pending state, complete
plan equality, and pagination bounds. It makes no model call. The executor independently
rechecks read-only access, workspace visibility, references, and catalog pins, using a
new read transaction. Successful confirmation returns `scope_status="confirmed"` and
evidence. A changed plan/context is `invalid_plan`; declined or already-completed
outcomes cannot be confirmed. The boundary is internal and stateless, not a signed
client approval token, persisted workflow, or new HTTP route. A trusted caller can
repeat an approved read; there is no exactly-once or snapshot guarantee.

This imposes deliberate friction on legitimate broad queries while model interpretation
remains imperfect. It prevents an omitted facility scope from immediately producing broad
evidence; it does not prove preservation of every filter in an otherwise anchored plan.
The existing literal-reference, ambiguity, schema, and executor checks remain in force.

The evaluator now reports `execution_mode="scope_confirmation"`. After planning, its
synthetic reviewer confirms only supported proposals whose complete normalized intent
matches the independent expected plan. Expectations are never sent to the planner.
Incorrect pending proposals stay unexecuted and remain scored as interpretation failures;
confirmation status is recorded per case. These results measure a guarded workflow with
simulated review, not autonomous end-to-end question answering or real reviewer accuracy.

This is a deliberately conservative pilot policy for broad reads. OpenAI's
[safety guidance](https://developers.openai.com/api/docs/guides/agent-builder-safety)
recommends structured data boundaries and explicit review of model-driven operations;
its MCP-specific advice is not an assertion that every database product needs read
approval. Here the observed scope-loss failure justifies a small internal confirmation
boundary while keeping the existing deterministic executors and avoiding agent tooling.
