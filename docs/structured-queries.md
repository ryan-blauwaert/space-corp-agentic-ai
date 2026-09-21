# Structured Operational Queries

Waypoint 2.2 is in progress. Unit 1 defines contracts and evaluation fixtures only.
It performs no model calls, database reads/writes, or query execution. The remaining
units add read-only sessions, Q1–Q5 execution, model planning, tracing, and evaluation.

## Scope and design

The model will propose one canonical operation and its typed inputs. Application
code will validate that proposal and construct a fixed parameterized query. Plans
have no SQL, table names, joins, arbitrary predicates, workspace selection, or
pagination controls. This deliberately supports Q1–Q5 rather than general SQL.
The illustrative roadmap question about lunar locations and a custom stock threshold
is outside this initial set and must be declined until an explicit extension exists.

Contracts use the existing Pydantic dependency. String-tagged
[discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)
select exactly one operation schema and reject unknown fields. No dependency or
framework is added. Validating a schema is not authorization, entity existence
checking, or proof that an answer matches a question.

## Plans and caller context

`app/queries/contracts.py` defines frozen values with unknown fields forbidden:

| Operation | Typed inputs | Fixed meaning |
| --- | --- | --- |
| Q1 | Optional `facility_id` | Degraded/offline units with unresolved incidents on the same unit; group evidence by Facility |
| Q2 | `equipment_unit_id` | Exact-model compatible components and local stock, requiring an unresolved incident |
| Q3 | `facility_id`, `as_of` | Active high/critical-priority work with blocked/overdue flags |
| Q4 | `equipment_model_id`, `fault_code`, `window_start`, `as_of` | Distinct same-fault incidents within the half-open time window |
| Q5 | `facility_id` | Recorded inventory strictly below its reorder point |

Identifiers are UUIDs. Plans refer to an exact model revision, not a family name.
Time inputs must be timezone-aware; accepted instants normalize to UTC. Q4 requires
`window_start < as_of`. Fault codes normalize by stripping whitespace and uppercasing,
with the domain's nonblank/64-character bound. Plans do not change the canonical
status, priority, recurrence, or shortage definitions.

`QUERY_PLAN` validates executable plan shapes. `PLANNING_OUTCOME` also accepts
`operation: declined` with one of four fixed reasons: `unsupported_question`,
`prohibited_operation`, `missing_input`, or `ambiguous_input`. A declined outcome
cannot validate as an executable plan. Declines do not authorize partial execution,
and no multi-turn clarification workflow is implemented here.

`QueryContext` is supplied by trusted application code and holds `request_id`,
`operation_id`, and `workspace_id`. Later orchestration will share the request UUID
with the 2.1 model call and use separate operation IDs for planning and execution.
The model cannot override this context. Trusted callers must still authorize it;
constructing the context itself grants no access.

`QueryPageRequest` is separate caller-owned input, using the existing default of
50 rows and maximum of 100, with a nonnegative offset. Values must be integers,
not booleans or strings. This adds no endpoint or generic pagination service.
Missing required inputs must not silently select an arbitrary entity. Defaulting
an interactive `as_of` to one server-captured instant belongs to later orchestration;
evaluation questions always specify the baseline's fixed instants.

## Structured evidence and errors

`QueryResponse` carries trusted context, the resolved catalog-release ID, and a
discriminated result. Each result contains a typed `EvidencePage` with immutable
row tuples, limit, offset, and total. The total describes all matching top-level
records before pagination. An empty page at a later offset does not mean no matches.
Nested Q1 evidence is not silently discarded to meet the top-level Facility limit;
execution and resource-bound behavior will be tested in the executor units.

- Q1 preserves distinct units and supporting incidents at each Facility. Local
  validation rejects duplicate unit/incident identities and unrelated unit evidence.
- Q2 preserves model/component compatibility pairs, incident IDs, inventory IDs,
  and quantities. Missing inventory has both ID and quantity null; recorded zero
  remains zero. `no_unresolved_incident`, `no_compatibility`, and `matched` are
  separate outcomes; a later empty page may still have `matched` status.
- Q3 labels originating incident, incident-affected unit, and work-target unit
  separately. Different units and absent targets remain valid. Unscheduled work
  cannot be overdue, and the blocked flag must agree with status.
- Q4's `count` equals the full distinct-incident total, not page length. `repeated`
  is true exactly when that total is at least two. Empty and single-occurrence
  results remain successful query outcomes.
- Q5 validates positive shortfall as reorder point minus recorded quantity.
  Equality and above-threshold stock cannot appear as shortage evidence.

Empty results describe matching records only, not facility health, repair suitability,
or unrecorded inventory. An unavailable/out-of-workspace input must instead fail as
`not_found`. The executor will validate database relationships, ownership, catalog
pins, date comparisons, and stable ordering; local result validation cannot prove
those facts from IDs alone.

`app/queries/errors.py` defines `invalid_plan`, `not_found`, `model_failure`,
`database_unavailable`, and `timeout` errors with caller correlation and fixed
messages. Declined plans are explicit outcomes, not database errors. Mapping
validation/provider/database failures into these categories is later work. Raw
Pydantic errors can include input; never log them, prompts, plans, or results
wholesale. Hiding result fields in representations is only a precaution.

## Versioned evaluation fixture

`data/evaluations/queries-1.json` references `demo-1` and `demo-catalog-1`, with a
SHA-256 of the validated baseline's canonical JSON using the existing dataset digest
function. The original baseline is unchanged. The fixture includes:

- 12 natural-language cases referencing every existing canonical scenario, including
  its authored inputs and exact expected evidence.
- Six declined cases covering missing inputs, ambiguity, unsupported forecasting,
  write requests, cross-workspace reads, and raw-SQL injection.
- Four global prohibited behaviors: writes, cross-workspace reads, raw SQL execution,
  and unvalidated execution. Every case must satisfy these prohibitions. Declined
  cases additionally prohibit operational query execution.

`scripts/query_evaluation_dataset.py` loads and validates fixture identity, digest,
coverage, unique case keys, decline categories, and evidence references. It resolves
`@collection:key` references into deterministic workspace/catalog UUIDs using the
existing baseline identity functions. The same substitutions render question text.
`ResolvedCase` holds the expected typed plan, typed result, and whether execution is
allowed. Supported cases use a first page of 100 for complete baseline evidence.

Expected plans come from authored scenario inputs; expected rows come from authored
scenario evidence, never executor output. The only result adaptation wraps existing
rows with pagination metadata and the operation tag. These references avoid a second
copy of the expected operational records. Shared catalog IDs remain the same across
workspaces; operational IDs change. Fixture expectations must never be sent to the
model as planning context.

This loader is not an evaluation runner and does not report model accuracy. Proving
that unsafe requests are declined and prohibited operations never execute requires
the later planner/executor tests and repeatable evaluation command.

## Unit 1 verification and remaining work

Tests mirror the new application and script modules. They cover plan variants,
rejected extra fields, required inputs, UUIDs, UTC/time boundaries, immutable values,
pagination bounds, Q1–Q5 evidence semantics, correlation/error messages, all fixture
cases, cross-workspace fixture identities, digest mismatches, and invalid references.

Verification: 647 tests passed with no failures or skips, including 121 new contract
and fixture tests. Ruff and mypy passed. One existing Starlette/AnyIO deprecation
warning remains.

Read-only enforcement, entity authorization, natural-language planning accuracy,
database result correctness, query tracing, and evaluation reporting are deliberately
unverified in this unit. Existing canonical SQL acceptance remains a baseline oracle,
not the new production query workflow. Waypoint 2.2 remains incomplete.
