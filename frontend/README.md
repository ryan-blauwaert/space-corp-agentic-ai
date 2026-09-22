# Space Corp interface

The lightweight Waypoint 2.4 frontend lives alongside the FastAPI backend. It currently
provides read-only facilities and scoped equipment. The Ask screen is a placeholder;
question submission and paired question/answer acceptance remain the next work.
The [root roadmap](../docs/roadmap.md) remains authoritative.

## Local setup

Use Node **24.19.0** (also recorded in `.node-version`) and pnpm **11.19.0**.
Install pnpm using your usual Node toolchain; dependencies are local to this directory.
Backend setup remains in the [root README](../README.md) and [dataset guide](../docs/dataset.md).

From the repository root, start the configured, seeded backend:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open http://127.0.0.1:5173. Both development and local build preview proxy `/api`
to the backend on port 8000. Browser requests stay on the frontend origin; no CORS
or backend change is needed. The frontend never reads backend secrets or chooses a
workspace. The existing server configuration supplies that scope. This is a local
demo, not a deployment setup. No live model calls are made by these views.

## Verification and build

```sh
pnpm build
pnpm test
pnpm format:check
pnpm types:check
pnpm preview
```

`build` includes TypeScript checks and produces `dist/`. Preview uses port 4173 and
still needs the backend. `node_modules/` and `dist/` are ignored.

React and React Router provide components/navigation. Vite supplies local development
and bundling; see its [official guide](https://vite.dev/guide/). TypeScript checks the
client. Vitest, Testing Library, and jsdom test user interactions and HTTP states;
Prettier keeps source formatting consistent. No UI kit, state container, or backend
runtime dependency is introduced. TypeScript is pinned to 5.9.3 because the installed
OpenAPI generator requires TypeScript 5; newer major versions are not interchangeable.

## API contract

```sh
pnpm types:generate
pnpm types:check
```

Generation uses the repository `.venv` to construct FastAPI's OpenAPI document without
starting the server, connecting to PostgreSQL, or calling a model. Install the existing
backend dependencies first. [openapi-typescript](https://openapi-ts.dev/introduction)
generates `src/api/generated.d.ts`. Do not edit that file manually.
`src/api/provenance.json` records the source backend Git revision and schema SHA-256.
The digest identifies the actual schema, including any uncommitted backend changes;
the revision alone does not prove a clean source tree. The check compares the current
schema digest and generated types, so moving HEAD for frontend changes does not create
false drift. Review and retain regenerated types/provenance with API changes. There is
no checked-in duplicate OpenAPI schema.

Responses are typed from the generated GET operations. Errors display safe local
messages rather than raw backend payloads. Loading, empty workspace, empty equipment,
empty page, missing record, invalid pagination, and unavailable backend are distinct
states. Retry is explicit. Navigation aborts obsolete reads; failed/old responses never
replace the new page. Lists use ten-record pages with backend totals and bounded offsets.
An empty page does not mean the workspace or facility is empty. No automatic full-list
fetching or new query capability is introduced.

## Current verification scope

Component tests exercise browsing/detail, facility pagination, empty/error/retry states,
invalid navigation, keyboard entry, focus, and stale-request cancellation. Manual browser
checks cover the real baseline facilities/equipment and equipment pagination at desktop
and narrow widths. These checks support the roadmap's shell, operational-context,
contract, and meaningful-state criteria. They do not constitute question-flow or full
waypoint acceptance; those await the next slices. No new CI configuration is added.
