# Project Brief: Agentic AI Operations Platform

## Overview

This project is a portfolio-grade demonstration of full-stack agentic AI engineering.

The goal is to build a production-style AI operations platform that can answer user questions across both structured and unstructured data, coordinate multiple tools and reasoning steps, execute governed actions, pause for human input when required, persist workflow state, and later resume execution from the saved state.

The application domain will be a fictional near-future space operations company. The domain is intentionally synthetic so the project can control its data model, documents, policies, failure cases, and evaluation ground truth without depending on proprietary or sensitive datasets.

The platform should feel like an internal mission-operations copilot rather than a generic chatbot.

The system should favor modular, service-oriented architecture. Capabilities should be separated behind clear interfaces and independently testable boundaries where practical. Microservices may be introduced when they provide meaningful isolation, ownership, scaling, deployment, security, or failure-containment benefits, but the project should avoid splitting functionality into separate services solely for architectural appearance.

## Primary User Experience

A user should be able to ask questions such as:

- What does a specific equipment fault code mean?
- Has this failure occurred before?
- Which replacement components are compatible with the affected system?
- Are compatible parts available at the relevant facility?
- Which maintenance procedure applies?
- Which facilities or systems match a set of operational conditions?
- What recent incidents or technical bulletins are relevant?

Some requests may require information from several sources before an answer can be produced.

The platform should also support governed actions such as:

- creating maintenance requests
- creating operational incidents
- sending internal notifications
- requesting replacement equipment
- updating selected workflow states

Actions that are sensitive, irreversible, ambiguous, or outside a user's authority should require deterministic policy checks and, where appropriate, human approval.

## Data Model

The platform will combine structured operational data with unstructured technical knowledge.

Structured data may include:

- missions
- facilities
- personnel
- equipment models
- installed equipment
- components and compatible parts
- inventory
- suppliers
- maintenance events
- work orders
- incidents
- shipments
- operational alerts

Unstructured data may include:

- equipment manuals
- maintenance procedures
- technical bulletins
- operational policies
- safety procedures
- incident reports
- engineering notes
- logistics documentation

The initial dataset will be synthetic and internally consistent.

A canonical world model should be used so that relational records, documents, historical events, and evaluation questions reference the same entities and facts.

## Architectural Objectives

The project should demonstrate strong architectural separation without introducing distributed-system complexity prematurely.

The preferred approach is:

1. define clear capability and domain boundaries
2. implement those boundaries as independently testable modules or services
3. use explicit contracts between components
4. allow selected components to be deployed independently where doing so provides a clear engineering benefit

Potential independently deployable services may eventually include:

- application/API service
- agent orchestration service
- document ingestion service
- retrieval service
- evaluation service
- workflow or approval service
- notification or communications service
- MCP servers
- administrative or observability backend

Not every capability must become a separate networked service.

A modular monolith or small collection of coarse-grained services is preferable to a large monolithic application, but excessive microservice decomposition should be avoided.

Service boundaries should be justified by considerations such as:

- independent scaling requirements
- different deployment lifecycles
- fault isolation
- security or permission boundaries
- ownership boundaries
- long-running or asynchronous workloads
- external integration boundaries
- differing persistence requirements

Where components remain in the same process initially, their interfaces should be designed so they can later be extracted into independent services without major rewrites.

The project should demonstrate understanding of both the benefits and costs of microservice architecture.

## AI Capabilities

The system should eventually demonstrate the following capabilities:

### Structured Data Reasoning

Users should be able to ask natural-language questions that require querying relational data.

The system should safely translate user intent into validated structured queries rather than allowing unrestricted model-generated SQL execution.

### Retrieval-Augmented Generation

The platform should support document ingestion, chunking, embeddings, retrieval, reranking, metadata filtering, context construction, and grounded response generation.

Retrieval should preserve source provenance so responses can be traced back to supporting evidence.

### Intent Routing and Planning

The system should determine which capabilities are required for a request.

Some requests may require only structured data, only document retrieval, or multiple capabilities in combination.

More complex requests may be decomposed into dependent steps that can execute sequentially or concurrently.

### Tool Use and Actions

Agents should be able to invoke typed tools for both read and write operations.

Write operations must enforce authorization, validation, idempotency, and policy outside of the language model.

Tools should expose explicit contracts so that their implementation can remain local initially and later move behind service or MCP boundaries without changing agent behavior unnecessarily.

### Human-in-the-Loop Controls

Human participation should be a first-class workflow capability rather than a simple synchronous confirmation prompt.

The system should support workflows that:

1. reach a point requiring human input or approval
2. persist the complete workflow state
3. transition into a waiting state
4. remain paused for an arbitrary period of time
5. accept the required human action later
6. reload the saved workflow state
7. validate the human response
8. resume execution from the appropriate workflow step

Human intervention may be required for reasons such as:

- high-risk or irreversible actions
- ambiguous user intent
- insufficient or conflicting evidence
- authorization or policy escalation
- exceptional operational conditions
- manual data entry or review
- financial or safety thresholds

The workflow should not depend on an in-memory process remaining alive while waiting.

A paused workflow should be recoverable after application restarts, worker failures, or deployment events.

The system should expose workflow states such as:

- running
- waiting for approval
- waiting for user input
- approved
- rejected
- resumed
- completed
- failed
- cancelled

The administrative interface should allow operators to inspect pending human tasks and understand why a workflow is waiting.

### Durable Workflow State and Resumption

Agent workflows should be modeled as durable stateful processes.

The system should persist enough information to reconstruct and resume an interrupted workflow, including where appropriate:

- workflow identifier
- thread or conversation identifier
- current workflow step
- completed steps
- pending steps
- user request
- relevant conversation context
- retrieved evidence
- tool results
- approval requirements
- human responses
- model and prompt versions
- retry information
- timestamps
- workflow status

Workflow state should be versioned or structured so that the system can reason about compatibility as the application evolves.

Resuming a workflow should avoid unnecessarily repeating completed side effects.

Write-capable steps should use idempotency controls so that retries or resumption cannot accidentally execute the same action multiple times.

The platform should demonstrate scenarios in which a workflow is paused, the application or worker is restarted, and the workflow successfully resumes later after the required human action is supplied.

### Context Management

The platform should explicitly manage conversation history, working context, retrieved evidence, tool results, and token budgets.

Long-term memory may be introduced later where it provides a clear benefit.

Persisted workflow state and LLM context should be treated as related but distinct concepts.

The system should not assume that the entire historical workflow state must be placed into model context when a workflow resumes.

Instead, the context manager should reconstruct only the information necessary for the next reasoning step.

## Example Human-in-the-Loop Scenario

A mission operator asks:

> Take Environmental Control Unit ECS-14 offline and create an emergency maintenance request.

The workflow may:

1. retrieve the equipment record
2. inspect current operational state
3. retrieve relevant procedures and policies
4. determine that taking the unit offline is safety-critical
5. create a proposed action plan
6. persist workflow state
7. transition to `WAITING_FOR_APPROVAL`
8. create a human approval task for the Flight Director

The initial request then completes without executing the shutdown.

Several minutes or hours later, a Flight Director approves the request.

The system:

1. receives the approval event
2. retrieves the persisted workflow
3. verifies that the approval is valid and has not expired
4. confirms that relevant conditions have not changed
5. restores the required working context
6. resumes at the previously suspended step
7. executes the authorized action using an idempotency key
8. creates the maintenance request
9. records the final result and audit trail
10. marks the workflow completed

This should remain functional even if the original application process no longer exists.

## Evaluation

Evaluation is a first-class component of the project rather than an afterthought.

A gold evaluation dataset should include more than question-and-answer pairs.

Evaluation cases may contain:

- expected intent
- expected plan or workflow
- expected tools
- expected tool arguments
- required sources
- expected facts
- reference answer
- prohibited actions
- whether approval is required
- expected pause point
- expected workflow state
- expected resumption behavior
- expected final state
- difficulty and category metadata

Deterministic evaluators should be used wherever possible.

Examples include:

- correct tool selection
- correct tool arguments
- correct database result
- required approval behavior
- correct workflow pause state
- correct workflow resume point
- absence of premature side effects
- idempotent behavior after retry or resumption
- retrieval of required evidence
- final state after an action

LLM-based evaluators may be used for semantic criteria such as:

- answer correctness
- completeness
- groundedness
- citation quality
- policy interpretation

Human-labeled examples should eventually be used to calibrate model-based evaluators.

## Observability

The system should provide detailed tracing across agent workflows and service boundaries.

Important telemetry includes:

- request latency
- model latency
- tool latency
- retrieval latency
- service-to-service latency
- token usage
- estimated cost
- routing decisions
- generated plans
- tool calls and results
- retrieved sources
- context composition
- evaluator results
- approval decisions
- workflow pause and resume events
- state persistence events
- retry attempts
- errors and failures

A single logical workflow should remain traceable across multiple processes, services, and time periods.

The system should preserve correlation and trace identifiers so that an operator can follow a request from its original user interaction, through downstream services and a waiting period, to its eventual resumed execution and completion.

## Admin and Evaluation Interface

A lightweight administrative portal should eventually support:

- viewing traces
- inspecting agent inputs and outputs
- viewing tool activity
- reviewing retrieved evidence
- examining evaluation results
- comparing model or prompt variants
- reviewing failed cases
- viewing cost and latency metrics
- managing selected experimental configuration
- viewing paused workflows
- viewing pending human approvals or input requests
- approving or rejecting eligible actions
- inspecting workflow state before resumption
- reviewing workflow history after completion
- inspecting service-level health and failures where useful

The frontend does not need to be visually sophisticated.

The majority of project effort should remain focused on AI architecture, data systems, service boundaries, safety, evaluation, workflow durability, and observability.

## Development and Deployment

The project should eventually include a CI/CD workflow that evaluates changes to AI behavior before deployment.

Changes that may trigger regression evaluation include:

- model changes
- prompt changes
- retrieval changes
- chunking strategy changes
- embedding model changes
- reranker changes
- agent orchestration changes
- workflow-state changes
- tool schema changes
- service contract changes

Deployment gates should prioritize deterministic quality and safety checks.

Model-based reviews and evaluators should provide additional evidence rather than act as the sole source of truth.

Migration and compatibility testing should eventually verify that persisted workflows can be safely handled when workflow definitions or application versions change.

Independently deployable services should have their own unit and contract tests where appropriate, while end-to-end tests should validate behavior across service boundaries.

## Development Philosophy

The project should be built iteratively using small, reviewable changes.

The initial implementation should remain intentionally simple.

Advanced capabilities should be introduced only after the underlying foundation is working and tested.

The architecture should favor explicit interfaces and deterministic control where possible.

Language models should be used where reasoning or semantic interpretation provides clear value, not where ordinary application logic is sufficient.

The system should demonstrate not only how to build agents, but also when not to use one.

Durable workflow behavior should be implemented using explicit persisted state and workflow semantics rather than relying on an LLM conversation remaining active.

Service decomposition should follow the same principle: use distributed architecture where it creates meaningful engineering value, not merely to maximize the number of technologies or services in the project.

## Initial Technical Direction

The initial backend will use:

- Python
- FastAPI
- pytest

Additional infrastructure such as PostgreSQL, vector storage, model providers, workflow persistence, queues or eventing, MCP, observability tooling, service containers, and CI/CD will be introduced incrementally as requirements emerge.

No specific agent, workflow, or microservice framework should be assumed at the beginning of the project.

The orchestration approach should remain explicit enough to demonstrate how routing, state, tool execution, context construction, retries, persistence, human intervention, service interaction, and resumption work.

The initial codebase may begin as a small modular application. Capabilities should be organized behind boundaries that allow selected components to evolve into independent services when justified.

## Current Scope

The current phase is development foundation only.

Immediate goals are:

1. establish repository conventions
2. configure coding-agent instructions
3. create a minimal backend service
4. establish automated testing
5. introduce modular service boundaries
6. introduce structured data incrementally
7. build the project through small, understandable implementation tasks

The following are explicitly out of scope for the initial foundation phase:

- multi-agent orchestration
- RAG
- vector databases
- MCP
- authentication
- durable workflow orchestration
- human approval workflows
- distributed microservice deployment
- production infrastructure
- advanced observability
- automated AI evaluation
- CI/CD deployment gates

These capabilities will be added in later milestones after the foundational application is stable.