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

- [ ] Complete

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

- [ ] Complete

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

- [ ] Complete

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

### Architectural Value

Introduces durable structured state.

Creates the foundation for operational data, workflow state, evaluations, and audit records.

### Completion Criteria

- database can be started locally
- application successfully connects
- initial empty migration applies successfully
- automated test verifies database connectivity
- database startup and migration commands are documented

### Status

- [ ] Complete

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

### Status

- [ ] Complete

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

### Status

- [ ] Complete

---

## Waypoint 1.4 — Core Operational Schema

### Capability

The database represents enough of the fictional organization to support meaningful operational questions.

### Initial Entities

Recommended minimum:

- Facility
- EquipmentModel
- EquipmentUnit
- Component
- InventoryItem
- Incident
- WorkOrder

### Architectural Value

Creates the minimum relational world required for later structured reasoning.

### Completion Criteria

- entity relationships are documented
- migrations create the schema
- foreign-key constraints enforce valid relationships
- basic repository tests exist for each major entity
- schema supports the first planned demo questions

### Status

- [ ] Complete

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

### Completion Criteria

- seed process is repeatable
- all foreign keys are valid
- seeded identifiers are deterministic where practical
- seed validation checks pass
- dataset can be recreated from scratch

### Status

- [ ] Complete

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

### Architectural Value

Prevents application code from being tightly coupled to one model implementation.

### Completion Criteria

- test endpoint or internal service can successfully invoke a model
- provider implementation is behind an interface
- failures are handled predictably
- model and prompt identifiers are logged

### Status

- [ ] Complete

---

## Waypoint 2.2 — Structured Query Capability

### Capability

A natural-language question can be translated into a safe structured query workflow.

### Example

> Which lunar facilities currently have fewer than two spare thermal control units?

### Recommended Flow

User question  
→ schema/context selection  
→ structured query plan  
→ validated query  
→ database execution  
→ structured result

### Safety Requirement

The model must not receive unrestricted database execution capability.

### Architectural Value

Introduces model-guided reasoning while retaining deterministic execution controls.

### Completion Criteria

- at least five supported question patterns work
- generated queries are validated before execution
- database access is read-only
- invalid queries fail safely
- query execution is traced
- automated tests cover supported and unsafe cases

### Status

- [ ] Complete

---

## Waypoint 2.3 — Structured Answer Synthesis

### Capability

Structured database results are converted into a useful natural-language answer.

### User Value

A user can ask an operational question conversationally instead of using an API or SQL.

### Completion Criteria

- answer is based only on returned structured data
- empty-result behavior is handled correctly
- model cannot invent records absent from evidence
- request trace links user query, database query, results, and final answer

### Status

- [ ] Complete

---

## Waypoint 2.4 — Minimal User Interface

### Capability

A user can submit a question and view the answer through a basic web interface.

### UI Scope

Only:

- input box
- submit action
- response display
- loading state
- basic error state

### User Value

Transforms the backend into a demonstrable product.

### Architectural Value

Establishes frontend/backend API boundary.

### Completion Criteria

- UI launches locally
- question reaches backend
- answer is displayed
- failure is shown gracefully
- no advanced styling required

### Status

- [ ] Complete

---

# MVP MILESTONE

The project reaches **Minimum Viable Product** when Waypoint 2.4 is complete.

The MVP must demonstrate:

1. working frontend
2. working backend
3. persisted structured operational data
4. natural-language structured-data question
5. safe query generation/execution
6. grounded answer synthesis
7. automated tests
8. basic tracing/logging

At this point the project should already be demoable.

Everything after this section is an enhancement.

---

# Phase 3 — Unstructured Knowledge and RAG

## Objective

Allow questions to incorporate technical documents and operational knowledge.

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

### Status

- [ ] Complete

---

# Phase 4 — Multi-Source Reasoning

## Objective

Support questions requiring both relational data and document retrieval.

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

### Status

- [ ] Complete

---

## Waypoint 5.3 — Action-Aware Routing

### Capability

The system distinguishes informational requests from action requests.

### Completion Criteria

- request such as “what is wrong?” does not execute tools
- request such as “create a maintenance ticket” selects the action capability
- ambiguous action requests do not execute automatically
- routing is evaluated against a gold set

### Status

- [ ] Complete

---

# Phase 6 — Durable Human-in-the-Loop Workflows

## Objective

Demonstrate long-running agent workflows capable of pausing and resuming safely.

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

### Status

- [ ] Complete

---

# Phase 7 — Observability and AI Control Plane

## Objective

Make internal AI behavior inspectable.

---

## Waypoint 7.1 — Standardized Tracing

### Capability

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

---

## Waypoint 8.1 — Evaluation Dataset Schema

### Capability

Evaluation cases are stored using a standardized schema.

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

**Phase 0 — Development Foundation**

Current recommended waypoint:

**Waypoint 0.1 — Repository Conventions**

The project should not begin implementing later phases until the current waypoint is complete.

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
- the next waypoint can begin without unfinished hidden dependencies