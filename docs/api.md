# API Documentation

FastAPI generates the endpoint specification from route declarations, Pydantic
schemas, response metadata, and operation IDs. The generated OpenAPI document is
the source of truth for endpoint paths, parameters, response schemas, and status
codes.

When the local API is running, use:

- [Swagger UI](http://127.0.0.1:8000/docs)
- [ReDoc](http://127.0.0.1:8000/redoc)
- [OpenAPI schema](http://127.0.0.1:8000/openapi.json)

Documentation groups endpoints by resource: questions, health, facilities, equipment units,
inventory items, incidents, work orders, equipment models, and components.
Model compatibility appears in the equipment-models group.

This document records cross-cutting conventions and durable usage notes that are
useful outside the generated specification. Keep it current when routes are
added or changed, but do not duplicate every generated schema here.

## Current Facility API

Configure both `SPACE_CORP_DATABASE_URL` and `SPACE_CORP_DEFAULT_WORKSPACE_ID`
before starting the Facility API. After one-time role provisioning, run
`.venv/bin/python -m scripts.bootstrap_development --validate` to apply migrations
and create or verify the configured workspace from the versioned baseline.
The canonical dataset contains five Facilities; see the [dataset guide](dataset.md)
for initial setup and explicit refresh. The API is read-only; development seeding uses the migration-owner
connection while the running application uses the restricted application role.

| Request | Operation ID | Successful response |
| --- | --- | --- |
| `GET /health` | `getHealth` | `200`, `{ "status": "ok" }`; liveness only, without a database check. |
| `GET /facilities?limit=50&offset=0` | `listFacilities` | `200`, `{ "items": [...], "pagination": { "limit": 50, "offset": 0, "total": 0 } }`. |
| `GET /facilities/{facility_id}` | `getFacility` | `200`, one Facility object. |

Facilities expose `id`, `code`, `name`, `facility_type`, `location`,
`operational_status`, `created_at`, and `updated_at`. Workspace ownership remains
internal. List results are ordered by code; `limit` defaults to 50 and accepts
1–100, while `offset` defaults to 0 and must be nonnegative. Empty workspaces and
offsets past the final record return an empty page. Page contents and total are
separate reads under PostgreSQL's default isolation, so concurrent writes can
change the total between reads.

## Core Operational Reads (Waypoint 1.6)

All endpoints are GET-only. Operational list/detail responses follow the Facility
API conventions: typed records, `{items, pagination}` lists, UUID detail paths,
`404` for inaccessible records, `422` for invalid inputs, and safe `503` database
problem responses. No workspace or baseline administration is exposed.

| Collection | Detail | Optional list filters |
| --- | --- | --- |
| `/equipment-units` | `/equipment-units/{equipment_unit_id}` | `facility_id`, `equipment_model_id`, `operational_status` |
| `/inventory-items` | `/inventory-items/{inventory_item_id}` | `facility_id`, `component_id` |
| `/incidents` | `/incidents/{incident_id}` | `facility_id`, `equipment_unit_id`, `status`, `fault_code`, `occurred_from`, `occurred_before` |
| `/work-orders` | `/work-orders/{work_order_id}` | `facility_id`, `status`, `priority` |

Filters are optional exact matches combined with AND. Each status/priority filter
accepts one enum value, as documented in OpenAPI. Incident fault codes are trimmed
and uppercased, consistent with domain input; unclassified incidents do not match
a specified code. Occurrence times require a timezone: `occurred_from` is inclusive,
`occurred_before` exclusive, and a supplied start must precede the end.

Lists reuse `limit` (default 50, range 1–100) and `offset` (default 0, nonnegative).
Totals include the same filters before pagination. Order is ascending asset tag
for units, ID for inventory, occurrence time for incidents, and reference code for
work orders; ID breaks ties. Unknown list parameters are rejected. Nonexistent or
other-workspace relationship filters return an empty page, without disclosing
whether the referenced record exists. Headers cannot change workspace selection.
Concurrent writes can change results between requests or between page/count reads;
this is the same simple pagination contract as Facilities.

Shared catalog reads support both browsing and following operational references:

- `GET /equipment-models` lists model revisions.
- `GET /components` lists component revisions.

Both lists accept optional `catalog_release_id` filtering and the existing
`limit`/`offset` parameters. They return all releases when the filter is omitted,
ordered by code then ID. Totals reflect the release filter; an unknown release
returns an empty page. Unused definitions are included.


- `GET /equipment-models/{equipment_model_id}` returns an exact model revision.
- `GET /components/{component_id}` returns an exact component revision.
- `GET /equipment-models/{equipment_model_id}/components` returns a paginated list
  of compatible components, ordered by code then ID. A missing model gives `404`;
  an existing model without compatibility entries gives an empty page.

Models and components expose their `catalog_release_id`. These are shared immutable
records, accessible across workspaces; no implicit latest-release selection is
performed. Resolve model IDs from equipment units and component IDs from inventory
or compatibility results, or browse the catalog lists. Release administration and
advanced catalog search remain outside this waypoint.

### Relationship and Question Semantics

The operational read endpoints supply records for bounded questions, with Q1–Q5 as
canonical examples rather than an exhaustive list of use cases. The question routes
below wrap the existing [query layer](structured-queries.md) and `AnswerService`;
they do not change the filters or semantics of operational GET endpoints.
Equipment status and incident status support Q1. Exact model compatibility
and local inventory support Q2. Work-order status, priority, and due times support
Q3. Unit model references and incident fault/time filters support Q4. Inventory
quantity and reorder point support Q5. Consumers must paginate through all relevant
records when assembling a complete result; a single page is not a complete answer.

Work orders preserve separate `originating_incident_id` and
`target_equipment_unit_id`. Follow the incident to its affected unit; do not assume
that this is the work target. Null references retain facility-level work. No
implicit current-time overdue flag is calculated. Compatibility alone does not
establish a repair, and a missing inventory row is distinct from recorded zero stock.

### Repeatable Local Verification

Use the existing setup and role provisioning in [local PostgreSQL](local-postgresql.md),
then run the sole seed command and start/restart the API:

```bash
.venv/bin/python -m scripts.bootstrap_development --validate
.venv/bin/uvicorn app.main:app --reload
```

With the server running, this read-only example verifies a successful response from
every new endpoint using IDs discovered from the configured workspace. Expected
totals apply to an unedited `demo-1` copy; it does not reset workspace edits.

```bash
.venv/bin/python - <<'PY'
import json
from urllib.request import urlopen

base = "http://127.0.0.1:8000"

def get(path):
    with urlopen(base + path) as response:
        assert response.status == 200
        result = json.load(response)
    print("200", path)
    return result

first = {}
for collection, total in (
    ("equipment-units", 60), ("inventory-items", 179),
    ("incidents", 60), ("work-orders", 60),
):
    page = get(f"/{collection}?limit=1")
    assert page["pagination"]["total"] == total
    first[collection] = page["items"][0]
    assert get(f"/{collection}/{page['items'][0]['id']}") == page["items"][0]

unit = first["equipment-units"]
model = get(f"/equipment-models/{unit['equipment_model_id']}")
for collection in ("equipment-models", "components"):
    get(f"/{collection}?limit=5")
    get(f"/{collection}?catalog_release_id={model['catalog_release_id']}&limit=5")
get(f"/equipment-models/{unit['equipment_model_id']}/components")
get(f"/components/{first['inventory-items']['component_id']}")
get(f"/incidents?equipment_unit_id={unit['id']}&status=open")
get(f"/work-orders?facility_id={unit['facility_id']}&priority=high")
get("/incidents?occurred_from=2026-01-01T00:00:00Z&occurred_before=2026-02-01T00:00:00Z")
print("All operational read endpoints verified.")
PY
```

For interactive requests, use `/docs`; `/redoc` and `/openapi.json` expose the same
generated contract. The existing query-model/typed-response approach follows
[FastAPI query parameter models](https://fastapi.tiangolo.com/tutorial/query-param-models/)
and [response models](https://fastapi.tiangolo.com/tutorial/response-model/).

### Acceptance Coverage

The matching route tests under `tests/app/api/routes/` exercise the real restricted
application role against two independent seeded workspaces and an empty workspace.
They verify exact baseline fields, filtered totals, pagination, list/detail success,
empty results, missing records, cross-workspace IDs and relationship filters, and
shared catalog access, release-filtered browsing, unused definitions, and ordering
across releases with duplicate codes. Unit tests verify request validation before database access,
safe database errors, and incident time/fault validation. `tests/app/test_main.py`
checks generated OpenAPI, read-only methods, and documentation pages.

Migration round-trip tests restore their starting application grants after recreating
tables, so they do not leave later read tests without permissions. This preserves
the existing provisioning contract; it does not grant new application privileges.

## Cross-Cutting Conventions

- A valid UUID that does not identify a Facility in the configured workspace
  returns `404`. Missing and other-workspace records use the same response.
- Malformed UUIDs and invalid list query parameters return `422`. FastAPI's
  existing `application/json` validation format is retained: `detail` is an
  array of validation errors. Unknown list query parameters, including
  `workspace_id`, are rejected.
- Database operational failures after startup return `503`. Missing startup
  configuration or an unreachable database prevents the application from
  starting; database exception details are not returned to clients.
- Expected `404` and `503` responses use [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)
  `application/problem+json`, with `type`, `title`, `status`, `detail`, and
  `instance`.
- The server selects the workspace for the current local API. Request query
  parameters or headers cannot change that selection.

Example problem response:

```json
{"type":"about:blank","title":"Not Found","status":404,"detail":"The requested Facility is not available.","instance":"/facilities/11111111-1111-1111-1111-111111111111"}
```

## Current Compatibility Notes

The operational API keeps the health and facility-list success payloads
stable; the facility-detail route is additive. Existing consumers of the earlier
`503` response must accept the `application/problem+json` media type and its
additional problem fields; the string `detail` remains available. Database-unavailable messages now refer to the operational API rather than only
Facilities; clients should branch on status codes rather than exact prose. No frontend
consumer exists in this repository yet.

## Operational Questions (Waypoint 2.4)

`POST /questions` (`askQuestion`) accepts a question and optional bounded page
(`limit` 1–100, default 50; nonnegative `offset`, default 0). Unknown fields are
rejected, including workspace, model, plan, and evidence inputs. The server chooses
the configured default workspace, correlation IDs, and execution controls.
Question text must contain a non-whitespace character and be at most 4,000 characters.

A `200` response contains the typed answered/cautious outcome, resolved plan,
scope status, requested page, returned evidence (or null), and correlation IDs.
Answered outcomes carry deterministic text, record references, and complete/partial
coverage. Cautious outcomes distinguish no results, insufficient evidence, declined
questions, pending review, and withheld answers. A decline's category is in the
plan. Clients must render text safely and preserve scope/coverage disclosures.
Evidence is the bounded result used for this answer, not a live record view.
There is no automatic page fetching or conversation history.

Unanchored scope returns `awaiting_confirmation`, null evidence, and an opaque
confirmation handle. Display the entire resolved plan, including all filters,
entity IDs, time boundaries/as-of values, and the requested page before offering
confirmation. Do not confirm automatically. To revise scope, submit a new question.

`POST /questions/confirm` (`confirmQuestionScope`) accepts only `confirmation_id`
in its JSON body. It executes the exact server-retained plan and page in the
original context; no new model call occurs. A handle is consumed atomically before
execution, even if execution fails. Concurrent/repeated submissions cannot execute
it twice. Missing, expired, consumed, or wrong-workspace handles return the same
safe `404`; submit a new question and review its plan again. Handles stay out of URLs
and application traces; successful responses use `Cache-Control: no-store`.
Treat handles as private bearer values. They are not authenticated reviewer sessions.

The necessary MVP bridge uses an in-memory store capped at 128 pending questions,
expiring after 300 seconds. Live entries are not evicted to admit new ones; capacity
returns `503`. Expired entries are pruned on insertion or access, and shutdown clears
the store. Run one backend process on a trusted local machine. Restart/reload loses
pending questions; multiple workers and public multi-user access are unsupported.
This is an intentional local-MVP limit, not a persistence or authentication system.

### Configuration and errors

Keep the existing database/workspace setup and set `SPACE_CORP_LLM_API_KEY`,
`SPACE_CORP_LLM_MODEL_ID=gpt-5.6-luna`, and `SPACE_CORP_LLM_REASONING_EFFORT=medium`
in local environment configuration. The provider remains configurable. Question
requests return `503` if model configuration is missing; ordinary operational reads
and application startup still work without it. A request-owned provider client is
closed on success or failure using FastAPI's
[yield dependency lifecycle](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).
Existing bounded model retries apply to planning only; confirmation/rendering add none.

Malformed bodies use the existing FastAPI `422` JSON validation response. Query
execution limits return `400`, unavailable references `404`, invalid model proposals
`502`, planning/database/configuration/capacity failures `503`, query execution timeouts
`504`, and unexpected service failures safe `500` problems. These failures are not
empty results. All problem responses use `application/problem+json`. Planning timeouts
currently arrive as the query layer's generic model failure (`503`).

Successful/service-failed operations expose `X-Request-ID`; successful bodies also
include query and synthesis operation IDs. Confirmation retains the original request
and query IDs and produces a new synthesis ID. Pre-operation validation, missing
configuration, and unknown-handle errors do not have an operation trace ID.

### Local manual smoke flow

Use the existing versioned baseline bootstrap and start the API as documented above.
With fresh authorization for any live evaluation, a local request can be made through
Swagger or, for example:

```bash
curl -sS -X POST http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"List inventory below its reorder point.","page":{"limit":50,"offset":0}}'
```

Review the returned plan, then explicitly confirm its handle:

```bash
curl -sS -X POST http://127.0.0.1:8000/questions/confirm \
  -H 'Content-Type: application/json' \
  -d '{"confirmation_id":"<handle from the reviewed response>"}'
```

The first call uses the configured model; this documentation grants no live-run
authorization. Automated route tests instead use fake providers with real restricted
database execution across both workspaces and all 24 development cases. Existing GET
contracts remain unchanged. OpenAPI is generated directly from typed route models;
there is no second hand-maintained schema.

## Documentation Maintenance

When adding or changing a route:

1. update the route's FastAPI metadata, typed request/response models, and tests;
2. verify the generated `/openapi.json` and the Swagger/ReDoc views;
3. update the relevant route summary and cross-cutting conventions here;
4. record compatibility implications when an existing response, status, or
   operation ID changes.

The generated OpenAPI schema remains the detailed contract. This document should
explain stable conventions and how to use the API without becoming a second
hand-maintained schema.
