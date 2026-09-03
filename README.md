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

**Phase 0 — Development Foundation**

The project is currently establishing its basic engineering foundation.

Current priorities:

1. establish repository conventions
2. configure coding-agent instructions
3. create a minimal backend service
4. establish automated testing
5. define modular boundaries
6. introduce structured data incrementally

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

Additional architecture and roadmap documentation will be added as the project evolves.

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

## Project Status

This project is under active development and is intentionally being built from the foundation upward.
