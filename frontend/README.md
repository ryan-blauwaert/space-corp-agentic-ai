# Space Corp interface

The lightweight Waypoint 2.4 frontend lives alongside the FastAPI backend. It currently
provides read-only facility/equipment browsing and an operations question screen.
The repeatable paired browser acceptance suite remains the next work.
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
demo, not a deployment setup. Browsing makes no model calls. Submitting a question
uses the configured backend model; confirmation adds no model call. Configure the
backend as described in the [question API guide](../docs/api.md#operational-questions-waypoint-24).
Live evaluation still requires fresh authorization.

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
contract, and meaningful-state criteria. The question coverage below complements these checks; full waypoint acceptance
remains pending. No new CI configuration is added.

## Asking the operations desk

`/ask` accepts a new question of up to 4,000 characters. It sends only that question
and a fixed first page (50 records, offset zero). Facility navigation never silently
scopes the question. Questions are independent; no chat history or local storage is
introduced. Loading/error states use accessible announcements, and focus moves to
the result or error. Nothing submits on navigation or mount.

Unanchored proposals show all plan fields, including unrestricted fields, exact IDs,
comparison operators, booleans, timestamps, and pagination. All filters intersect;
listed alternatives within one filter mean any listed value. Review before selecting
**Confirm scope and retrieve**. The browser sends only the opaque server handle.
Editing or revising the question discards the review. Expiry is conservatively timed
from request start; the server remains authoritative. Failed, expired, or consumed
reviews require a fresh submission, never an automatic confirmation retry.

Answer text is displayed verbatim as plain text, with complete/partial coverage and
all scope disclosures preserved. Expand supporting records and references to inspect
the original returned evidence, including nested relationships and null/zero values.
No page fetching, extra record reads, or prose rewriting happens in the browser.
Cautious outcomes distinguish no results, insufficient evidence, declined questions,
and withheld answers. Server errors are mapped to safe local messages.

Requests are sent from explicit user actions. In-flight buttons are disabled and a
synchronous guard prevents double sends. Stop waiting or route navigation aborts the
browser request and discards late responses, following [React effect cleanup guidance](https://react.dev/reference/react/useEffect#fetching-data-with-effects)
and the [AbortController API](https://developer.mozilla.org/en-US/docs/Web/API/AbortController).
This cannot guarantee server-side cancellation. Waiting is bounded to two minutes;
there is no automatic retry, and a dismissed confirmation cannot be reused. Handles
are never shown in the page, saved in browser storage, or included in URLs.

Question component tests cover direct answers, explicit review/confirmation, validation,
expiry, failed confirmations, duplicate sends, timeout, stale responses, route cleanup,
keyboard submission, safe errors, literal text rendering, partial/cautious outcomes,
and supporting evidence across all five domains. Manual browser verification used a
temporary fake planning provider with real local database execution at 1280px and
390px widths. No live model calls were made. This does not replace the repeatable paired
smoke suite and full waypoint closeout planned for the next increment.

## Current visual preview

Flight Manual (palette 01) is applied for owner review using the approved Space Corp
lockups: stacked in the desktop sidebar and horizontal on narrow screens. The current
layout and query behavior are unchanged. See the [design brief](../docs/frontend-design.md)
for the approval record and remaining identity decisions.

Fonts are served from `public/fonts/`, with their original OFL notices. The unmodified
variable TrueType files were obtained from the official Google Fonts repository:
`ofl/spacegrotesk/SpaceGrotesk[wght].ttf` and `ofl/orbitron/Orbitron[wght].ttf`.
The mark in `public/brand/space-corp.webp` is the lossless encoding extracted unchanged
from the approved design study. CSS reproduces the reference crop and color overlay;
a production vector export remains pending. No runtime font service or package was added.

### Switching palettes in code

Change only `ACTIVE_PALETTE` in `src/palette.ts`, then reload the development page
(or rebuild and relaunch a production preview). The available names are:

- `flight-manual` (default)
- `lunar-workshop`
- `remote-station`
- `deep-space-service`
- `field-repair`

That setting supplies the page colors, both logo lockups, and browser theme color.
The four approved swatches remain exact; panel, muted text, border, hover, and active
button colors are derived centrally. Flight Manual retains its existing reviewed
supporting tones. Semantic status colors stay consistent between themes. There is
no palette dropdown, browser preference, backend setting, or new dependency.
