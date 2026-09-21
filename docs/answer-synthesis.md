# Structured answer synthesis

Waypoint 2.3 is in progress. Typed evidence facts, deterministic sentence rendering,
selection validation, and cautious responses are implemented. The free-form model-prose
delivery path has been removed. There is no model selection call, answer endpoint,
query-to-answer orchestration, or live answer assessment yet. The query service is unchanged.

## Implemented direction: render answers from evidence

Application code builds typed facts from returned records and renders the sentences.
A future model call may select fact identifiers for presentation order; it cannot
supply values, prose, names, causes, sentence fragments, or formatting instructions.
All returned records remain in the answer, including when a selection lists only a
subset. This prevents selection from suppressing mandatory fields or disguising a
subset as the complete result. Counts, scope notices, and coverage are application-owned.

The renderer rebuilds facts from the trusted request each time. It does not accept
caller-supplied facts or rendered sentences. The prior `AnswerDraft`, `EvidenceClaim`,
and `validate_draft` interfaces are removed, with no free-prose fallback. The previous
regression that accepted true claims alongside false prose is replaced with tests
that reject prose-bearing selections and prove altered external fact values are not
used for rendering. Constructing an output model alone is not a delivery API.

Rules follow the five result shapes and their fields, not Q1–Q5 identifiers or fixture
wording. Query/filter flexibility is unchanged. No dependencies, schema migrations,
general template engine, additional queries, or new infrastructure were introduced.

## Contracts and application boundary

`app/answers/contracts.py` defines:

- `AnswerRequest`: the original question and trusted `QueryOutcome`, preserving context,
  resolved scope, and typed returned evidence. It rejects mismatched evidence contexts
  and domains, and evidence attached to declined/pending queries.
- `EvidenceFact`: a tagged union of facility-equipment, compatible-stock, work-order,
  incident, and inventory facts. Each contains one complete top-level evidence row,
  including its record relationships, with a snapshot-bound identifier. These values
  are application-built selection inputs, not accepted model output.
- `FactSelection`: only a bounded tuple of unique fact identifiers. Listed facts appear
  first; unlisted facts follow in original order. An empty selection preserves that
  order. Selection does not omit records, approve scope, or set completeness.
- `RenderedAnswer` and `AnswerResponse`: application output containing deterministic
  text/references, caller context, synthesis operation ID, and answered/cautious state.
  The renderer returns an outcome; later orchestration supplies the response/trace wrapper.

The existing frozen, extra-field-forbidding Pydantic models and
[recommended discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)
provide shape validation. Input is revalidated at runtime, including nested copies.
Schema validity is not authorization or proof that a database query was correct.
The request remains a trusted internal boundary, not a client-submittable security token.

`evidence_facts` binds identifiers to a digest of the request, including context,
question, plan, and returned evidence. Cross-request, changed-scope, and changed-evidence
selections are rejected. These digests are local consistency checks, not authentication
or a persisted approval workflow. No fact storage is introduced.

## Rendering and evidence semantics

`app/answers/rendering.py` implements `evidence_facts` and `render_answer`:

- All supplied records and their required fields are rendered; fact selection can only
  prioritize order. Facility totals count facilities, not their nested units/incidents.
- Compatible-stock rows distinguish recorded zero quantity from missing inventory and
  unknown quantity. Supporting incidents are included when returned; a query without
  an incident requirement does not gain one from a canonical example.
- Work-order status, priority, due date, blocked/overdue flags, and the query's as-of
  instant are preserved. Originating incident, incident-affected unit, and direct target
  are labeled separately. A completed order does not become overdue because its due
  date is old, and due-at-the-boundary is not rewritten as overdue.
- Incidents retain status, severity, fault, time, facility, and optional unit. A recurrence
  sentence requires a declared fault and interval, a complete result, matching fault/time
  values in every row, and agreement with an explicit unit filter when present. Two or
  more distinct incidents establish recurrence under those filters; one does not.
  Model-scoped recurrence can span units and never implies they were the same unit.
  No recurrence is inferred from an arbitrary broad count or a partial page.
- Inventory sentences preserve quantity, reorder point, and shortfall. Equality does
  not become below-reorder; no repair, purchase, or other action is claimed.
- Coverage is complete only with offset zero and row count equal to total. Otherwise
  mandatory partial-page wording gives returned and total counts. Only supplied rows
  receive record details. No automatic page fetching occurs.
- References are collected from typed evidence, including nested and supporting
  relationships, and generated by application code. IDs present only in the question,
  plan, caller context, or omitted pages are not added as record citations.
- Stored free text such as fault codes is quoted and escaped for control characters,
  HTML, and Markdown metacharacters. It remains a labeled data value, not an instruction
  or stand-alone sentence. Consumers must use text-safe rendering; they must not decode
  escaped evidence into active markup. The renderer does not invent human-readable names.
- The existing 12,000-character and 500-reference output bounds remain. An oversized
  answer is withheld as `invalid_answer`, never silently truncated into an apparently
  complete answer. This limitation can affect large or heavily nested result pages.

## Cautious responses and validation

`app/answers/validation.py` retains pure functions without database/model/logging effects:

- `cautious_response` handles declines, pending or unconfirmed broad scope, missing
  evidence, zero matches, and empty pages with a nonzero total.
- `evidence_references` collects returned typed identities across all five shapes.
- `validate_selection` rejects malformed, duplicate, and unknown fact identifiers.
  Every input selection is checked against the facts rebuilt for this exact request.
- `failed_answer` distinguishes invalid-answer and model-failure messages.

Pending scope stays pending; selection cannot approve or execute anything. A declined
query supplies an appropriate explanation/clarification, not a claim that no database
records exist. Missing evidence is insufficient evidence, while zero total means no
matches within the executed filters. Empty compatible-stock states distinguish no
matching incident from no compatibility, without claiming zero stock. An empty page
with positive total is insufficient evidence for record details, not no matches.

## Development expectations

`data/evaluations/answers-1.json` adds required facts and prohibited claims for all 24
`queries-3` cases, pinned by the query-dataset digest. All five domains, canonical
examples, additional combinations, empties, and declines remain covered. The baseline,
query fixtures, frozen 2.2 protocols, and expected evidence remain unchanged.
`scripts/answer_evaluation_dataset.py` checks the dependency and exact case coverage.

Required facts are semantic expectations, not fixed wording. Their values must attach
to the correct returned records; keyword/number matching alone is insufficient. The
existing authored query evidence remains the record-level oracle. Expectations and
prohibited claims never enter model prompts. The eight grounding challenges remain
development material for the later evaluator; tests now cover non-delivery of arbitrary
prose and selected-fact validation, but the assessment runner does not yet score answers.

## Remaining committable work

1. **`feat: select answer facts with bounded model output`** — Add a versioned selection
   prompt through the existing Luna/medium integration. Accept only current fact IDs;
   reject invented values, extra prose, and invalid output. Reuse safe failures and
   bounded calls without a repair loop. Validate the selection before rendering. No
   new model selection behavior is implemented by the renderer change.
2. **`feat: connect queries to rendered answers`** — Compose query execution, selection,
   validation, and rendering through an internal interface. Preserve scope confirmation
   and correlate planning, execution, evidence, selection, and final answer without raw
   content logging. Test full-flow success and cautious/failure outcomes. HTTP/UI is 2.4.
3. **`test: verify evidence-rendered answers`** — Extend the existing evaluator to score
   selection, required facts, correct record associations, and delivered sentences.
   Separate fixed-evidence rendering tests from end-to-end planning accuracy. Freeze the
   full implementation and fresh assessment data, obtain approval before live calls,
   preserve all results, and publish limitations before completing the waypoint.

## Acceptance thresholds set before live answer testing

Apply the following separately to development and a fresh, independently reviewed
wording holdout. Freeze the final prompt, model (Luna/medium unless explicitly changed),
implementation, data, and six planned runs (three per set) before live acceptance.
Obtain approval before live calls and retain every run. No retries or additional grading
model are implicitly authorized. These targets are unchanged by deterministic rendering.

| Measure | Pilot acceptance threshold |
| --- | --- |
| Unsupported record references delivered | Zero |
| Unsupported factual claims delivered, including claims about valid records | Zero |
| Answerable cases conveying all required facts with correct record associations | At least 95% per dataset across runs |
| Correct cautious behavior for empty, insufficient, declined, or pending cases | 100% |
| Incorrect complete-result claims for partial evidence | Zero |
| Missing trace linkage or model/execution errors | Zero |

Safe fallbacks on answerable cases count against answer success. A supported case
failing every repetition fails acceptance regardless of aggregate score. Record invalid
selections withheld separately from delivered unsupported claims. Compare selected facts
and rendered values against the authored oracle and review every delivered assessment
answer for sentence meaning, scope, and associations. An unreviewed semantic claim is
not a pass. Report atomic supported/unsupported claims, required-fact coverage, case
outcomes, and withheld answers. Another model's agreement is not sole proof of truth.

## Guarantees, limitations, and verification

There is no model-prose input in the rendering path, so the former route of attaching
correct claims to false generated sentences is removed. This is narrower than proving
all possible answers correct: incorrect source data, wrong query planning, bugs in
wording or derivation rules, and output-size limits remain possible. Snapshot binding
cannot prove trustworthy query provenance. Selection currently changes order only;
conciseness, richer summarization, and new derived analytics are not introduced here.
Synthetic wording coverage cannot establish production reliability.

Tests cover all baseline outcomes, all domain fields, null/zero and equality, separate
work-order relationships, recurrence conditions and time boundaries, partial/empty
pages, state/context consistency, snapshot drift, selection tampering, literal escaping,
and oversized output. Removed free-prose and explicit-claim tests were replaced with
renderer and selection coverage; test totals therefore need not increase monotonically.
Model selection, trace integration, live answer quality, and the full semantic evaluator
remain unimplemented and unverified. Waypoint 2.3 remains in progress.

Historical verification: the contracts revision passed 1,074 tests; the explicit-claim
validation revision passed 1,143 tests, both including required PostgreSQL integration
without skips. Those results describe the superseded interfaces. No model calls or
commits were made for the renderer change.

Renderer verification: **1,133 tests passed**, including 103 answer-contract, validation,
and rendering tests plus required PostgreSQL integration, with no failures or skips
(55.39 seconds). Ruff, formatting, mypy, and whitespace checks passed. One existing
Starlette/AnyIO deprecation warning remains. The lower total reflects replacement of
obsolete prose/claim validation tests, not skipped tests. Live answer assessment and
selection/trace integration remain pending.
