# Repository Guidance

This repository is a portfolio project for building a production-style agentic AI platform.

## Current Phase

We are in Phase 2 — Minimum Viable Product. Waypoint 2.2 — Structured Query Capability
is complete: the frozen Luna assessment passed all 144 cases across three development
and three fresh wording-holdout runs. See `docs/roadmap.md` and `docs/query-evaluation.md`.
The tested configuration is `gpt-5.6-luna`, medium reasoning, prompt 6, and
`scope_confirmation` execution mode. Unanchored plans require exact-plan caller
confirmation before evidence execution; simulated evaluation review is not autonomous
accuracy. Preserve all assessment reports, including earlier failures. The live batch
permission is exhausted; obtain fresh approval for any further live evaluation.
Waypoint 2.3 is complete. The application renders evidence-backed answers across all
five domains with reference validation, cautious responses, and query-to-answer tracing.
Only query planning calls the model. Current fixed-evidence assessments pass 24/24 each;
offline replay of all 144 saved outcomes verifies the disclosure correction. The original
safe unnecessary refusal remains recorded within the query-aligned pilot allowance.
Full verification passed 1,210 tests, including required PostgreSQL integration, with
no failures or skips. See `docs/answer-evaluation.md` for evidence and limitations.
Preserve historical reports and source attribution. Additional live calls require fresh
approval. Waypoint 2.4 is active: the question/confirmation HTTP boundary is implemented;
frontend implementation and paired browser acceptance remain pending. Keep this a
lightweight local MVP; see `docs/api.md` for the single-process confirmation contract.

## Development Instructions

- Make small, reviewable changes.
- Describe roadmap progress by delivered capability and verification, not chat-specific numbered units of work.
- Default to `gpt-5.6-luna` with medium reasoning for bounded queries and evaluations. Keep the provider configurable; discuss model changes before switching. Preserve historical frozen protocols rather than rewriting their model IDs.
- Obtain explicit approval for each live evaluation run that sends fixture questions and query schemas to OpenAI. Approval applies to that single run only; do not infer permission for later runs.
- Inspect the repository before editing.
- Before editing, identify the files in scope; after editing, summarize the files changed and verification performed.
- Run the relevant test suite and report failures, skips, and any remaining coverage gaps.
- Do not add agents, RAG, MCP, vector databases, authentication, Docker, CI/CD, or extra infrastructure unless explicitly asked.
- Prefer simple architecture over premature abstraction.
- Check current official guidance and established practice for architectural decisions; document meaningful deviations when project constraints justify them.
- Use the repository's Python version and dependencies as defined in `pyproject.toml`.
- Keep interfaces typed.
- Use explicit inheritance when a concrete class intentionally implements a project-defined protocol, so the relationship is visible and checked by the type checker.
- Do not introduce dependencies without explaining why.
- Work only on the active roadmap waypoint unless the task explicitly expands scope. Do not implement future-waypoint architecture speculatively.
- When all completion criteria for a waypoint have been verified, update its status to complete in the same change; do not mark it complete when required checks are skipped or unverified.

## Structured Query Guidance

- Treat `queries-3` as development data, not independent acceptance evidence. Freeze the prompt/model/protocol before holdout runs; never tune on holdout results while retaining that set as held out. Preserve every planned run and report. Follow `docs/query-evaluation.md`; do not infer a live-call authorization from process work.
- Treat Q1–Q5 as canonical acceptance examples, not an exhaustive intended-use list or production operation registry.
- Use the bounded domain contracts in `app/queries/contracts.py`; [structured-query notes](docs/structured-queries.md) define their semantics and current limits.
- Support combinations of approved typed filters. Do not add one hardcoded operation per natural-language question or silently apply canonical-example filters to broader requests.
- Keep workspace, catalog pins, authorization, pagination, execution limits, and read-only enforcement outside model control. Schema validation alone is not authorization or proof of correctness.
- Distinguish unsupported capability, prohibited behavior, missing input, and ambiguity. Never silently substitute a different question or guess entity identities.
- Preserve canonical baseline evidence and add versioned cases for novel combinations, filter boundaries, and unsafe requests. Unit 1 schema tests do not prove query execution or model accuracy.
- Document and test any extension of the query language within the active waypoint; arbitrary SQL, arbitrary joins, grouped analytics, and multi-query planning are not implicitly authorized by the flexibility goal.

## Python Environment

- Use the repository-local `.venv` for Python, pytest, and development commands.
- Install or update dependencies with `python -m pip` inside `.venv`; do not install project dependencies globally.
- Keep `.venv/`, credentials, and local database files out of commits. Update `pyproject.toml` when a dependency is required.

## API Documentation

- Treat FastAPI route declarations, Pydantic schemas, and response metadata as the source of truth for the API contract.
- Keep cross-cutting API conventions, durable usage notes, and compatibility guidance in `docs/api.md`; keep the README focused on setup and links to generated documentation.
- When adding or changing a route, update its FastAPI metadata, typed models, tests, and the relevant `docs/api.md` section; verify `/docs`, `/redoc`, and `/openapi.json` when practical.
- Do not create a second hand-maintained OpenAPI schema. The generated OpenAPI document remains the detailed endpoint contract.

## Test Organization

- Mirror the application source structure under `tests/`.
- Name test files with the `test_` prefix.
- Tests for `app/main.py` should initially live in `tests/app/test_main.py`.
- When `app/main.py` contains enough routes to justify separate test files, route tests may be organized under `tests/app/main/`, such as `tests/app/main/test_health.py` and `tests/app/main/test_<route_name>.py`.
- Apply the same source-to-test path convention to other modules. For example, tests for `app/config.py` should live in `tests/app/test_config.py`.
- Route modules follow the same convention. For example, tests for `app/api/routes/facilities.py` should live in `tests/app/api/routes/test_facilities.py`.

## Test Coverage

For each change:

- map automated tests to the active waypoint's completion criteria
- cover the primary success path
- cover meaningful failure or edge cases introduced by the change
- do not stop after adding a nominal number of tests
- before declaring work complete, identify any known coverage gaps
- if a gap is intentionally left uncovered, explain why
- distinguish a passing test from a skipped or environment-dependent test

## Commit Messages

Use concise, feature-centric commit messages.

Prefer:
- `feat: add facility health endpoint`
- `test: add facility API coverage`
- `fix: handle missing facility records`

Avoid:
- implementation-detail-heavy messages
- vague messages like `updates`, `changes`, or `fix stuff`
- unnecessarily long commit messages

Keep the message focused on the user-facing or architectural capability delivered.

## Branch Naming

Use short, descriptive branch names tied to the active roadmap waypoint when applicable.

Format:

`<type>/<waypoint>-<short-description>`

Allowed types:
- `feat` — new capability
- `fix` — bug fix
- `docs` — documentation-only change
- `test` — tests or evaluations only
- `refactor` — behavior-preserving structural change
- `chore` — tooling, configuration, CI, or maintenance

Examples:
- `feat/0.2-minimal-backend`
- `feat/1.2-facility-domain-model`
- `fix/1.4-equipment-relationship`
- `docs/0.1-project-roadmap`
- `test/2.2-query-safety`
- `refactor/4.2-retrieval-interface`
- `chore/ci-test-pipeline`

Rules:
- use lowercase
- use hyphens between words
- keep names concise
- describe the capability, not the implementation method
- include the roadmap waypoint when the work belongs to one
- create a new branch for each independently reviewable capability
- keep `main` as the only long-lived branch for this single-contributor project
- do not use personal, temporary, or agent-specific names such as `dev`, `working`, `codex`, or `new-stuff`
- delete merged branches unless there is a specific reason to keep them
