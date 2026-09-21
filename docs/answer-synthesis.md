# Structured answer synthesis

Waypoint 2.3 is in progress. Typed contracts, development expectations, deterministic evidence
checks, and cautious responses exist. There is no answer generator, answer endpoint,
or live answer assessment yet. The existing query service remains unchanged.

## Approved direction: render answers from validated facts

The model will select from application-built facts; application code will render the
final sentences. Model-authored prose will not be delivered, even when accompanied by
correct citations or claims. This closes the specific route where true claims can
accompany unrelated false text, once the renderer replaces the current draft path.
It is a planned change, not a guarantee supplied by the existing validator.

Facts will be built solely from the returned evidence and its resolved scope, retaining
record identity, field meaning, and value together. The model may select supported fact
identifiers and bounded presentation choices; it may not supply replacement values,
names, explanations, sentence fragments, or arbitrary formatting instructions. The
renderer reads values from those facts and generates references itself. Evidence text
such as fault codes is displayed as a quoted/escaped value, never executed as an
instruction or incorporated as a free-standing factual sentence.

Rendering rules follow the five evidence shapes and field semantics, not Q1–Q5 question
identifiers or fixture wording. Flexible filter combinations remain supported. Counts,
null/zero distinctions, record relationships, scope, and partial-result notices remain
application-owned. Required fields and disclosure cannot be suppressed by model
selection. Selecting only some returned records must not masquerade as a complete list.
Any derived statement, such as recurrence, needs an explicit tested rule and sufficient
scope/evidence; unsupported interpretations receive a cautious response.

This deliberately trades free-form expression for stronger factual control in this
structured-data waypoint. It does not add a general templating framework, database
schema, multi-query planner, or new query capabilities. Existing evidence checks and
cautious responses will be reused where useful; the parallel free-prose delivery path
will be retired, not preserved as a fallback.

## Remaining committable work

1. **`feat: render answers from validated evidence`** — Build typed evidence facts and
   deterministic sentences for all five result shapes. Revise the answer contracts so
   model input/output selection is separate from application-rendered answer text;
   remove free-prose draft delivery. Derive identifiers and values from evidence,
   preserve null/zero, relationships, empty and partial states, and enforce mandatory
   disclosures. Replace the test that currently demonstrates accepted false prose with
   tests proving such text cannot reach the delivered answer. Cover broader combinations
   and false claims about real records without question-specific rendering branches.
2. **`feat: select answer facts with bounded model output`** — Add a versioned selection
   prompt through the existing Luna/medium integration. Accept only identifiers from the
   current request's fact set and approved presentation options. Reject unknown facts,
   invented values, extra prose, and invalid output; keep safe failures and existing
   bounded calls without a repair loop. Model selection cannot change workspace, scope,
   mandatory facts, completeness, or evidence. Validate the selection before rendering.
3. **`feat: connect queries to rendered answers`** — Compose query execution, fact
   selection, validation, and rendering through the internal interface. Preserve exact
   scope confirmation and link planning, execution, evidence, selection, and rendered
   answers through existing trace identifiers without logging raw content. Test the
   complete flow, cautious outcomes, and failure paths. HTTP/UI remains in 2.4.
4. **`test: verify evidence-rendered answers`** — Extend existing evaluation tooling to
   check selected facts, required coverage, record associations, and actual rendered
   sentences. Verify unsupported references/facts and renderer semantics separately from
   planning accuracy. Preserve thresholds below, freeze the full implementation and fresh
   assessment data, obtain approval before live calls, retain all results, and publish
   remaining limitations. Complete 2.3 only after these criteria pass.

Splitting deterministic rendering from model selection adds one reviewable commit to
what was previously the single synthesis unit. It introduces no new waypoint scope.

## Current implementation: boundary and values

`app/answers/contracts.py` defines:

- `AnswerRequest`: the original question and trusted `QueryOutcome`, including its
  resolved scope, caller context, and returned evidence. It rejects mismatched evidence
  contexts/domains and evidence attached to declined or pending-confirmation queries.
- `AnswerDraft`: untrusted natural-language text, typed record references, and explicit
  scalar evidence claims. It cannot
  set workspace, execution authority, approval, or completeness metadata.
- `AnswerResponse`: caller context, a synthesis operation identifier, and either an
  answered result with complete/partial coverage or a cautious result with a reason.
  This is application output, not a schema to accept directly from the model.

Values reuse the project's frozen, extra-field-forbidding Pydantic models. Tagged
outcomes follow [Pydantic's recommended discriminated-union approach](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions)
for predictable validation. No new framework or dependency is needed. Contract
validation proves shape and limited consistency, not provenance, authorization, valid
reference membership, or factual correctness. A typed UUID may still be invented and
true references may accompany false prose. Trusted orchestration must reconstruct and
validate values at the boundary; Python objects are not security tokens.

References distinguish facilities, units, models, components, inventory, incidents,
and work orders. Validation checks reference membership against typed returned
evidence and checks standard hyphenated/compact UUIDs embedded in prose against the
reference array. An identifier appearing in the question or query plan alone is not evidence.
Prompt instructions and citation membership cannot establish the truth of a claim.

## Required answer semantics

- Answer only from the returned evidence, interpreted within the resolved plan's scope.
  Do not fetch extra records or infer labels, causes, forecasts, or completed actions.
- A pending scope confirmation stays pending; no synthesis or implicit approval occurs.
- Declined queries return an explanation/clarification appropriate to the decline,
  not a claim that no matching database records exist.
- Missing evidence is insufficient evidence. A result with total zero is no matching
  evidence within the query scope, not proof of global absence.
- Preserve compatible-stock statuses: no matching incident is different from no
  compatibility. Missing inventory means unknown quantity, not zero.
- Application-owned coverage is complete only when the supplied page actually contains
  the whole matching result (offset zero and row count equal to total). Otherwise the
  answer must disclose partial coverage, use only supplied rows for record details,
  and may use the explicit total as a count. An empty page with nonzero total is not
  a no-results answer; it requires a cautious explanation of the page/evidence limit.
  No automatic page fetching is added by this waypoint.
- Broader filter combinations retain their own meaning. Resolved incidents are not
  unresolved, completed orders are not active, and compatibility need not require an
  incident. Do not inherit Q1–Q5 restrictions when the resolved plan does not impose them.
- Cautious reasons are `no_results`, `insufficient_evidence`, `awaiting_confirmation`,
  `declined`, `invalid_answer`, and `model_failure`. Their messages are supplied by
  application code; model failures do not masquerade as emptiness.

## Development expectations

`data/evaluations/answers-1.json` layers required facts and prohibited claims onto all
24 `queries-3` questions, pinned by the normalized query-dataset digest. The original
query fixture, baseline, frozen protocols, and expected evidence remain unchanged.
`scripts/answer_evaluation_dataset.py` checks the dependency and exact case coverage.

Required facts are semantic expectations, not verbatim answer strings. Grading must
also verify that described facts attach to the correct returned records; matching an
isolated number or keyword is insufficient. The existing authored query evidence
remains the oracle for record-level values. These expectations never enter model prompts.
The eight grounding challenges include invented identifiers and plausible false claims
about genuine records, missing stock, recurrence, causal explanations, and actions.
They are test inputs for subsequent grounding/evaluation work, not currently executed
claim-rejection tests. This dataset is development material, not a fresh holdout.

## Acceptance thresholds set before live answer testing

Apply the following separately to development and a fresh, independently reviewed
wording holdout. Freeze the final prompt, model (Luna/medium unless explicitly changed),
implementation, data, and six planned runs (three per set) before live acceptance.
Obtain approval before any live calls and retain every run. Neither retries nor an
additional grading model are implicitly authorized.

| Measure | Pilot acceptance threshold |
| --- | --- |
| Unsupported record references delivered | Zero |
| Unsupported factual claims delivered, including claims about valid records | Zero |
| Answerable cases conveying all required facts with correct record associations | At least 95% per dataset across runs |
| Correct cautious behavior for empty, insufficient, declined, or pending cases | 100% |
| Incorrect complete-result claims for partial evidence | Zero |
| Missing trace linkage or model/execution errors | Zero |

Record withheld invalid drafts separately from delivered unsupported claims. Safe
fallbacks on answerable cases count against answer success, so refusing everything
cannot pass. Any supported case failing all repetitions fails acceptance regardless
of aggregate score. Score factual claims across all prose, not just citations or
fixture-listed prohibited claims. Compare selected facts and rendered values
against the authored oracle, and review every delivered assessment answer for sentence
meaning, scope, and correct record associations. Renderer tests must verify those
semantics independently of the model; deterministic code can still contain incorrect
wording or derivation rules. An unreviewed semantic claim is not a pass. Report atomic supported/unsupported
claim counts, required-fact coverage, case outcomes, and withheld drafts. Do not use
another model's agreement as sole evidence of truth.

Evaluate synthesis against fixed authored evidence separately from end-to-end query
planning. A correct answer to the wrong query remains an end-to-end failure. Scope
review simulation must remain explicitly labeled. Fresh wording is limited synthetic
coverage, not evidence of production reliability. Rendering eliminates delivery of
model-authored prose, but cannot repair a wrong query, incorrect source data, omitted
relevant facts, or a buggy rendering rule. Publish these limits with the assessment.

## Verification and remaining work

Contract tests cover all 24 baseline outcomes, context/domain mismatches, pending and
declined state consistency, bounded text, typed/duplicate references, and output states.
Fixture tests check canonical/additional coverage, all five domains, empty/decline
expectations, challenge membership, and dependency drift.

Still required: evidence-fact rendering and contract revision, bounded model selection,
query-to-answer tracing, rendered-fact grading, and approved live assessment. The current
checks cover explicit claims and recognizable UUID references, not arbitrary prose
meaning; the approved renderer replacement is not implemented yet.
HTTP/UI integration belongs to Waypoint 2.4. No model calls were made for this change.

Verification for the contracts revision: **1,074 tests passed**, including 53 new
contract/fixture tests and required PostgreSQL integration, with no failures or skips
in the completed run. An initial sandboxed run was interrupted after database-access
setup errors; the full rerun with database access passed. Ruff, formatting, mypy, and
whitespace checks passed. One existing Starlette/AnyIO deprecation warning remains.

## Deterministic validation and cautious responses

`app/answers/validation.py` provides pure functions with no model, database, logging,
or approval side effects:

- `cautious_response` revalidates trusted input and returns application-authored messages
  for declines, pending/unconfirmed broad scope, missing evidence, no matches, and an
  empty page with nonzero total. No-incident and no-compatibility results are distinct.
- `evidence_references` collects typed identifiers from all five result shapes, including
  nested units/incidents, optional inventory, and work-order relationship IDs. Context,
  plan-only, question-only, and omitted-page identifiers are not admitted as evidence.
- `claim_matches` compares an `EvidenceClaim` to the exact scalar at its field/index
  path in the returned result JSON. Values are strict string/integer/boolean/null;
  null is not zero, booleans are not integers, and values cannot move between rows.
  Missing fields, out-of-range indices, expressions, and non-scalar values fail.
- `validate_draft` revalidates the draft, checks typed references and UUIDs in prose,
  requires at least one matching explicit claim and rejects any false one. Failure
  withholds the entire draft as `invalid_answer`. Missing claims do not silently pass.
  Coverage comes from evidence, and partial answers receive an application-owned notice.
  `failed_answer` defines separate invalid-answer and model-failure responses.

The path language is an in-memory lookup over already-returned evidence, not a query
language. It cannot access attributes, call functions, fetch records, or aggregate
new facts. This is the current explicit-claim design. The next revision replaces model
claims/prose with selection from facts whose values are supplied by application code.
The default empty claim tuple preserves contract construction, but cannot pass draft
validation. One claim is not proof of answer completeness; required-fact evaluation
remains necessary.

**Known limit:** a draft can attach true explicit claims to false prose. These checks
do not prove claim/prose correspondence, causal statements, completeness statements,
or arbitrary invented names/codes. UUID scanning covers normal hyphenated and compact
forms (case-insensitive, including braces/URN wrappers), not every possible obfuscated
identifier spelling. `answered` indicates the implemented checks passed, not semantic
certification. A regression test deliberately demonstrates this limit rather than
adding phrase-specific rejection rules. The approved renderer revision must remove this
free-prose delivery path and replace that regression with rejection/non-delivery coverage.
Fact evaluation must still review the rendered sentences. The zero-unsupported-claim
pilot target remains unchanged; the current checks have not established that target.

Tests cover success across all baseline cases, nested evidence membership, invented and
cross-workspace IDs, wrong entity types, uncited UUIDs, false values on real records,
null/zero distinctions, malformed drafts, pending scope, page boundaries, context
mismatch, and cautious failure behavior. No question-specific runtime rules were added.

Validation revision verification: **1,143 tests passed**, including 69 new validation
cases and required PostgreSQL integration, with no failures or skips (55.74 seconds).
Ruff, formatting, mypy, and whitespace checks passed. One existing Starlette/AnyIO
warning remains. Synthesis, live answer quality, and arbitrary prose grounding were
not tested because generation and semantic evaluation are not implemented in this unit.
