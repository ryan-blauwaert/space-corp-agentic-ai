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

No particular agent framework, workflow framework, vector database, or deployment platform is assumed at the start.

## Current Status

**Phase 1 — Structured Operational Backend**

The latest completed waypoint is **1.3 — Facility API**; the next is **1.4 — Core Operational Schema**. The backend includes typed configuration, PostgreSQL migrations, workspace-scoped Facility persistence, and read-only list/detail endpoints. See the [roadmap](docs/roadmap.md) for verification and completion status.

Advanced AI capabilities are intentionally not being implemented yet.

## Planned Capability Areas

### Structured Data

Natural-language requests over relational operational data, with controlled and validated query execution.

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

The backend requires Python 3.12 or later.

Create a virtual environment and install the application with development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
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

### Application Configuration

Settings are loaded from environment variables and an ignored project-root `.env` file when the application starts. Copy the tracked template before starting the API:

```bash
cp .env.example .env
```

The application refuses to start until its database URL and default workspace ID are configured, and it checks database reachability during startup. This prevents a server that cannot serve Facility API requests from accepting traffic.

| Environment variable | Default | Accepted values and purpose |
| --- | --- | --- |
| `SPACE_CORP_ENVIRONMENT` | `development` | `development`, `test`, or `production`; identifies the application environment. |
| `SPACE_CORP_APPLICATION_NAME` | `Agentic AI Operations Platform` | A string used as the FastAPI title, visible in the API documentation and OpenAPI schema. |
| `SPACE_CORP_LOGGING_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; validated and stored, but not yet applied to logger configuration. |
| `SPACE_CORP_DATABASE_URL` | Unset (`None`) | A validated PostgreSQL URL used by application database resources. It should use the restricted application role and is required at startup. |
| `SPACE_CORP_MIGRATION_DATABASE_URL` | Unset (`None`) | A validated PostgreSQL URL used only by Alembic schema migrations. It should use the schema-owner migration role. |
| `SPACE_CORP_DEFAULT_WORKSPACE_ID` | Unset (`None`) | UUID of an existing workspace, selected by the server for local Facility API requests. Required at startup. This is not public multi-user authorization. |

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
alembic upgrade head
```

Configure both test URLs to the dedicated `space_corp_test` database before running real PostgreSQL checks:

```bash
pytest -m integration
```

## Project Status

This project is under active development and is intentionally being built from the foundation upward.

## Facility API Contract

Configure both `SPACE_CORP_DATABASE_URL` and `SPACE_CORP_DEFAULT_WORKSPACE_ID` before starting the Facility API. The workspace must already exist; creating and seeding workspaces is not part of this read-only API. Use the migration-owner connection for manual local data setup. The application role accesses Facility rows only.

| Request | Operation ID | Successful response |
| --- | --- | --- |
| `GET /health` | `getHealth` | `200`, `{ "status": "ok" }`; liveness only, without a database check. |
| `GET /facilities?limit=50&offset=0` | `listFacilities` | `200`, `{ "items": [...], "pagination": { "limit": 50, "offset": 0, "total": 0 } }`. |
| `GET /facilities/{facility_id}` | `getFacility` | `200`, one Facility object. |

Facilities expose `id`, `code`, `name`, `facility_type`, `location`, `operational_status`, `created_at`, and `updated_at`. Workspace ownership remains internal. List results are ordered by code; `limit` defaults to 50 and accepts 1–100, while `offset` defaults to 0 and must be nonnegative. Empty workspaces and offsets past the final record return an empty page. Page contents and total are separate reads under PostgreSQL's default isolation, so concurrent writes can change the total between reads.

- `404`: a valid UUID does not identify a Facility in the configured workspace. Missing and other-workspace records return identical errors.
- `422`: malformed UUIDs or invalid list query parameters. FastAPI's existing `application/json` validation format is retained: `detail` is an array of validation errors. Unknown list query parameters, including `workspace_id`, are rejected. Query parameters or headers on detail requests cannot change the server-selected workspace.
- `503`: a database operational failure after startup. Missing startup configuration or an unreachable database prevents the application from starting; database exception details are not returned to clients.

The `404` and `503` responses use [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) `application/problem+json`, with `type`, `title`, `status`, `detail`, and `instance` (request path). For example:

```json
{"type":"about:blank","title":"Not Found","status":404,"detail":"The requested Facility is not available.","instance":"/facilities/11111111-1111-1111-1111-111111111111"}
```

The generated `/openapi.json` documents response schemas, statuses, pagination, and stable operation IDs. Compatibility review for Waypoint 1.3: health and list success payloads remain unchanged; the detail route is additive. Existing consumers of the earlier 503 error must accept the new media type and additional problem fields; the string `detail` is preserved. No frontend consumer exists in this repository yet.

## Packaging and Local Artifacts

Setuptools explicitly discovers `app` and its subpackages, following its [package-discovery guidance](https://setuptools.pypa.io/en/stable/userguide/package_discovery.html). Migrations and provisioning are run from the source checkout; the application wheel does not bundle them.

```bash
python -m pip wheel --no-deps --wheel-dir dist .
```

`build/`, `dist/`, bytecode, pytest caches, coverage outputs, and macOS metadata are generated artifacts and are ignored. Keep local logs, database exports, and other private scratch files under the ignored `.local/` directory. `.env.example` may be tracked with placeholders only. Ignore rules do not remove already-tracked files or replace credential review.

Dependency locking, lint/type-check tooling, and CI remain separate follow-up work. No application dependencies were added for the Facility API fixes.
