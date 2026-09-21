# Structured answer synthesis

Waypoint 2.3 is in progress. Only typed contracts and development expectations exist;
there is no answer generator, grounding validator, answer endpoint, or live answer
assessment yet. The existing query service remains unchanged.

## Boundary and values

`app/answers/contracts.py` defines:

- `AnswerRequest`: the original question and trusted `QueryOutcome`, including its
  resolved scope, caller context, and returned evidence. It rejects mismatched evidence
  contexts/domains and evidence attached to declined or pending-confirmation queries.
- `AnswerDraft`: untrusted natural-language text and typed record references. It cannot
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
and work orders. Later validation must check every delivered identifier against typed
returned evidence, including identifiers embedded in prose, not just the references
array. An identifier appearing in the question or query plan alone is not evidence.
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
  `declined`, `invalid_answer`, and `model_failure`. Their messages will be supplied by
  application behavior in subsequent work; model failures must not masquerade as emptiness.

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
fixture-listed prohibited claims. Initially use deterministic comparison where facts
are explicit plus a documented human review of every delivered answer for remaining
semantic claims; an unreviewed claim is not a pass. Report atomic supported/unsupported
claim counts, required-fact coverage, case outcomes, and withheld drafts. Do not use
another model's agreement as sole evidence of truth.

Evaluate synthesis against fixed authored evidence separately from end-to-end query
planning. A correct answer to the wrong query remains an end-to-end failure. Scope
review simulation must remain explicitly labeled. Fresh wording is limited synthetic
coverage, not evidence of production reliability. Passing samples cannot guarantee that
future prose contains no hallucinations; publish limitations with the final assessment.

## Verification and remaining work

Contract tests cover all 24 baseline outcomes, context/domain mismatches, pending and
declined state consistency, bounded text, typed/duplicate references, and output states.
Fixture tests check canonical/additional coverage, all five domains, empty/decline
expectations, challenge membership, and dependency drift.

Still required: runtime identifier/fact checks, deterministic cautious messages,
synthesis prompting and bounded invocation, query-to-answer tracing, partial-page
behavior tests, adversarial rejection tests, actual fact grading, and approved live
assessment. The contracts alone satisfy none of the runtime grounding completion gates.
HTTP/UI integration belongs to Waypoint 2.4. No model calls were made for this change.

Verification for the contracts revision: **1,074 tests passed**, including 53 new
contract/fixture tests and required PostgreSQL integration, with no failures or skips
in the completed run. An initial sandboxed run was interrupted after database-access
setup errors; the full rerun with database access passed. Ruff, formatting, mypy, and
whitespace checks passed. One existing Starlette/AnyIO deprecation warning remains.
