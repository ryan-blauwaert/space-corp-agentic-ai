# Project Roadmap

## Purpose

This roadmap defines the planned evolution of the Agentic AI Operations Platform from an empty repository to a production-style agentic AI system.

It is intended to be used by both humans and coding agents to:

- understand the current project phase
- identify the next logical unit of work
- avoid implementing later-stage capabilities prematurely
- track measurable project progress
- preserve architectural direction
- maintain an MVP-first development strategy
- distinguish foundational requirements from future enhancements

The project should evolve through small, independently reviewable increments.

A later waypoint should depend only on capabilities delivered by earlier waypoints.

No waypoint should require unfinished work from a future phase in order to be considered complete.

---

# Roadmap Principles

## 1. Build vertically when possible

Prefer delivering a thin but working capability across the necessary layers rather than building large horizontal infrastructure with no user-visible behavior.

For example:

Prefer:

> User can retrieve a real facility record through the API.

Over:

> Repository abstraction, event bus, cache layer, database framework, and service mesh exist but no user capability works.

---

## 2. Introduce complexity only when justified

New infrastructure should solve a demonstrated need.

Do not introduce:

- microservices
- message brokers
- vector databases
- agent frameworks
- workflow engines
- caches
- Kubernetes
- complex eventing

solely because they may eventually be useful.

Design boundaries early, but distribute components only when the benefit becomes concrete.

### Framework Guidance

LangChain and LangGraph are optional implementation candidates, not roadmap
requirements. Evaluate them when they reduce integration or workflow complexity,
while keeping domain contracts, authorization, persistence, execution, and
evaluation in application-owned interfaces. Framework choice must not be part of
a waypoint's acceptance criteria.

---

## 3. Every waypoint must be measurable

Each waypoint should define:

- capability delivered
- architectural value
- user value where applicable
- completion criteria
- tests or evaluation required
- artifacts produced

A waypoint is complete only when its completion criteria can be objectively verified.

---

## 4. Preserve working software

The main branch should remain runnable.

Each waypoint should leave the system in a coherent state.

Large rewrites should be avoided where incremental migration is possible.

---

## 5. Evaluation grows with capability

Testing and evaluation should be introduced at the same time as the behavior being evaluated.

Do not postpone all evaluation until the end of the project.

---

# Phase 0 — Development Foundation

## Objective

Establish a minimal, reliable development environment and repository structure.

No AI behavior is required during this phase.

The goal is to create a foundation on which all later work can safely build.

---

## Waypoint 0.1 — Repository Conventions

### Capability

The repository clearly communicates:

- what the project is
- how coding agents should work
- where the project is headed

### Deliverables

- `README.md`
- `PROJECT_BRIEF.md`
- `AGENTS.md`
- `docs/roadmap.md`

### Architectural Value

Creates durable project context outside of chat conversations.

Allows coding agents to operate using repository-defined expectations.

### Completion Criteria

- all four documents exist
- responsibilities of each document are clear
- `AGENTS.md` defines coding-agent behavior
- roadmap identifies current phase
- repository contains no unnecessary application infrastructure

### Status

- [x] Complete

---

## Waypoint 0.2 — Minimal Backend

### Capability

A local backend service can be started and queried.

### Deliverables

- minimal FastAPI application
- `/health` endpoint
- automated health endpoint test
- documented local run command
- documented test command

### User Value

Establishes the first executable component of the platform.

### Architectural Value

Creates the application boundary that future capabilities can build upon.

### Completion Criteria

- application starts locally
- `GET /health` returns HTTP 200
- automated test verifies expected response
- test suite passes
- no database, AI, RAG, authentication, or workflow dependencies exist yet

### Status

- [x] Complete

---

## Waypoint 0.3 — Application Configuration

### Capability

Application configuration is loaded consistently from environment-driven settings.

### Deliverables

Configuration support for at least:

- application environment
- application name
- logging level
- database URL placeholder

### Architectural Value

Prevents configuration from becoming hard-coded as the project expands.

Creates a stable configuration boundary for future services.

### Completion Criteria

- configuration is represented through a typed settings object
- application starts with default development configuration
- configuration can be overridden using environment variables
- tests verify at least one configuration override
- secrets are not committed

### Status

- [x] Complete

---

# Phase 1 — Structured Operational Backend

## Objective

Create the first real domain capability without involving AI.

At the end of this phase, the platform should expose useful structured operational information through ordinary deterministic application logic.

---

## Waypoint 1.1 — PostgreSQL Integration

### Capability

The application can connect to a PostgreSQL database.

### Deliverables

- database connection management
- local development database configuration
- migration mechanism
- database connectivity test
- documented workspace isolation approach, including connection and permission implications

### Architectural Value

Introduces durable structured state.

Creates the foundation for operational data, workflow state, evaluations, and audit records.

### Completion Criteria

- database can be started locally
- application successfully connects
- initial empty migration applies successfully
- automated test verifies database connectivity
- database startup and migration commands are documented
- workspace isolation direction is documented before domain schema implementation; the initial approach is workspace-scoped records in shared tables, with application authorization and PostgreSQL row-level security as additional enforcement

This waypoint records the isolation design only. Workspace records and enforcement begin with the domain schema; reviewer sessions and reset controls arrive in Waypoint 2.5.

### Status

- [x] Complete — 2026-09-07
- Verification: local PostgreSQL development and test databases connected successfully; `0001_initial` applied; full suite passed with real integration checks.
- Commit: `f45d96c feat: add PostgreSQL migration foundation`.
- Architectural decision: use shared workspace-scoped tables, application authorization, and future PostgreSQL row-level security; workspace persistence and enforcement begin in Waypoint 1.2.

---

## Waypoint 1.2 — First Domain Entity: Facility

### Capability

Facilities can be stored and retrieved.

### Example Entity

A facility may represent:

- lunar installation
- orbital station
- logistics depot
- mission control center

### Deliverables

- `Facility` domain model
- persistence model
- migration
- repository interface
- repository implementation
- basic CRUD or read capability
- minimal workspace identity and ownership for facility records; local development may use one default workspace

### User Value

The system contains its first meaningful operational data.

### Architectural Value

Establishes the pattern used for domain modeling and persistence.

### Completion Criteria

- facility record can be inserted
- facility can be retrieved by ID
- facility list can be queried
- automated repository tests pass
- domain and persistence concerns remain separated where practical
- facility repository operations require explicit workspace scope
- database permissions and row-level security enforce workspace isolation using an application role that cannot bypass those policies
- tests with two workspaces verify isolation and reject cross-workspace access

### Recommended Execution Substeps

1. Define workspace identity and facility ownership, then create the minimal domain and persistence models with their migration.
2. Implement typed repository operations with explicit workspace scope and tests for normal reads and missing records.
3. Configure database roles and row-level security, including safe workspace context handling when connections are reused.
4. Verify isolation using two workspaces and the actual application database role, including cross-workspace reads, writes, and connection reuse.

Keep these changes independently reviewable. All completion criteria still apply before this waypoint is complete; workspace enforcement remains outside Waypoint 1.1's connectivity implementation.

### Status

- [x] Complete — 2026-09-07
- Verification: full suite passed with 63 tests; 29 real PostgreSQL integration tests verified migrations, repository behavior, restricted application-role permissions, two-workspace RLS isolation, rejected cross-workspace writes, and transaction-local context reset on a reused pooled connection.
- Commits: `1a74dec feat: add facility domain model`, `4ba9ed8 feat: add facility repository`, `abc5b88 feat: enforce facility workspace isolation`, and `a52873d feat: harden PostgreSQL role isolation`.
- Architectural decision: `space_corp` owns schema migrations while `space_corp_app` is an unprivileged application role constrained by Facility row-level security and a transaction-local workspace context.

---

## Waypoint 1.3 — Facility API

### Capability

Users can retrieve facility data over HTTP.

### Example

`GET /facilities`

### Deliverables

- facility API routes
- typed request/response schemas
- service layer if justified
- endpoint tests

### User Value

First meaningful application capability exposed externally.

### Architectural Value

Establishes API → domain/service → repository layering.

### Completion Criteria

- facility list endpoint works
- single facility endpoint works
- invalid facility ID returns appropriate response
- API behavior is covered by automated tests
- facility API operations use a trusted workspace context and cannot select another workspace through arbitrary client-supplied identifiers
- response and error schemas, HTTP statuses, pagination limits, and stable OpenAPI operation identifiers are documented and tested
- API contract changes are reviewed for compatibility with existing consumers
- repeatable local smoke data makes successful list and detail responses manually verifiable outside the automated test suite

Until reviewer sessions are introduced in Waypoint 2.5, local API development may use a server-configured default workspace. This is not sufficient for public multi-user access.

### Status

- [x] Complete — 2026-09-07
- Commits: `2a164a0 feat: complete facility API`, `f27bd80 feat: add local API smoke data`, `a31c747 test: stabilize pytest imports`, and `51884e6 test: load local integration settings`.
- Verification: 144 tests passed with no skips against PostgreSQL 17, including disposable provisioning tests. The live local list and detail endpoints returned the repeatable smoke dataset through the restricted application role. A clean wheel build, installation outside the checkout, health/OpenAPI smoke check, and Git ignore checks passed.
- Completion-criteria coverage:
  - `tests/app/api/routes/test_facilities.py` verifies list/detail success, empty results, pagination, invalid IDs/queries, missing records, trusted workspace scope, cross-workspace denial, configuration failures, safe database errors, OpenAPI response formats, and stable operation IDs.
  - `tests/app/schemas/` verifies typed public responses and pagination/error schemas; `tests/app/api/test_errors.py` checks HTTP headers survive problem conversion.
  - `tests/app/test_database.py`, `tests/app/facilities/`, and `tests/scripts/test_provision_postgresql_application_role.py` verify transaction cleanup, migration round trips and invalid legacy data, domain/database constraints, real RLS enforcement, and least-privilege provisioning success/failure.
  - `tests/app/test_main.py` verifies application assembly and owned/injected database lifecycles. The original smoke-seed coverage is now superseded by `tests/scripts/test_seed_support.py`, `test_seed_dataset.py`, and `test_bootstrap_development.py`; `tests/scripts/test_test_environment.py` verifies automatic local integration-test configuration. `README.md` records the contract compatibility review and manual smoke workflow.
- Architectural decisions: retain synchronous SQLAlchemy routes and the existing FastAPI 422 format; use RFC 9457 problems for expected HTTP failures; keep workspace selection in server configuration until reviewer sessions; discover only application packages for wheel builds; grant application privileges explicitly per table.
- Scope: packaging, ignore rules, PostgreSQL safeguards, and documentation repair the existing foundation. No new application dependencies, authentication, AI, Docker configuration, CI, or additional services were introduced.
- Known limits: database outage responses are tested through injected operational failures rather than a live outage drill; verification used Python 3.14 and PostgreSQL 17, not a full version matrix. One existing Starlette/AnyIO deprecation warning remains. These do not leave an active completion criterion uncovered. Dependency locking, lint/type-check tooling, and later infrastructure remain follow-up work.
- Post-completion enhancement: a guarded, repeatable development seed creates the configured workspace and enough deterministic Facility data for local endpoint smoke testing. This remains intentionally smaller than the complete synthetic dataset in Waypoint 1.5.

---

## Waypoint 1.4 — Core Operational Schema

### Capability

The database represents enough of the fictional organization to support meaningful operational questions.

### Initial Entities

Recommended minimum:

- Facility
- CatalogRelease
- EquipmentModel
- EquipmentUnit
- Component
- InventoryItem
- Incident
- WorkOrder

### Architectural Value

Creates the minimum relational world required for later structured reasoning.

### Recommended Execution Units

Implement this waypoint as small vertical slices rather than a single schema-only
change:

1. document the first canonical operational questions, entity relationships,
   lifecycle states, and data-ownership model
2. add CatalogRelease, EquipmentModel, and EquipmentUnit
3. add Component and InventoryItem
4. add Incident and WorkOrder
5. verify that the complete model is traceable to the canonical questions,
   including the entities, relationships, fields, constraints, and repository
   query paths each question requires

Each entity slice includes its migration, typed domain and persistence models,
repository coverage, workspace-isolation checks, required role grants and RLS
policies, and enough deterministic smoke data to exercise the capabilities it
introduces.

### Completion Criteria

- the schema design is traceable to the five canonical questions Q1–Q5 in
  `docs/operational-data-model.md`: each question's required entities,
  relationships, predicates, evidence, and time semantics are represented in
  the documented model; complete seeded scenarios and natural-language query
  execution are deferred to Waypoints 1.5 and 2.2
- entity relationships, lifecycle states, and an ownership matrix are documented
- the ownership matrix distinguishes workspace-owned records from intentionally
  shared immutable reference data and identifies the migration owner and
  restricted application-role access for each table
- migrations create the schema
- foreign-key constraints enforce valid relationships
- check constraints or typed enumerations enforce documented lifecycle values
- `catalog_releases` supplies a stable relational identity; model/component
  revisions reference it and composite foreign keys reject mixed-release compatibility
- incident fault classification and occurrence time support recurrence queries;
  work-order due times and terminal timestamps follow the documented semantics
- WorkOrder accepts an optional originating Incident and optional target Unit,
  including both or neither; incident-affected and work-target units may differ
  within one Facility, and evidence preserves those distinct meanings
- composite foreign keys enforce common workspace and Facility for each reference
- column-level UPDATE grants and repository allowlists protect identity and
  relationship fields from creation; approved updates succeed and direct
  restricted-role changes to fixed fields fail
- application DELETE/TRUNCATE privileges are absent on operational tables;
  legacy broad grants are removed, and controlled migration-owner repair remains
  possible within relational constraints
- indexes support the documented query paths
- basic repository tests exist for each major entity
- mutable operational records carry workspace ownership; intentionally shared immutable reference data is documented
- foreign keys and uniqueness constraints include workspace scope where needed to prevent cross-workspace relationships and allow repeated baseline identifiers
- tests verify isolation across related entities and reject cross-workspace references
- migrations, application-role provisioning, and tests verify least-privilege
  grants and RLS policies for each workspace-owned table; shared reference data
  is read-only to the restricted application role

### Status

- [x] Complete — implementation verified and merged
- Design refinement: Q1–Q5, catalog/baseline/workspace boundaries, identity rules,
  catalog release identity, incident/target semantics, restricted-role permissions,
  and the implementation coverage plan are documented.
- CatalogRelease, EquipmentModel, Component, EquipmentUnit, InventoryItem, Incident,
  and WorkOrder persistence are implemented. Component/model compatibility is
  constrained to one catalog release; workspace-owned operational records are
  isolated by workspace and Facility. Incident and WorkOrder domain records, ORM
  mappings, repositories, and matching tests live in `app/operations/` and
  `tests/app/operations/`; catalog, units, and inventory remain in equipment.
- Acceptance coverage: `tests/app/operations/` covers reference semantics,
  lifecycle constraints, scoped uniqueness, repository reads/counts/pagination,
  missing records, isolation, and updates. Disposable provisioning tests exercise
  real restricted-role RLS, approved updates, denied fixed-field updates and
  deletion, owner repair, and removal of PUBLIC/default permission bypasses in
  both databases. Existing database/equipment/seed suites cover migration parity,
  catalog integrity, connection reuse, and repeatable smoke data.
- Verification (2026-09-20): 256 tests passed with no skips against PostgreSQL,
  including disposable-cluster permission regressions in both databases.
  `git diff --check` passed. One existing Starlette/AnyIO deprecation warning
  remains. Q1–Q5 seeded scenarios and query-plan validation remain deliberately
  deferred to their dataset/query waypoints; no new 1.4 acceptance gap is known.
- No Waypoint 1.5 capability is implemented by this acceptance pass.

---

## Waypoint 1.5 — Synthetic Structured Dataset

### Capability

A repeatable script populates the development database with a small, internally consistent fictional operational dataset.

### Minimum Dataset Target

Approximately:

- 5 facilities
- 10–20 equipment models
- 50+ equipment units
- 30+ component types
- inventory across multiple facilities
- 50+ incidents
- 50+ work orders

Exact volume is less important than consistency.

### Architectural Value

Creates controlled test and demo data.

Small endpoint-specific developer smoke fixtures may be introduced before this waypoint. This waypoint remains responsible for the complete, internally consistent, versioned dataset spanning the core operational schema.

### Completion Criteria

- seed process is repeatable
- all foreign keys are valid
- seeded operational UUIDs are deterministic per workspace and baseline entity;
  two copies reuse human codes but have disjoint operational IDs and correctly
  remapped foreign keys
- seed validation checks pass
- dataset can be recreated from scratch
- each frozen baseline manifest pins a `catalog_releases` row; workspaces
  retain baseline identity and a catalog-release foreign key, and their
  queries/references cannot mix catalog releases
- publication rejects changes to existing released catalog content; new releases
  do not change existing workspace results
- the canonical synthetic baseline has an explicit version and remains unchanged by reviewer edits
- Q1–Q5 baseline scenarios include fixed evaluation times, expected evidence IDs,
  and the positive, empty, unknown, boundary, and isolation cases in the model's
  verification plan
- the seed process can populate a specified workspace with internally consistent records and deterministic identifiers within that workspace
- seeding one workspace does not modify another; tests cover repeatability, isolation, and baseline-version tracking
- after one-time local PostgreSQL role provisioning, a documented project command
  applies migrations and creates or refreshes a specified development workspace
  from the canonical baseline
- the bootstrap documentation distinguishes privileged one-time role provisioning
  from repeatable migration and development-seeding commands, and includes
  successful endpoint smoke-test examples

### Status

- [x] Complete
- `data/baselines/demo-1.json` supplies 5 Facilities, 12 models, 36 Components,
  60 units, 179 stock rows, 60 Incidents, 60 WorkOrders, and 12 fixed Q1–Q5 cases.
- `scripts/bootstrap_development.py` applies migrations and seeds/validates a
  specified workspace; explicit refresh restores only that pinned copy. The old
  smoke seeder is retired. Its owner/configuration safeguards are retained by
  the shared seed-support module and the bootstrap tests; the example/local
  configuration selects the full dataset workspace.
- `0010_baseline_pins` records frozen manifests and workspace catalog pins.
  Publication rejects released-content rewrites; catalog checks reject mixed
  release references without granting workspace administration to the app role.
- See `docs/dataset.md` for commands, identity encoding, ownership, known limits,
  and the completion-criteria test mapping.
- Verification (2026-09-20): 279 tests passed, no skips; one existing
  Starlette/AnyIO deprecation warning. Coverage includes migration/model parity,
  an empty-schema bootstrap, independent workspace copies, frozen publication,
  release-pin enforcement under the application role, all 12 evidence scenarios,
  and existing Facility API compatibility. `git diff --check` passed.
- The documented development workspace `15000000-0000-4000-8000-000000000001`
  was created and validated. Restricted-role list/detail smoke requests returned
  200 with five Facilities. Q1–Q5 execution plans were inspected on this small
  dataset; this is not a production-scale performance benchmark.
- No active acceptance coverage gap is known. The dataset increment is committed;
  Waypoint 1.6 API acceptance is recorded below.

---

## Waypoint 1.6 — Core Operational Read API

### Capability

The core operational dataset is available through typed, read-only HTTP APIs
that support the later frontend and structured-query workflows.

### Completion Criteria

- list and detail endpoints expose the operational records required by the
  canonical questions
- endpoint scope follows the ownership model and cannot expose another
  workspace's mutable records
- pagination, relevant filters, stable response schemas, and standard problem
  responses are documented in OpenAPI; cross-cutting conventions and durable
  usage notes are maintained in `docs/api.md`
- automated tests cover successful responses, empty results, validation errors,
  unavailable database behavior, and cross-workspace isolation
- repeatable local smoke data and documented requests make every new endpoint's
  primary successful response manually verifiable
- no write endpoints are introduced; reviewer editing remains Waypoint 2.5 work

### Status

- [x] Complete
- Added workspace-scoped list/detail reads for equipment units, inventory items,
  incidents, and work orders, plus shared model/component lists and details and
  paginated exact-model compatibility. Catalog lists optionally filter by release,
  include unused definitions, and order by code then ID. Existing Facility behavior remains available.
- Reused bounded limit/offset pagination, typed response/query models, and
  problem responses. Filters are limited to the relationships, statuses,
  classification, priority, and incident time bounds needed by Q1–Q5.
- `docs/api.md` documents ownership, filtering, ordering, question semantics,
  and repeatable requests using the existing baseline. OpenAPI remains generated.
- Verification (2026-09-20): 362 tests passed, no failures or skips; one existing
  Starlette/AnyIO deprecation warning. Route acceptance tests use the restricted
  application role and independent seeded workspaces. Coverage includes exact
  data, pagination and filtered totals, empty results, validation, unavailable
  database responses, isolation, compatibility, release-filtered browsing across
  multiple releases, and generated documentation.
- The documented smoke requests returned 200 for every new endpoint against the
  configured development dataset through a running API using `space_corp_app`.
  `/docs`, `/redoc`, and `/openapi.json` also returned 200. API tests passed again
  after the full suite, confirming migration tests retain application grants.
- `git diff --check` passed. No active completion-criterion coverage gap is known;
  concurrent pagination snapshots and production-scale load testing are outside
  this increment. No migrations, dependencies, write endpoints, analytical answer
  endpoints, or Waypoint 1.7 automation were added.

---

## Waypoint 1.7 — Basic Pull Request Checks

### Capability

Pull requests automatically run the existing unit suite, applicable PostgreSQL
integration tests, and baseline static quality checks.

### Architectural Value

Protects the working backend before AI and public-demo capabilities are added.

### Completion Criteria

- checks run automatically on pull requests
- integration tests use an isolated test database with the required migrations
- failed required checks prevent merging
- local reproduction commands and required configuration are documented
- external model calls and provider credentials are not required for these checks
- formatting and lint checks run automatically
- static type checks run automatically for the typed backend interfaces
- migrations are exercised by the automated checks
- dependency installation is reproducible from documented project inputs

This is the explicitly scoped introduction of basic CI. Phase 11 expands the
pipeline with AI evaluation automation and deployment gates; those capabilities
are not required here.

### Status

- [x] Complete
- `.github/workflows/checks.yml` runs required Quality and Tests jobs on pull
  requests and pushes to `main`, using Python 3.14.6 and PostgreSQL 17 on Ubuntu.
- Hashed runtime, development, and build dependencies are recorded in
  `requirements-dev.lock`; clean Linux installation and local installation passed.
- Ruff formatting/lint and mypy across all 47 application/script modules pass.
  The initial lint baseline includes mechanical formatting/import cleanup and
  narrow type fixes, with no schema or application capability changes.
- The complete suite passed locally and in GitHub: 370 passed, zero failures or
  skips, one existing Starlette/AnyIO deprecation warning. Required test mode
  rejects missing integration prerequisites and skipped coverage. Fresh CI
  databases exercise migrations, restricted-role behavior, and provisioning.
- `main` protection requires Quality and Tests from GitHub Actions, up-to-date
  branches, and administrator enforcement. A deliberate unused-import probe
  failed Quality while Tests passed and GitHub reported BLOCKED; the probe was
  removed, both checks passed, and GitHub reported CLEAN. No merge was attempted.
- Acceptance: [PR #10](https://github.com/ryan-blauwaert/space-corp-agentic-ai/pull/10),
  [passing run](https://github.com/ryan-blauwaert/space-corp-agentic-ai/actions/runs/35549044523),
  [failed-gate verification](https://github.com/ryan-blauwaert/space-corp-agentic-ai/actions/runs/35548918274).
- [CI guide](ci.md) documents local reproduction, lock updates, permissions, and
  environment boundaries. No active acceptance gap remains; broader Python/OS
  matrices, static checks for tests/migrations, deployment, and AI checks are
  intentionally outside this initial CI increment.

---

# Phase 2 — Minimum Viable Product

## Objective

Deliver the first user-facing intelligent capability.

The MVP should allow a user to ask natural-language questions about structured operational data and receive a grounded answer.

Do not introduce multi-agent orchestration yet.

---

## Waypoint 2.1 — First LLM Integration

### Capability

The backend can make a controlled LLM request.

### Deliverables

- model-provider abstraction
- one configured model implementation
- typed request/response wrapper
- basic retry/error handling
- model call telemetry
- a minimal trace contract connecting request identifiers to operations, outcomes, latency, model/prompt versions, and token usage when available

### Architectural Value

Prevents application code from being tightly coupled to one model implementation.

### Possible Framework Use

LangChain model integrations or structured-output helpers may be used behind the
provider and request/response interfaces. Keep retries, telemetry, redaction, and
provider-independent contracts in the application layer.

### Completion Criteria

- test endpoint or internal service can successfully invoke a model
- provider implementation is behind an interface
- failures are handled predictably
- model and prompt identifiers are logged
- request and operation correlation is demonstrated for both successful and failed model calls
- telemetry avoids credentials and defines which request/evidence fields may be recorded

Phase 7 extends this foundation across capabilities and provides richer inspection. The initial implementation must be usable without Phase 7 infrastructure.

### Status

- [x] Complete — controlled model integration and live acceptance verified.
- Added validated model requests/results, caller-owned request/operation correlation,
  model/prompt identifiers, optional token usage, explicit output-limit completion,
  normalized error categories, and a one-attempt provider protocol under `app/llm/`.
- Fake-provider tests cover contract validation and success/failure correlation
  without SDKs, credentials, or network calls. See [integration notes](llm-integration.md).
- Contract verification: 412 tests passed, no failures or skips (42 contract/provider
  tests); Ruff and mypy passed. One existing Starlette/AnyIO warning remains.
- Added a configurable OpenAI Responses adapter, explicit output/timeout
  bounds, disabled SDK retries, safe error mapping, and mocked transport tests.
- Adapter verification: 454 tests passed, no failures or skips; Ruff, mypy,
  and locked dependency installation passed. The existing warning remains.
- Added a provider-independent execution service with bounded transient
  retries, jittered backoff, and allowlisted JSON attempt/operation telemetry.
  Tests cover correlation, timing, safe logs, and single-layer retry behavior.
- Execution-service verification: 481 tests passed, no failures or skips (27 new service
  tests); Ruff and mypy passed. The existing warning remains.
- Added an internal model smoke command with a fixed versioned prompt,
  explicit call bounds, safe result summaries, and console telemetry setup.
  Mocked HTTP tests verify the command through the provider and execution service.
- Smoke-command verification: 506 tests passed, no failures or skips (25 command tests);
  Ruff, mypy, and command help passed. The existing warning remains.
- Recorded user-supplied live successes with GPT-5 nano and GPT-5.6 Luna,
  plus the earlier bounded 429 failure. All traces preserve request/operation IDs,
  model/prompt identity, outcomes, timing, and safe metadata. See the live acceptance
  tables in [integration notes](llm-integration.md).
- Recognized billing/quota 429s now map to non-retryable `quota_exceeded`; temporary
  throttling remains `rate_limit`. Mocked adapter/service/command tests verify the
  distinction and immediate termination without logging provider messages.
- Final verification: 526 tests passed, no failures or skips; Ruff and mypy passed.
  One existing Starlette/AnyIO deprecation warning remains. No additional live calls
  or deliberately induced billing failures were needed. The original 429's exact
  cause remains unknown; answer quality is outside this waypoint's acceptance.

---

## Waypoint 2.2 — Structured Query Capability

### Capability

A natural-language question can be translated into a bounded domain query that
combines approved typed filters and relationships. Q1–Q5 are canonical acceptance
examples; supported combinations can answer additional questions without introducing
an operation per question. See [the query design](structured-queries.md) for the
current language and its limits.

### Example

> Which lunar facilities currently have fewer than two spare thermal control units?

### Recommended Flow

1. Receive the user question and trusted request context.
2. Produce a bounded domain proposal with approved filters and literal entity references.
3. Validate its shape, then resolve exact references within the authorized workspace and pinned catalog.
4. Validate the resolved plan and construct a parameterized query deterministically.
5. Require exact-plan caller confirmation for unanchored scope, then execute within a
   workspace-scoped read-only transaction and resource limits.
6. Return typed evidence with provenance.

### Safety Requirement

The model must not receive unrestricted database execution capability. Workspace,
catalog pins, authorization, pagination, and resource limits remain caller-owned.
Distinguish unsupported capability from prohibited behavior and missing/ambiguous
inputs; never silently answer a different question. Schema validity alone is not
authorization, semantic correctness, or read-only enforcement.

### Architectural Value

Introduces model-guided reasoning while retaining deterministic execution controls.

### Possible Framework Use

LangChain prompt and structured-output components may help produce a typed query
plan. Query validation, read-only enforcement, SQL execution, and unsafe-case
handling must remain deterministic application behavior.

### Completion Criteria

- Q1–Q5 are canonical acceptance examples, not an exhaustive intended-use list;
  bounded domain queries support their scenarios and documented combinations of
  approved filters without one operation per question
- deterministic tests verify expected plans/records and prohibited-behavior controls
  for every canonical and additional case; model interpretation is assessed separately
- a frozen development/holdout protocol measures repeated model outcomes against
  predeclared pilot targets, with all runs retained and no tuning on held-out results;
  see [query evaluation process](query-evaluation.md)
- unanchored model proposals require explicit exact-plan caller confirmation before
  evidence execution; evaluator-simulated review is distinguished from autonomous accuracy
- generated queries are validated before execution
- database access is read-only
- invalid queries fail safely
- query execution is traced
- automated tests cover canonical examples, new filter combinations, nested invalid
  inputs, unsafe cases, and filter/join/count boundaries
- every advertised filter is implemented and tested; evaluation checks intent and
  records so silent question substitution cannot pass as correct
- a small versioned evaluation dataset records questions, expected records, and prohibited behavior against the versioned synthetic baseline
- a repeatable evaluation command reports case-level results and aggregate outcomes, with dataset, model, and prompt versions recorded
- query operations share the request correlation introduced in Waypoint 2.1

Use deterministic checks for query results and prohibited operations. Phase 8 expands and consolidates this evaluation foundation instead of introducing evaluation for the first time.

### Status

- [x] Complete — bounded query execution and the guarded workflow passed the frozen Luna assessment (144/144 cases).
- Bounded facility-equipment, compatible-stock, work-order, incident, and inventory
  plans combine approved filters. Q1–Q5 remain examples, not an exhaustive use-case
  registry; authority and execution limits remain caller-owned.
- Read-only repeatable-read sessions enforce workspace scope and statement timeouts.
  All five executors validate references, catalog pins, relationships, counts, and
  evidence bounds. Migration 0011 exposes only the transaction workspace's catalog
  pin; the restricted role requires the corresponding provisioning grant.
- Versioned model planning, strict JSON validation, exact scoped entity resolution,
  and content-free correlated traces connect natural-language questions to evidence.
  No answer synthesis or natural-language HTTP endpoint is introduced.
- The repeatable evaluation command scores intent, evidence, and execution policy
  independently against `queries-3`: 12 canonical scenarios, six additional
  combinations, and six declined cases. The unchanged `demo-1` baseline is the
  oracle. Reports record model/prompt/dataset attribution and per-case outcomes.
- Latest automated verification: 1,021 tests passed, no failures or skips, in 53.61 seconds.
  Ruff, formatting, mypy, and whitespace checks passed. One existing Starlette/AnyIO
  deprecation warning remains. Supported evidence is tested in two workspaces.
- Local read-only preflight passes after restoring the existing catalog-pin EXECUTE
  grant. One approved live run with `gpt-5.6-luna`, `bounded-query` prompt version 1,
  and `queries-2` scored 17/24: six canonical, six additional, and five declined cases
  passed. `queries-3` subsequently clarified eight question texts while preserving
  all expected plans, evidence, and declines. A separately approved live run of
  `queries-3` scored 23/24: all 18 supported queries and five of six declines passed.
  The missing-facility question still executed instead of declining. Prompt version 2
  now explicitly prohibits dropping unresolved entity restrictions while preserving
  valid unrestricted queries. Its approved run scored 22/24: missing-facility passed,
  but completed-work was declined and ambiguous-unit received the wrong decline
  category. Both previously passed under prompt version 1; a single run cannot
  distinguish prompt effects from model variability.
- The final authorized iteration (prompt version 3, same `queries-3` fixture) scored
  23/24: all 12 canonical scenarios, five additional combinations, and all six declines
  passed. Completed-work was incorrectly declined as `ambiguous_input`. Safe report
  diagnostics now record operation, decline category, and mismatched field names.
  No further retries or tuning runs were made. This over-decline is documented as a
  system limitation with follow-up options in the query guide. These are development
  runs, not independent acceptance evidence.
- Replaced the single-perfect-run gate with `query-protocol-1`: three scheduled runs
  each of development and candidate wording-holdout datasets, configuration/dataset
  fingerprints, separate failure categories, and per-dataset pilot targets. No live
  calls were made for this process change, and no prior run was retroactively passed.
  The 95% supported-query and 90% decline-classification targets allow limited safe
  refusals but zero incorrect execution/evidence or call errors. These are provisional
  synthetic-pilot targets, not production reliability guarantees. The first frozen assessment completed all six runs: supported-query success was
  52/54 development versus 34/54 holdout; declines passed 18/18 in each set. Holdout
  failures comprised 11 unnecessary declines and nine reference-resolution errors.
  The protocol failed its declared targets. Review holdout entity-type ambiguity and
  resolution diagnostics before further changes; preserve this result. See the
  [assessment record](query-evaluation.md#first-frozen-assessment--2026-09-21).
  See [structured-query notes](structured-queries.md) for scope and verification limits.
- Prompt version 4 adds scoped UUID type grounding before planning and general
  capability/decline guidance. Scored fixtures and the historical protocol remain
  unchanged. Subsequent authorized iterative checks are recorded below; completion
  still requires a new frozen protocol and fresh reviewed holdout.
- Prompt version 6 clarifies returned evidence, exact fault identifiers, and existing
  numeric filters. Deterministic checks reject invented fault codes and silent
  selection among multiple grounded UUID candidates. Evaluation reports retain local
  plan diagnostics and recognize tested full-enum equivalence. Reasoning effort is
  configurable and attributed in reports; no saved model choice was changed.
- The ten-run holdout allowance is exhausted, with all runs preserved. The final paired
  check on GPT-5.2 with medium reasoning scored 23/24 development and 24/24 holdout.
  An unidentified facility was silently dropped, causing broader inventory execution.
  This violated the zero-unexpected-execution criterion and kept 2.2 open at that point.
  The scope-confirmation boundary below addresses execution of unanchored proposals. See the full iterative record in the evaluation guide.
- The explicit scope boundary is now implemented: unanchored plans return for review;
  only exact-plan caller confirmation can execute them. No new HTTP endpoint, UI,
  persisted workflow, or model repair loop is introduced. Frozen `query-protocol-2`
  and fresh `queries-holdout-2` were prepared for final assessment. The user selected
  Luna first, recorded separately as `query-protocol-2-luna`; the GPT-5.2 protocol
  remains unrun. Earlier failures remain preserved.
- The approved frozen Luna assessment passed all six scheduled runs: 72/72 development
  and 72/72 fresh wording holdout, with 54/54 supported and 18/18 declined cases per
  dataset. All 144 calls completed on the first attempt. Zero incorrect queries,
  evidence mismatches, unexpected executions, or call errors were observed. The
  assessor verified the fixed source, prompt, datasets, model, reasoning, and execution
  mode against the protocol. Thirty cases used simulated exact-plan caller confirmation.
  This closes 2.2 for the guarded synthetic-pilot workflow, not autonomous production
  reliability. See the [final assessment](query-evaluation.md#luna-final-assessment--2026-09-21).
  No later-waypoint work or additional live runs are authorized by this completion.

---

## Waypoint 2.3 — Structured Answer Synthesis

### Capability

Structured database results are converted into a useful natural-language answer.
The existing model plans the query; application code renders the returned evidence.
Free-form model prose is not an approved delivery path.

### User Value

A user can ask an operational question conversationally instead of using an API or SQL.

### Completion Criteria

- answer is based only on returned structured data
- delivered sentences are rendered by application code from validated evidence facts;
  model output cannot inject prose, replace values, or suppress mandatory scope/coverage
  disclosures; rendering supports domain/filter combinations rather than Q1–Q5 templates
- empty-result behavior is handled correctly
- answer record identifiers are deterministically checked against returned evidence; unsupported references are rejected before delivery
- evaluation measures unsupported factual claims, including plausible claims about valid records, against documented acceptance thresholds
- unsupported or insufficient evidence produces a defined cautious response
- request trace links user query, database query, results, and final answer
- the evaluation baseline from Waypoint 2.2 includes expected answer facts for both
  canonical examples and additional filter combinations, empty-result cases, and
  unsupported-claim cases; broader results must not inherit canonical-only claims

These checks provide measurable grounding guarantees; they do not claim that a generative model can never invent a fact. Publish known limitations alongside evaluation results.

### Possible Framework Use

No framework is required. Reuse the existing query planner and typed domain renderers;
no additional model call is needed for answer ordering or prose. Evidence values, sentence wording,
identifier checks, scope disclosures, and cautious responses remain application-owned.

### Status

- [~] In progress — typed evidence facts, deterministic sentence rendering, selection
  validation, cautious responses, development expectations, and traced query-to-answer
  orchestration exist.
- The renderer rebuilds facts from trusted query evidence and accepts only snapshot-bound
  fact IDs for presentation order. All returned records and mandatory disclosures remain.
  Free-form draft delivery is removed; model-provided values or prose cannot be rendered.
- Rules cover all five domains, null/zero stock, distinct work-order relationships,
  conditional recurrence, and empty/partial results. Unsupported selections and oversized
  answers are withheld. No extra queries, framework, or database changes were added.
- `answers-1` and the historical 2.2 fixtures/protocols remain unchanged. Rendering tests
  replace obsolete free-prose validation tests and cover additional filter combinations.
- `AnswerService` connects query execution directly to rendering, preserves exact-plan
  scope confirmation, and links planning/execution/results/answers through content-free
  tracing. The fact-ordering model call is dropped; only query planning calls the model.
- Answer evaluation now produces fixed/live reports with independently reviewed factual
  checks. The assessor rejects incomplete reviews, drift, duplicates, and incompatible
  batches. Fixed development and candidate holdout each pass 24/24 mechanical checks;
  the approved frozen live batch then scored 72/72 development and 71/72 holdout on
  mechanical checks. One valid empty work-order query was incorrectly declined as
  unsupported. All 144 calls completed in one attempt. This misses the current 100%
  cautious/empty-state target; semantic reviews are also pending. See the
  [assessment record](answer-evaluation.md#approved-live-batch-result).
  Do not equate mechanical checks with factual acceptance or replace the failed run.
- Deterministic rendering does not prove query correctness or eliminate renderer bugs.
- Verification before live answer assessment: 1,203 tests passed with no failures or
  skips, including required PostgreSQL integration and evaluator/review-gate coverage.
  Lint, formatting, and types passed; one existing Starlette/AnyIO warning remains.

---

## Waypoint 2.4 — Operational Query Interface

### Capability

A user can explore the synthetic operational context, submit a question, and understand a grounded answer through a professional web interface.

### Sequencing and Readiness

The frontend build begins only after the first backend vertical slice is complete: the Phase 1 operational API and dataset, plus the controlled model, structured-query, and answer-synthesis capabilities in Waypoints 2.1 through 2.3. Do not defer the first frontend until later RAG, action, workflow, or observability phases; those capabilities should extend an already working interface when they exist.

Before implementation, document the initial user journeys, route map, API error and empty-state behavior, and visual direction. This is a short readiness artifact for this waypoint, not a separate frontend implementation phase.

### Initial UI Scope

- application shell with an operations-oriented visual language and clear navigation
- read-only facility and operational-data context using the Phase 1 API
- question input and submission flow
- answer and supporting-record display
- loading, empty, validation, and failure states
- responsive and keyboard-accessible core flows

### User Value

Transforms the first intelligent backend capability into a credible, usable product demonstration.

### Architectural Value

Establishes a typed frontend/backend API boundary and validates that the backend's first complete vertical slice serves a real user workflow.

### Frontend Organization and Contract

Prefer a separate frontend application within the existing repository initially, with its own dependencies and build commands. Decide and document repository placement when frontend implementation begins; this roadmap does not require creating or moving a repository now.

If a separate frontend repository is selected:

- keep this product roadmap authoritative and link to it from the frontend repository
- link both repositories and the hosted demo from their READMEs, with reproducible paired startup instructions
- track compatible frontend/backend versions and coordinate API changes and releases

For either layout, use the backend OpenAPI schema as the API contract and generate client types from a known backend version. Document error handling, pagination, and contract regeneration. Add the session-access and reset contracts when Waypoint 2.5 introduces them. Repository separation does not require separate browser origins; evaluate a shared origin for the UI and API when deploying.

### Completion Criteria

- frontend launches locally with reproducible setup and build commands
- application shell exposes the initial operational-data and question-answer journeys
- read-only facility context is retrieved through the documented backend API
- question reaches the backend and the grounded answer with supporting records is displayed
- loading, empty, validation, and backend-failure states are shown clearly without exposing internal errors
- core flows are usable with keyboard navigation and at common desktop and narrow viewport sizes
- frontend client types match the documented backend contract, and the regeneration command is reproducible
- component tests cover the primary query flow and meaningful client-side states
- the paired frontend and backend pass an end-to-end question/answer and error-handling smoke test

### Status

- [ ] Complete

---

## Frontend Evolution After the MVP

The interface grows only when an underlying backend capability is complete:

- Waypoint 2.5 adds private reviewer sessions, selected-record editing, reset, expiration, and usage-limit communication.
- Phases 3 and 4 add document provenance, retrieval evidence, and clearly distinguished multi-source results.
- Phase 5 adds action-request status and explicit side-effect feedback; Phase 6 adds approval and durable-workflow state.
- Phases 7 and 8 may add a separately scoped internal operations surface for traces, evaluations, and system health when it provides concrete inspection value. It is not required for the public MVP interface.

This sequencing keeps the project backend-first while ensuring that each major backend capability is exercised through an appropriate user experience rather than accumulated as API-only infrastructure.

---

# MVP MILESTONE

The project reaches **Minimum Viable Product** when Waypoint 2.4 is complete.

The MVP must demonstrate:

1. professional operational query interface
2. working backend
3. persisted structured operational data
4. natural-language structured-data question
5. safe query generation/execution
6. grounded answer synthesis
7. automated tests
8. basic tracing/logging

At this point the project reaches a **technical MVP**: it is suitable for a
local or private demonstration of the complete read-only query journey.

The reviewer-ready portfolio release is completed at Waypoint 2.6, after private
workspaces, controlled editing, reset, resource limits, and hosted recovery have
been demonstrated. Those capabilities are part of the intended portfolio
experience, not optional replacements for the technical MVP.

---

## Waypoint 2.5 — Reviewer Demo Workspaces

### Capability

A reviewer can start a private browser session, explore and edit synthetic operational data, observe how changes affect answers, and reset to a stable baseline.

### Deliverables

- server-validated browser session access without requiring an account initially
- private workspaces populated from the versioned baseline
- a small data browser with validated editing of selected operational fields
- guided scenarios showing how data changes affect grounded answers
- reset that creates a fresh workspace and retires the previous one
- workspace expiration, cleanup, and bounded usage

### User Value

Reviewers can explore the system independently and repeat demonstrations without affecting other visitors or the canonical dataset.

### Architectural Value

Exercises workspace isolation through the UI, API, structured-query execution, conversations, and generated results. A workspace identifier alone does not authorize access; the server derives access from the validated session.

### Recommended Execution Units

1. private session creation and baseline workspace provisioning
2. selected-record browsing and validated editing
3. workspace reset, stale-request protection, expiration, and cleanup
4. cross-session resource limits and global model-spending controls

### Completion Criteria

- a reviewer can create a seeded private session through the browser
- selected records can be inspected and edited through validated deterministic endpoints
- changed records are reflected in subsequent query results and answers
- two concurrent reviewers cannot access or modify each other's data, conversations, or results
- reset restores the selected baseline version by switching to a fresh workspace
- retired workspaces reject subsequent writes and cannot affect replacement workspaces
- expired workspaces are cleaned up, and expiration and usage limits are communicated in the UI
- automated tests cover unauthorized access, cross-workspace isolation, editing validation, reset, stale requests, and expiration
- reset and session behavior are documented
- documented configuration bounds session lifetime, session creation rate, concurrent requests, database query duration and result size, model calls, and token consumption
- server-side limits apply across sessions as well as within a workspace; creating another session cannot bypass all resource controls
- a global model-spending ceiling includes admission checks for in-flight requests and a defined response when budget is unavailable
- tests exercise limits and concurrent requests using deterministic provider substitutes, with bounded rejection behavior and no paid calls required

Data editing here is ordinary application functionality. Agent-initiated write tools remain in Phase 5. Background jobs and durable workflows extend these guarantees when their own waypoints introduce them.

### Status

- [ ] Complete

---

## Waypoint 2.6 — Reviewer Demo Deployment and Recovery

### Capability

The paired frontend and backend are available through a hosted demo link and can be reproducibly deployed and recovered after a failed release.

### Deliverables

- documented hosting choice and deployment procedure for the frontend, backend, and PostgreSQL
- environment configuration, secret handling, and versioned baseline provisioning instructions
- a release record identifying backend, frontend, schema, and baseline versions
- hosted smoke checks and a recovery procedure

### Completion Criteria

- a reviewer can open the demo without local installation and complete a guided scenario
- hosted checks verify health, session creation, isolated edits, answer behavior, reset, expiration, and usage limits
- clean-environment provisioning is reproducible from the documented release inputs
- a recovery rehearsal verifies the documented response to a failed release, including schema compatibility and restoration or explicit reseeding of disposable demo workspaces
- recovery documentation states any session/data loss and distinguishes disposable workspace state from retained operational records
- existing PR checks pass before release, and local commands reproduce the hosted smoke checks

Select hosting when implementing this waypoint. A documented manual deployment is sufficient initially; advanced deployment automation remains in Phase 11. Database recovery must not assume that reverting application code also reverses schema changes.

### Status

- [ ] Complete

---

# Phase 3 — Unstructured Knowledge and RAG

## Objective

Allow questions to incorporate technical documents and operational knowledge.

LangChain is a possible adapter layer for document loaders, text splitters,
embeddings, retrievers, and prompt composition in this phase. Preserve the
project's own metadata, provenance, workspace boundaries, and retrieval interfaces
so the system can be evaluated or replaced independently of the framework.

---

## Waypoint 3.1 — Document Storage and Metadata

### Capability

Technical documents can be registered and stored with metadata.

### Document Types

Examples:

- equipment manuals
- maintenance procedures
- technical bulletins
- operational policies
- incident reports

### Completion Criteria

- document metadata schema exists
- documents can be ingested
- source identity and version are preserved
- document lookup works without vector search
- shared immutable documents and workspace-owned documents are explicitly distinguished, with access and provenance tests

### Status

- [ ] Complete

---

## Waypoint 3.2 — Chunking Pipeline

### Capability

Documents are transformed into retrieval-ready chunks.

### Requirements

Chunks preserve:

- document ID
- source
- section
- page where applicable
- document version
- chunk position

### Architectural Value

Creates independent ingestion and retrieval preparation boundaries.

### Completion Criteria

- chunking is deterministic
- metadata is preserved
- unit tests cover normal and malformed documents
- chunk inspection tooling exists

### Status

- [ ] Complete

---

## Waypoint 3.3 — Embeddings and Vector Retrieval

### Capability

Semantic search retrieves relevant document chunks.

### Completion Criteria

- chunks are embedded
- vector similarity search works
- retrieval results include provenance
- at least ten manually verified queries retrieve expected documents
- workspace-owned chunks and vector results remain isolated; retired-workspace results cannot appear in a replacement workspace

### Status

- [ ] Complete

---

## Waypoint 3.4 — Hybrid Retrieval

### Capability

Retrieval combines lexical and dense search.

### Possible Components

- dense vector retrieval
- BM25 or equivalent lexical retrieval
- rank fusion

### Architectural Value

Provides a stronger retrieval foundation before agent orchestration.

### Completion Criteria

- both retrieval modes work independently
- combined retrieval works
- retrieval results expose scores
- retrieval evaluation can compare strategies

### Status

- [ ] Complete

---

## Waypoint 3.5 — RAG Answering

### Capability

Users can ask questions answered from unstructured documents.

### Requirements

Responses should include evidence provenance.

### Completion Criteria

- retrieved context is passed to synthesis
- answers include source references
- unsupported questions return appropriately cautious responses
- initial RAG gold set exists
- basic groundedness evaluation exists
- retrieval context, generated artifacts, and any caches respect workspace ownership and reset boundaries

### Status

- [ ] Complete

---

# Phase 4 — Multi-Source Reasoning

## Objective

Support questions requiring both relational data and document retrieval.

LangChain runnable composition or retriever interfaces may help connect the
structured and unstructured paths. The capability router, typed evidence model,
concurrency policy, and failure representation should remain explicit application
contracts.

---

## Waypoint 4.1 — Capability Router

### Capability

The system determines whether a request requires:

- structured data
- document retrieval
- both
- unsupported capability

### Architectural Value

Introduces orchestration without requiring multiple autonomous agents.

### Completion Criteria

- router emits typed output
- test set measures routing correctness
- invalid or low-confidence cases are handled explicitly
- routing behavior is traced

### Status

- [ ] Complete

---

## Waypoint 4.2 — Multi-Source Execution

### Capability

A single request can invoke both structured and unstructured retrieval.

### Example

> Has this equipment fault happened before, what does the manual recommend, and do we have the replacement component available?

### Completion Criteria

- structured and document retrieval can execute within one request
- evidence from each source remains distinguishable
- independent operations execute concurrently where safe
- failures in one source are represented explicitly

### Status

- [ ] Complete

---

## Waypoint 4.3 — Evidence-Aware Synthesis

### Capability

The final response synthesizes evidence from multiple sources.

### Requirements

The synthesis layer should not independently call external tools.

### Completion Criteria

- structured facts remain attributable to database results
- document claims remain attributable to sources
- conflicting evidence is surfaced rather than silently resolved
- tests cover incomplete and conflicting evidence

### Status

- [ ] Complete

---

# Phase 5 — Tool Use and Governed Actions

## Objective

Move from answering questions to safely changing system state.

LangChain tool schemas or tool-calling adapters may be used at the model boundary.
Authorization, validation, auditability, idempotency, and side-effect policy must
remain outside the model and outside opaque framework behavior.

---

## Waypoint 5.1 — Tool Contract Framework

### Capability

Application actions use explicit typed tool contracts.

### Requirements

Each tool defines:

- name
- input schema
- output schema
- errors
- authorization requirement
- side-effect classification

### Completion Criteria

- tool registry exists
- at least one read-only tool is implemented
- tool invocation is traced
- invalid arguments fail safely

### Status

- [ ] Complete

---

## Waypoint 5.2 — First Write Tool

### Capability

The platform can create a maintenance work order.

### User Value

First true agentic action.

### Safety Requirements

- authorization outside the model
- input validation
- audit record
- idempotency

### Completion Criteria

- work order can be created through a tool call
- repeated idempotent request does not create duplicate records
- unauthorized execution fails
- audit trail exists
- automated tests cover success and failure
- tool authorization, audit records, and idempotency keys are workspace-scoped
- retired-workspace actions are rejected; demo external effects are simulated and confined to the demo

### Status

- [ ] Complete

---

## Waypoint 5.3 — Action-Aware Routing

### Capability

The system distinguishes informational requests from action requests.

### Completion Criteria

- an informational request such as “what is wrong?” may use read-only tools but cannot invoke write or side-effecting tools without an authorized action request
- request such as “create a maintenance ticket” selects the action capability
- ambiguous action requests do not execute automatically
- routing is evaluated against a gold set

### Status

- [ ] Complete

---

# Phase 6 — Durable Human-in-the-Loop Workflows

## Objective

Demonstrate long-running agent workflows capable of pausing and resuming safely.

LangGraph is a possible implementation candidate for stateful, interruptible
orchestration once the workflow contracts are understood. It must complement—not
replace—the project's persisted workflow state, restart/recovery semantics,
workspace checks, and explicit side-effect controls.

---

## Waypoint 6.1 — Durable Workflow State

### Capability

A workflow instance can persist execution state.

### State Includes

- workflow ID
- current step
- completed steps
- pending steps
- relevant evidence
- tool results
- status
- timestamps
- model/prompt version where applicable

### Completion Criteria

- workflow state survives application restart
- workflow can be loaded by ID
- workflow transitions are validated
- state transitions are tested
- workflow instances and related evidence belong to a workspace; reset retires their execution context

### Status

- [ ] Complete

---

## Waypoint 6.2 — Human Approval Task

### Capability

A workflow can transition into `WAITING_FOR_APPROVAL`.

### User Value

Sensitive actions can be safely gated.

### Completion Criteria

- approval task is persisted
- prohibited action does not execute before approval
- authorized user can approve or reject
- approval event is audited
- approval access and decisions are workspace-scoped, and approvals from retired workspaces cannot authorize actions

### Status

- [ ] Complete

---

## Waypoint 6.3 — Workflow Resume

### Capability

A persisted workflow resumes from the correct step after human approval.

### Critical Demonstration

1. start workflow
2. reach approval
3. stop application
4. restart application
5. approve request
6. reload state
7. continue execution
8. complete without duplicate side effects

### Architectural Value

Demonstrates real durable orchestration rather than an in-memory confirmation loop.

### Completion Criteria

- above restart scenario passes automatically
- previously completed tools are not repeated unnecessarily
- write operations remain idempotent
- trace links pre-pause and post-resume execution
- jobs and resumed workflows revalidate workspace activity before side effects; reset cannot redirect old work into a replacement workspace
- tests cover reset while a workflow is paused or running, including concurrent reset and write attempts
- external actions with lost acknowledgments have an explicit unknown-outcome state and a documented idempotency or reconciliation strategy
- tests simulate a successful external effect followed by a lost response and application restart; recovery reconciles the outcome or safely reuses the external idempotency key
- where the external system cannot support safe retry or reconciliation, recovery pauses for human resolution rather than blindly repeating the effect

Database transactions alone do not guarantee exactly-once external effects. Demonstrate these cases using simulated external services within the reviewer demo.

### Status

- [ ] Complete

---

# Phase 7 — Observability and AI Control Plane

## Objective

Make internal AI behavior inspectable.

---

## Waypoint 7.1 — Standardized Tracing

### Capability

Extend the request and operation correlation introduced in Waypoints 2.1–2.3 as new capabilities are added. Earlier tracing requirements do not depend on this later waypoint.

Requests generate correlated traces across:

- API
- model calls
- retrieval
- database operations
- tools
- workflows

### Completion Criteria

- every user request has a trace ID
- nested operations create spans
- latency and errors are recorded
- token/model metadata is captured where possible

### Status

- [ ] Complete

---

## Waypoint 7.2 — Trace Viewer

### Capability

Admin users can inspect a request execution.

### Minimum UI

Show:

- request
- router decision
- model calls
- retrieval
- database queries
- tool calls
- workflow transitions
- errors
- latency

### Completion Criteria

- trace can be retrieved by ID
- execution ordering is visible
- failures are clearly represented

### Status

- [ ] Complete

---

## Waypoint 7.3 — Pending Workflow Dashboard

### Capability

Admin UI displays:

- waiting workflows
- pending approvals
- current status
- reason for pause
- workflow age

### User Value

Human operators can manage asynchronous AI work.

### Completion Criteria

- pending workflow list works
- approval/rejection is supported
- workflow history can be inspected

### Status

- [ ] Complete

---

# Phase 8 — Evaluation System

## Objective

Measure system behavior at multiple layers.

LangSmith or other framework-specific tracing and evaluation integrations may be
considered as supplemental inspection tools if they preserve the project's
versioned datasets, deterministic evaluators, privacy rules, and reproducible
reports. They are not substitutes for the application's evaluation contracts.

---

## Waypoint 8.1 — Evaluation Dataset Schema

### Capability

Evaluation cases are stored using a standardized schema.

Consolidate and extend the versioned cases and execution reports introduced in Waypoints 2.2–2.3, retaining their baseline, model, and prompt attribution.

### Possible Fields

- input
- category
- expected route
- expected tools
- expected arguments
- required evidence
- expected facts
- reference answer
- approval required
- prohibited actions
- expected final state

### Completion Criteria

- schema exists
- at least 25 evaluation cases are stored
- cases cover structured, RAG, multi-source, and action workflows

### Status

- [ ] Complete

---

## Waypoint 8.2 — Deterministic Evaluators

### Capability

System behavior is measured mechanically where possible.

Expand the initial repeatable evaluation command into a shared runner for the capabilities now implemented.

### Metrics

Examples:

- route accuracy
- tool selection accuracy
- tool argument accuracy
- SQL result correctness
- retrieval recall@K
- approval correctness
- workflow final-state correctness

### Completion Criteria

- evaluation runner exists
- results are persisted
- aggregate metrics are produced
- failing cases can be inspected

### Status

- [ ] Complete

---

## Waypoint 8.3 — LLM-as-Judge

### Capability

Semantic response characteristics are evaluated using model judges.

### Possible Criteria

- correctness
- completeness
- groundedness
- citation quality

### Completion Criteria

- judge prompt/version is tracked
- judge outputs are structured
- judge is tested against a small human-labeled calibration set
- deterministic evaluators remain preferred when applicable

### Status

- [ ] Complete

---

## Waypoint 8.4 — Evaluation Dashboard

### Capability

Admin UI displays evaluation runs and regressions.

### Completion Criteria

- runs can be compared
- failures can be filtered
- model/prompt/config versions are visible
- key metrics are charted

### Status

- [ ] Complete

---

# Phase 9 — Context and Memory Management

## Objective

Make model context deliberate, inspectable, and efficient.

LangChain message, context, or middleware utilities may be useful for selected
assembly tasks. The context builder remains the authoritative component for token
budgets, provenance, persistence boundaries, and what information is allowed into
model context.

---

## Waypoint 9.1 — Context Builder

### Capability

Model context is assembled through an explicit component.

### Inputs May Include

- current request
- selected conversation history
- retrieved evidence
- tool results
- workflow state summary

### Completion Criteria

- context composition is deterministic outside semantic selection
- token counts are measured
- context components retain provenance

### Status

- [ ] Complete

---

## Waypoint 9.2 — Context Compaction

### Capability

Older or oversized information can be summarized or omitted.

### Completion Criteria

- configurable token budget exists
- tool outputs can be compacted
- old conversation history can be summarized
- tests verify required information is preserved

### Status

- [ ] Complete

---

# Phase 10 — MCP and Service Extraction

## Objective

Demonstrate interoperability and justified distributed boundaries.

---

## Waypoint 10.1 — First MCP Server

### Capability

One existing tool domain is exposed through MCP.

### Recommended Candidate

Operations/work-order tools.

### Completion Criteria

- MCP server exposes typed tools
- existing application can consume it
- authorization behavior remains intact
- contract tests exist

### Status

- [ ] Complete

---

## Waypoint 10.2 — Extract Asynchronous Service

### Capability

One workload with a legitimate independent lifecycle becomes a separate service.

### Recommended Candidate

Document ingestion or evaluation execution.

### Architectural Value

Demonstrates intentional microservice extraction.

### Completion Criteria

- service has explicit contract
- independent tests exist
- failure does not corrupt primary application state
- service can be deployed independently
- distributed tracing crosses the boundary

### Status

- [ ] Complete

---

# Phase 11 — CI/CD and Regression Gates

## Objective

Prevent AI behavior regressions from reaching deployment.

---

## Waypoint 11.1 — Automated Test Pipeline

### Capability

Expand the basic PR checks introduced in Waypoint 1.7. This phase does not defer the earlier requirement for automated regression protection.

Every pull request runs:

- unit tests
- integration tests
- linting
- type checking

### Completion Criteria

- pipeline executes automatically
- failure prevents merge

### Status

- [ ] Complete

---

## Waypoint 11.2 — AI Evaluation Pipeline

### Capability

Relevant application changes trigger offline AI evaluations.

### Completion Criteria

- evaluation dataset runs automatically
- candidate configuration is compared against baseline
- results are attached to build output

### Status

- [ ] Complete

---

## Waypoint 11.3 — Deployment Quality Gates

### Capability

Deployment is blocked when defined quality or safety thresholds regress.

### Example Gates

- no critical safety failures
- no approval-policy regressions
- minimum route accuracy
- minimum retrieval recall
- maximum acceptable quality regression
- latency/cost budget

### Completion Criteria

- thresholds are version controlled
- failing threshold prevents deployment
- override requires explicit human action

### Status

- [ ] Complete

---

# Phase 12 — Robustness and Production-Style Enhancements

## Objective

Test behavior beyond the happy path.

These capabilities occur only after the core system works.

---

## Waypoint 12.1 — Adversarial Evaluation

Test:

- prompt injection
- malicious retrieved documents
- authorization escalation
- ambiguous requests
- conflicting evidence
- malformed tool outputs
- unsafe action requests

### Completion Criteria

- adversarial dataset exists
- critical safety scenarios pass
- failures become permanent regression cases

### Status

- [ ] Complete

---

## Waypoint 12.2 — Failure Recovery

Test:

- model timeout
- database outage
- retrieval failure
- tool timeout
- worker restart
- duplicate events
- partial workflow execution

### Completion Criteria

- failure states are explicit
- retry policies are documented
- duplicate side effects are prevented
- recovery scenarios are automated

### Status

- [ ] Complete

---

## Waypoint 12.3 — Cost and Performance Optimization

### Capability

System tracks and optimizes:

- latency
- token use
- model cost
- retrieval cost
- tool latency

### Potential Enhancements

- model routing
- caching
- retrieval optimization
- parallel execution
- context reduction

### Completion Criteria

- baseline performance metrics exist
- optimization produces measurable improvement without unacceptable quality regression

### Status

- [ ] Complete

---

# Phase 13 — Advanced Portfolio Enhancements

These capabilities are optional and should not delay the core system.

Potential additions include:

- second model provider
- adversarial independent model reviewer
- multi-agent specialist architecture
- agent-to-agent delegation
- richer long-term memory
- canary deployment
- production feedback ingestion
- automatic promotion of failed traces into evaluation cases
- synthetic scenario generation
- advanced reranking experiments
- prompt/model experiment management
- feature flags
- service autoscaling
- richer frontend visualization

These should be implemented only when they add a concrete demonstration of engineering skill.

---

# Recommended Release Milestones

## MVP — Structured AI Operations Assistant

Requires completion through:

**Waypoint 2.4**

Demonstrates:

- full-stack application
- relational database
- synthetic operational domain
- LLM integration
- safe structured querying
- natural-language answer synthesis
- automated testing

---

## Reviewer-Ready Demo

Requires:

- completion through **Waypoint 2.6**, including the reviewer workspaces in Waypoint 2.5
- a hosted deployment reachable through a public demo link, with no local installation required
- validation of session isolation, reset, expiration, and usage limits in the hosted environment
- documented deployment configuration and baseline version

Adds private, editable reviewer sessions with guided scenarios and a repeatable reset experience.

The technical MVP remains Waypoint 2.4. Waypoint 2.6 delivers the reviewer-ready
hosted release and recovery capabilities, using the basic PR checks from
Waypoint 1.7. Advanced CI/CD capabilities in Phase 11 are not a prerequisite.

---

## MVP+ — Hybrid Knowledge Assistant

Requires completion through:

**Waypoint 4.3**

Adds:

- document ingestion
- vector retrieval
- RAG
- hybrid retrieval
- multi-source reasoning
- routing
- evidence-aware synthesis

---

## Agentic Release

Requires completion through:

**Waypoint 6.3**

Adds:

- typed tools
- write actions
- authorization
- idempotency
- durable workflows
- human approval
- pause/restart/resume behavior

---

## Engineering Release

Requires completion through:

**Waypoint 8.4**

Adds:

- end-to-end tracing
- admin control plane
- structured evaluation
- LLM-as-judge
- regression visibility

---

## Production-Style Release

Requires completion through:

**Waypoint 12.3**

Adds:

- MCP interoperability
- justified service extraction
- CI/CD evaluation gates
- adversarial testing
- failure recovery
- cost and performance optimization

---

# Current Project Position

Current phase:

**Phase 2 — Minimum Viable Product**

Current waypoint:

**Waypoint 2.3 — Structured Answer Synthesis (in progress)**

Bounded contracts, all five read-only executors, scoped model planning, tracing,
explicit scope confirmation, and repeatable evaluations are implemented. The frozen
Luna assessment passed 144/144 cases across six runs; earlier failures remain in the
assessment history. The verified workflow requires caller review for unanchored plans,
simulated in evaluation. Q1–Q5 remain examples alongside additional supported filters.
Waypoint 2.2 was committed as `eb2fc19`. Waypoint 2.3 now renders sentences from evidence
facts, with snapshot-bound selection
validation and cautious responses. The internal service connects queries to rendered
answers with tracing and scope confirmation. Model-prose delivery and the planned
fact-ordering call are removed. Evaluation tooling is implemented; live assessment and
completed human factual reviews remain pending. The approved live batch had one safe
unnecessary decline (143/144 mechanical passes), so 2.3 is not complete.
Real-user coverage and confirmation usability remain future validation work.

---

# Status Tracking Convention

Each waypoint should be assigned one of:

- `[ ] Not Started`
- `[~] In Progress`
- `[x] Complete`
- `[!] Blocked`
- `[-] Deferred`

When a waypoint moves to complete, record:

- completion date
- relevant commit or pull request
- major architectural decision if any
- known follow-up work

Example:

```text
[x] Waypoint 1.2 — First Domain Entity
Completed: YYYY-MM-DD
PR: #12
Notes:
- Facility repository interface introduced.
- No generic repository abstraction added.
```

---

# Rules for Coding Agents

When working from this roadmap, coding agents should:

1. identify the active waypoint before making changes
2. avoid implementing capabilities from future waypoints unless explicitly instructed
3. prefer the smallest change that satisfies the current completion criteria
4. report any discovered dependency that is not represented in an earlier waypoint
5. add or update automated tests required by the waypoint
6. avoid marking a waypoint complete unless all measurable criteria pass
7. update documentation only when implementation changes make it inaccurate
8. avoid speculative infrastructure intended only for future phases
9. preserve backward compatibility with already-completed capabilities where practical
10. leave the repository in a runnable and testable state
11. when adding an endpoint backed by persisted data, provide enough repeatable local smoke data and documentation to exercise its primary successful response outside the automated test suite

---

# Definition of Done for Any Waypoint

Unless a waypoint explicitly states otherwise, completion requires:

- implementation exists
- implementation is understandable and reviewable
- relevant automated tests pass
- failure behavior is considered
- documentation is updated where necessary
- no unrelated future capabilities were introduced
- code is committed
- completion criteria can be demonstrated
- new persisted-data endpoints can be exercised manually against documented, repeatable local smoke data
- the next waypoint can begin without unfinished hidden dependencies
