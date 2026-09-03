# Repository Guidance

This repository is a portfolio project for building a production-style agentic AI platform.

## Current Phase

We are only setting up the development foundation. Do not implement AI features yet.

## Development Instructions

- Make small, reviewable changes.
- Inspect the repository before editing.
- Before making changes, summarize the files you plan to create or modify.
- After making changes, summarize exactly what changed.
- Run tests when tests exist.
- Do not add agents, RAG, MCP, vector databases, authentication, Docker, CI/CD, or extra infrastructure unless explicitly asked.
- Prefer simple architecture over premature abstraction.
- Backend will start with Python, FastAPI, and pytest.
- Keep interfaces typed.
- Do not introduce dependencies without explaining why.

## Test Organization

- Mirror the application source structure under `tests/`.
- Name test files with the `test_` prefix.
- Tests for `app/main.py` should initially live in `tests/app/test_main.py`.
- When `app/main.py` contains enough routes to justify separate test files, route tests may be organized under `tests/app/main/`, such as `tests/app/main/test_health.py` and `tests/app/main/test_<route_name>.py`.
- Apply the same source-to-test path convention to other modules. For example, tests for `app/config.py` should live in `tests/app/test_config.py`.

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
- `fix/3.3-vector-retrieval`
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
- do not use personal, temporary, or agent-specific names such as `dev`, `working`, `codex`, or `new-stuff`
- delete merged branches unless there is a specific reason to keep them
