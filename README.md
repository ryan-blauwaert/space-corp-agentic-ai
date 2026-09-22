# Agentic AI Operations Platform

A portfolio-grade project for designing and building a production-style agentic AI system with structured and unstructured data access, governed tool use, durable workflows, human-in-the-loop controls, evaluation, observability, and service-oriented architecture.

The application domain is a fictional near-future space operations company. The synthetic domain provides a controlled environment for demonstrating complex AI workflows without depending on proprietary or sensitive data.

## Project Goals

The platform is intended to demonstrate capabilities across:

- agent orchestration and intent routing
- structured data reasoning
- retrieval-augmented generation
- embeddings, chunking, retrieval, and reranking
- typed tool use
- governed write actions
- human approval workflows
- durable workflow state and resumption
- context management
- MCP integration
- observability and tracing
- deterministic and LLM-based evaluation
- synthetic data generation
- CI/CD quality gates
- modular and service-oriented architecture

The project will be built incrementally through small, reviewable changes rather than introducing the entire AI stack at once.

## Example Future Workflow

A mission operator may eventually ask:

> Environmental Control Unit ECS-14 is reporting a fault. What does it mean, has it happened before, do we have compatible replacement parts available, and what should we do next?

Answering that request may require the system to combine:

- structured equipment data
- historical incidents
- inventory records
- technical manuals
- maintenance procedures
- operational policies

The user may then request an action such as taking the system offline or creating an emergency maintenance request.

Sensitive operations should be protected by deterministic authorization and policy controls. A workflow may pause while waiting for a human approval, persist its state, and later resume safely after the required approval is provided.

## Architectural Direction

The project will favor clear service and domain boundaries without introducing unnecessary distributed-system complexity.

Capabilities should be independently testable and communicate through explicit interfaces.

Selected components may later become independently deployable services where justified by:

- scaling requirements
- fault isolation
- security boundaries
- deployment lifecycle
- asynchronous workloads
- external integration boundaries

The project should avoid both a tightly coupled macroservice and unnecessary microservice proliferation.

## Initial Technology Direction

The project will begin with:

- Python
- FastAPI
- pytest

Additional infrastructure will be introduced incrementally as requirements emerge, potentially including:

- PostgreSQL
- vector storage
- LLM providers
- workflow persistence
- queues or eventing
- MCP
- OpenTelemetry
- evaluation tooling
- containers
- CI/CD

No particular agent framework, workflow framework, vector database, or deployment platform is assumed at the start. LangChain and LangGraph may be evaluated later as implementation adapters for model, retrieval, tool, or durable-workflow capabilities; they are optional and do not define the application's contracts.

## Current Status

**Phase 2 — Minimum Viable Product; Waypoint 2.4 in progress**

The operational backend, versioned dataset, read-only API, PR checks, and controlled
[LLM integration](docs/llm-integration.md) are implemented. Bounded queries support
facility equipment, compatible stock, work orders, incidents, and inventory through
model planning, scoped entity resolution, read-only execution, and correlated tracing.
Q1–Q5 are examples; approved filters can express additional legitimate questions.

The [frozen assessment](docs/query-evaluation.md#luna-final-assessment--2026-09-21)
passed all 144 cases using `gpt-5.6-luna` with medium reasoning. Unanchored plans
require explicit caller confirmation before execution; the evaluator simulates this
review. These synthetic pilot results do not guarantee model interpretation on unseen
requests. See the [query guide](docs/structured-queries.md) for capabilities and limits.

Waypoints 2.2 and 2.3 are complete. [Answer synthesis](docs/answer-synthesis.md) renders
validated evidence with cautious responses, record references, correlated tracing and
scope confirmation. Only query planning calls the model. Both current fixed-evidence
answer datasets pass 24/24; offline replay verifies the disclosure correction against
all 144 saved live outcomes. One original unnecessary refusal remains within the
query-aligned pilot allowance. See [answer evaluation](docs/answer-evaluation.md) for
factual assessment, historical results and limitations. Full verification passed 1,210
tests with no failures or skips at 2.3 closeout. Waypoint 2.4 now exposes the
[question and scope-confirmation API](docs/api.md#operational-questions-waypoint-24).
Frontend implementation and browser acceptance remain pending.

The [dataset guide](docs/dataset.md) covers bootstrap and refresh,
[API documentation](docs/api.md) covers existing endpoints, and the
[CI guide](docs/ci.md) covers local checks. The [roadmap](docs/roadmap.md) records
acceptance status and sequencing.

## Planned Capability Areas

### Structured Data

Natural-language requests over relational operational data using combinations of approved typed filters, with application-controlled validation and execution. Canonical questions illustrate supported behavior without exhausting it.

### Retrieval-Augmented Generation

Document ingestion, metadata extraction, chunking, embeddings, hybrid retrieval, reranking, context construction, and source-aware generation.

### Agent Orchestration

Intent classification, task decomposition, capability selection, dependency-aware execution, and multi-source synthesis.

### Tool Use

Typed tools for read and write operations with validation, authorization, error handling, and idempotency.

### Human-in-the-Loop Workflows

Workflows capable of pausing for human approval or input, persisting state, surviving application restarts, and resuming from the correct execution point.

### Evaluation

Gold datasets and automated evaluation covering retrieval, structured queries, routing, tool calls, workflows, policy compliance, and final responses.

### Observability

End-to-end tracing of model activity, retrieval, tools, workflow transitions, service calls, cost, latency, errors, and evaluation results.

### Administration

A lightweight control plane for inspecting traces, evaluations, workflow state, pending approvals, experiments, and system behavior.

## Development Philosophy

This repository follows a few core principles:

- Prefer small, reviewable changes.
- Favor explicit interfaces over hidden framework behavior.
- Use deterministic software where deterministic software is sufficient.
- Use language models where reasoning or semantic interpretation adds clear value.
- Treat safety, evaluation, and observability as first-class system capabilities.
- Design service boundaries before distributing everything across networked services.
- Do not introduce infrastructure solely for architectural appearance.
- Preserve the ability to understand and explain every major system decision.

## Repository Guidance

Coding agents should follow the instructions in `AGENTS.md`.

More detailed project requirements and long-term goals are documented in `PROJECT_BRIEF.md`.

See the [database architecture](docs/database-architecture.md) and [roadmap](docs/roadmap.md) for current decisions and sequencing.

## Local Development

The backend declares Python 3.12 or later; use Python 3.14.6 to reproduce the
verified local and CI environment.

Create a virtual environment and install the application with development dependencies:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
```

Start the local API:

```bash
uvicorn app.main:app --reload
```

Verify the health endpoint in another terminal:

```bash
curl http://127.0.0.1:8000/health
```

The endpoint returns `200 OK` with `{"status":"ok"}`.

Run the test suite:

```bash
pytest
```

For the complete PostgreSQL-backed suite, copy `.env.test.example` to the ignored `.env.test` file once. The test configuration is loaded automatically, so later `pytest` runs require no terminal exports.

### Application Configuration

Settings are loaded from environment variables and an ignored project-root `.env` file when the application starts. Copy the tracked template before starting the API:

```bash
cp .env.example .env
```

The application refuses to start until its database URL and default workspace ID are configured, and it checks database reachability during startup. This prevents a server that cannot serve operational API requests from accepting traffic.

| Environment variable | Default | Accepted values and purpose |
| --- | --- | --- |
| `SPACE_CORP_ENVIRONMENT` | `development` | `development`, `test`, or `production`; identifies the application environment. |
| `SPACE_CORP_APPLICATION_NAME` | `Agentic AI Operations Platform` | A string used as the FastAPI title, visible in the API documentation and OpenAPI schema. |
| `SPACE_CORP_LOGGING_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; validated and stored, but not yet applied to logger configuration. |
| `SPACE_CORP_DATABASE_URL` | Unset (`None`) | A validated PostgreSQL URL used by application database resources. It should use the restricted application role and is required at startup. |
| `SPACE_CORP_MIGRATION_DATABASE_URL` | Unset (`None`) | A validated PostgreSQL URL used only by Alembic schema migrations. It should use the schema-owner migration role. |
| `SPACE_CORP_DEFAULT_WORKSPACE_ID` | Unset (`None`) | UUID of an existing workspace, selected by the server for local operational API requests. Required at startup. This is not public multi-user authorization. |

For example, start the API with a different application name:

```bash
SPACE_CORP_APPLICATION_NAME="Test Operations API" uvicorn app.main:app --reload
```

Open [the local API documentation](http://127.0.0.1:8000/docs) to see `Test Operations API` as the title. Stop any existing server using port 8000 before running this example. The override applies only to this command; restart the server after changing its environment variables.

Unsupported environment or logging-level values cause configuration validation to fail at startup. Values must match the accepted spelling and capitalization shown above.

The `.env` file is ignored and must never contain committed credentials. The included URLs omit passwords: keep local PostgreSQL passwords in the ignored `~/.pgpass` file or another local credential store. Explicit process environment variables override `.env` values, which keeps deployment configuration separate from repository files.

### PostgreSQL Development

PostgreSQL is required for the Phase 1 persistence, migration, and integration checks. Follow the [local PostgreSQL setup guide](docs/local-postgresql.md) to choose a native macOS or Docker-based instance, create separate development and test databases, and configure credentials safely.

Configure the migration-owner URL before applying migrations:

```bash
.venv/bin/python -m scripts.bootstrap_development --validate
```

After one-time role provisioning, this command applies migrations and uses the
configured migration-owner connection to create or validate the complete versioned
dataset. Ordinary reruns preserve workspace edits; `--refresh` explicitly restores
the selected workspace. See [the dataset guide](docs/dataset.md) for setup and
switching an existing installation to the canonical dataset.

Copy the test configuration template once before running real PostgreSQL checks:

```bash
cp .env.test.example .env.test
pytest
```

## Project Status

This project is under active development and is intentionally being built from the foundation upward.

## API Documentation

Start the API locally, then use the generated documentation:

- [Swagger UI](http://127.0.0.1:8000/docs)
- [ReDoc](http://127.0.0.1:8000/redoc)
- [OpenAPI schema](http://127.0.0.1:8000/openapi.json)

See [API documentation](docs/api.md) for cross-cutting conventions, current
usage notes, smoke-test setup, and API compatibility guidance.

## Domain Module Boundaries

`app/equipment/` owns catalog releases, equipment models, components, deployed
units, and inventory. `app/operations/` owns incident and work-order domain records, lifecycle
enums, validation, ORM records, and repository interfaces and implementations.
Operational tests follow the same boundary under
`tests/app/operations/`. Import operational types from `app.operations.domain`,
`app.operations.models`, or `app.operations.repository`.

Incidents still reference Facilities, Workspaces, and optional EquipmentUnits.
These relationships use SQLAlchemy's shared registry and
[late-evaluated relationship references](https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#late-evaluation-of-relationship-arguments),
with cross-module type imports under `TYPE_CHECKING` to avoid circular imports.
`app/persistence/models.py` registers all records for application startup;
Alembic and the development seed also load the operations models. Moving
incidents into this package did not change the schema. WorkOrder persistence is
introduced by migration `0009_work_orders`; apply migrations and rerun role
provisioning to install the table permissions and legacy-grant hardening.

## Packaging and Local Artifacts

Setuptools explicitly discovers `app` and its subpackages, following its [package-discovery guidance](https://setuptools.pypa.io/en/stable/userguide/package_discovery.html). Migrations and provisioning are run from the source checkout; the application wheel does not bundle them.

```bash
python -m pip wheel --no-deps --wheel-dir dist .
```

`build/`, `dist/`, bytecode, pytest caches, coverage outputs, and macOS metadata are generated artifacts and are ignored. Keep local logs, database exports, and other private scratch files under the ignored `.local/` directory. `.env.example` may be tracked with placeholders only. Ignore rules do not remove already-tracked files or replace credential review.

Dependency locking, formatting, linting, static typing, and required PR checks are
documented in [the CI guide](docs/ci.md), including equivalent local commands.

## Model Integration Smoke Check

Configure `SPACE_CORP_LLM_MODEL_ID` and `SPACE_CORP_LLM_API_KEY` in your local
`.env` or environment, then run from the repository root:

```bash
.venv/bin/python -m scripts.smoke_llm
```

This makes a real model call using a fixed test prompt and may incur provider
charges. No database is required. See [model integration notes](docs/llm-integration.md)
for bounds, exit codes, and safe telemetry output.
