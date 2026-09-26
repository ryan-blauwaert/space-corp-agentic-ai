# Waypoint 1.5: reproducible operational dataset

The checked-in `data/baselines/demo-1.json` is the canonical baseline. It contains
5 Facilities, 12 EquipmentModels, 36 Components, 33 compatibility pairs, 60
EquipmentUnits, 179 inventory rows, 60 Incidents, and 60 WorkOrders. It pins
`demo-catalog-1`. No external service, random generator, or current-clock input is
needed to reproduce it. The manifest is source-checkout tooling, like migrations;
it is not bundled in the application wheel.

## Initial local setup

Follow [local PostgreSQL setup](local-postgresql.md) to create the migration
owner, development/test databases, and local credentials. Apply the schema and
run the administrator provisioning script once before using the application role:

```bash
.venv/bin/python -m alembic upgrade head
SPACE_CORP_MIGRATION_DATABASE_URL="postgresql+psycopg://space_corp@localhost:5432/space_corp_test" .venv/bin/python -m alembic upgrade head
psql -X -d postgres -f scripts/provision_postgresql_application_role.sql
```

The commands assume `.env` contains the development migration-owner URL and
credentials are already available through `.pgpass` or the local credential
mechanism. Provisioning is administrator work; normal bootstrap uses the schema
owner and does not create roles, change passwords, or grant privileges.

## Create, validate, and refresh a workspace

Use a new UUID for the full dataset. The example is intentionally different from
the old fixed-ID smoke workspace:

```bash
.venv/bin/python -m scripts.bootstrap_development --workspace 15000000-0000-4000-8000-000000000001 --validate
```

This command validates the manifest, applies pending migrations, publishes or
verifies the frozen catalog/baseline, seeds the selected workspace, and checks
exact rows plus all 12 Q1–Q5 scenarios. It prints workspace identity, versions,
record counts, and the number of verified scenarios. Omit `--workspace` to use
`SPACE_CORP_DEFAULT_WORKSPACE_ID`. `--manifest PATH` selects another validated
versioned manifest.

A normal rerun preserves an existing workspace's edits. `--validate` checks
whether it still matches the canonical baseline and reports deviations. To
explicitly discard operational edits in this one pinned workspace and restore
the canonical dataset, use:

```bash
.venv/bin/python -m scripts.bootstrap_development --workspace 15000000-0000-4000-8000-000000000001 --refresh
```

Refresh removes and recreates only that workspace's operational rows in foreign-key
order, within one transaction. Other workspace copies and shared reference data
remain untouched. Failures roll back publication/seeding together; migrations
have their own transaction. The same baseline and workspace produce the same IDs
and timestamps. This is privileged local development tooling, not a reviewer reset
API. Later phases will implement retirement, sessions, and authorization.

The command rejects production/test environments, test database names, nonlocal
connections, missing workspace IDs, and nonempty unpinned legacy workspaces.
It cannot switch a pinned workspace to another baseline. Create a new workspace
for a new baseline instead. The old smoke seeder has been retired; bootstrap is
the only supported seeding command.

For an existing installation, set `SPACE_CORP_DEFAULT_WORKSPACE_ID` in `.env` to
the new dataset workspace UUID, run bootstrap with `--validate`, and restart the
API. `.env.example` uses the UUID shown above. Existing unpinned workspace rows
are retained; they are not rewritten or deleted as part of this switch.

## Exercise the existing API

Start the application using the newly seeded workspace:

```bash
SPACE_CORP_DEFAULT_WORKSPACE_ID=15000000-0000-4000-8000-000000000001 .venv/bin/python -m uvicorn app.main:app --reload
```

In another terminal:

```bash
curl -fsS 'http://127.0.0.1:8000/facilities?limit=5'
```

The response contains five Facilities and `pagination.total` is `5`. Copy an
`items[].id` from that response into:

```bash
curl -fsS 'http://127.0.0.1:8000/facilities/<facility-id>'
```

The detail response contains the selected Facility. Both requests use the
restricted application role from `SPACE_CORP_DATABASE_URL`. The automated
bootstrap test verifies list/detail success and rejects a Facility ID from
another workspace. No new operational HTTP routes are introduced in 1.5.

## Identity, publication, and release enforcement

Operational UUIDs use UUIDv5 with the workspace UUID as namespace. The name is
compact JSON `[baseline_version, entity_collection, logical_key]`, with ASCII
escaping and no whitespace. Collection names are `facilities`, `units`,
`inventory`, `incidents`, and `work_orders`. Thus human codes repeat across copies,
while operational IDs and their references do not. Shared IDs use UUIDv5 with
`NAMESPACE_URL` and compact JSON `["space-corp", version, entity, logical_key]`.

`baselines` stores the full canonical manifest, its SHA-256, and a catalog-release
foreign key. Each seeded Workspace records both baseline and release, with a
composite foreign key ensuring that pair agrees. Existing legacy workspaces keep
null pins; they are not accepted by the canonical scenario runner. The application
role has no baseline or workspace administration privileges.

Publication is serialized by a transaction-scoped advisory lock. Existing
catalogs are compared against their hash, actual model/component rows, and exact
compatibility pairs; changed, missing, or added definitions are rejected. An
existing baseline version must have exactly the same manifest and hash. To change
facts, publish a new release/baseline and create a new workspace. Workspace edits
never modify the canonical manifest. The migration owner remains able to perform
explicit administrative repair; this guarantee is enforced by trusted publication
and restricted application privileges, not protection against a database owner.

Two small triggers enforce catalog pins on unit/inventory inserts and updates.
They avoid duplicating a release discriminator throughout the existing domain
interfaces. The catalog check uses a fixed-search-path `SECURITY DEFINER` function
so it can inspect private workspace pins without exposing workspace administration
to the application role. It locks the workspace row while checking. A separate
trigger prevents repinning and rejects adopting a populated unit/inventory
workspace. Baseline creation additionally requires every operational table to be
empty. No WorkOrder-to-Incident equality trigger is added.

This is a deliberate exception to preferring foreign keys alone: checking the
release of a referenced model/component against a private workspace row cannot
be expressed as a row-local check without additional discriminator columns.
See PostgreSQL's [constraint guidance](https://www.postgresql.org/docs/current/ddl-constraints.html)
and [transaction/row locking](https://www.postgresql.org/docs/current/explicit-locking.html).

## Scenario coverage

The fixed evaluation instant is **2026-01-31 12:00 UTC**; the recurrence window
starts **2026-01-01 00:00 UTC**, inclusive. The end is exclusive. Expected evidence
uses `@collection:key` references that resolve to exact UUIDs for each workspace;
expected answers are authored in the manifest, not generated from query results.

| Question | Dataset cases |
| --- | --- |
| Q1 | Degraded unit with unresolved incidents, unrelated Facility incident, offline units without matching incidents, deduplicated Facility evidence, empty Facility result. |
| Q2 | Compatible parts with positive stock, recorded zero stock, missing stock, no unresolved incident, no listed compatibility. |
| Q3 | Blocked and overdue together, due exactly at evaluation time, unscheduled work, future due date, completed/cancelled/low-priority exclusions, distinct incident and target units, absent target. |
| Q4 | Two matching incidents despite multiple originating work orders, different fault and unknown classification excluded, start boundary included, end and pre-window events excluded, single occurrence and no matches. |
| Q5 | Positive shortfall, zero-stock shortfall, equality excluded, absent inventory excluded, no shortages. |

Q1–Q5 specify these baseline examples only. Exclusions such as completed work or
stock at its reorder point are scenario filters, not universal product restrictions.
The [bounded query layer](structured-queries.md) represents them as explicit filters
and supports additional combinations. Its `data/evaluations/queries-3.json` fixture
references all 12 baseline scenarios and adds six supported variations plus six
declined cases. The loader validates contracts and evidence references. Unit 3 integration tests
execute the facility-equipment and compatible-stock cases against the database;
unit 4 adds work-order, incident, and inventory execution. All 18 supported cases
now have database evidence checks in two workspaces. Unit 5 also runs these cases
through the planning workflow with controlled model responses, and verifies that
all six decline responses prevent evidence execution. These are application checks,
not live model accuracy measurements. Unit 6 adds `python -m scripts.evaluate_queries`, which checks exact workspace
rows, catalog pin, and expected evidence before calling the configured model.
It scores intent, evidence, and decline/execution behavior for all 24 cases.
Live acceptance scored 23/24; a completed-work over-decline remains; see the [evaluation guide](structured-queries.md#repeatable-evaluation-unit-6).
The baseline manifest and its original expectations are unchanged. `queries-3`
clarifies eight compatibility, work-order, and recurrence questions without changing
any expected plan, record, decline, or case count. All six decline questions are
unchanged. `queries-2` is retained to reproduce the original 17/24 live result;
the revised wording scored 23/24 with prompt version 1. A subsequent approved
prompt-version-2 run scored 22/24: missing-facility passed, while completed-work and
ambiguous-unit failed. See the evaluation guide for the preserved run history.

The reference SQL in `scripts/dataset_queries.py` is a fixed acceptance oracle,
not natural-language execution or a public query endpoint. Two-workspace tests
run the same cases against disjoint IDs, edit and refresh one copy, and verify
that the other copy's evidence stays unchanged. Publishing a second catalog also
leaves the first workspace's results unchanged. A foreign or missing input raises
an error rather than being reported as an empty successful query.

## Implementation and coverage

`seed_support.py` owns the shared error and migration-owner guard, including
ownership of the baseline table. `bootstrap_development.py` is the sole command;
`seed_dataset.py`, `dataset_manifest.py`, and `dataset_queries.py` implement its
publication, validated input, and reference-query behavior. There is no parallel
smoke dataset or compatibility seed command.

`test_seed_support.py` retains the real owner/application-role checks from the
retired seed tests. `test_bootstrap_development.py` covers unsafe configuration,
missing migrations, repeatable bootstrap, and the Facility API. `test_seed_dataset.py`
covers the full dataset's counts, isolation, refresh, and existing-workspace
preservation. The old smoke-only tests have been replaced by those checks.

## Verification

```bash
.venv/bin/python -m pytest -q
```

Manifest tests validate references, time/lifecycle rules, classification, quantities,
and uniqueness before publication. PostgreSQL tests verify exact row/ID remapping,
repeatability, explicit refresh, recreation, publication rejection, pins under both
owner and restricted-role connections, migrations from an empty schema, and the
existing API. Integration settings remain in ignored `.env.test`; disposable
PostgreSQL binaries are required for the bootstrap test. No AI, public sessions,
new read API, CI, or infrastructure is part of this waypoint.

Acceptance verification on 2026-09-20: 279 tests passed with no skips, including
an empty-schema rebuild. The example development workspace was seeded and all
12 scenarios validated; existing restricted-role Facility list/detail requests
returned 200. Q1–Q5 `EXPLAIN ANALYZE` checks returned the expected row counts on
the small local dataset. Index tuning under realistic load and concurrent
publication stress testing are not claimed by this acceptance run. One existing
Starlette/AnyIO deprecation warning remains.


## Development versus holdout evaluation

`queries-3` is explicitly development regression data. Its default `purpose` metadata
is `development`; no historical fixture file was rewritten. The new
`queries-holdout-1.json` is labeled `holdout_candidate` and preserves expected
plans/evidence while introducing 24 new question wordings. It is a wording holdout,
not independently collected production data or coverage of new business concepts.
Prompt version 3 was not changed during its creation. New purpose metadata changes
the canonical dataset fingerprint used by report format 3; historical report digests
remain historical. See [the evaluation process](query-evaluation.md) for frozen
configuration, protocol targets, contamination rules, and explicit live-call approval.

The first frozen assessment completed: development supported queries passed 52/54,
while candidate holdout supported queries passed 34/54. Expected declines passed
18/18 in each dataset. See [the preserved assessment](query-evaluation.md#first-frozen-assessment--2026-09-21)
for failure details and an entity-type ambiguity concern in the holdout recurrence
wording. No fixture was changed or excluded after the assessment.

## Additive facility location context

Waypoint 2.4 adds `body_or_system` display metadata while preserving the frozen
`demo-1` manifest, its digest, and all historical query/answer assessment files.
`scripts/facility_locations.py` supplies explicit values for the five known
code/name/location tuples during seeding; unmatched facilities receive null.
The matching frozen backfill is in migration `0012_facility_body_or_system`.
No body is guessed from a facility's type. Existing local location strings remain
unchanged so historical exact-location filters retain their meaning.

To migrate an existing configured development database and verify its baseline:

```sh
.venv/bin/python -m scripts.bootstrap_development --validate
```

Use ordinary bootstrap without `--refresh`: this change does not require replacing
workspace records. If a workspace has intentional edits, `--validate` can report a
baseline mismatch even after a successful migration; it does not undo those edits.

The display uses NASA's terminology “Earth’s Moon” and identifies both bodies for
Lagrange points (e.g. Earth–Moon L1). Naming references:
[NASA Moon facts](https://science.nasa.gov/moon/facts/) and
[NASA/JPL lunar trajectories](https://descanso.jpl.nasa.gov/monograph/series12/LunarTraj--Overall.pdf).
