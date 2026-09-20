# API Documentation

FastAPI generates the endpoint specification from route declarations, Pydantic
schemas, response metadata, and operation IDs. The generated OpenAPI document is
the source of truth for endpoint paths, parameters, response schemas, and status
codes.

When the local API is running, use:

- [Swagger UI](http://127.0.0.1:8000/docs)
- [ReDoc](http://127.0.0.1:8000/redoc)
- [OpenAPI schema](http://127.0.0.1:8000/openapi.json)

This document records cross-cutting conventions and durable usage notes that are
useful outside the generated specification. Keep it current when routes are
added or changed, but do not duplicate every generated schema here.

## Current Facility API

Configure both `SPACE_CORP_DATABASE_URL` and `SPACE_CORP_DEFAULT_WORKSPACE_ID`
before starting the Facility API. Run `python -m scripts.seed_development_data`
after migrations and application-role provisioning to create the configured local
workspace and restore the catalog, Facility, equipment-unit, and inventory smoke
dataset. The API is read-only; development seeding uses the migration-owner
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

The current Facility API keeps the health and facility-list success payloads
stable; the facility-detail route is additive. Existing consumers of the earlier
`503` response must accept the `application/problem+json` media type and its
additional problem fields; the string `detail` remains available. No frontend
consumer exists in this repository yet.

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
