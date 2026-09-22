import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { postQuestion, QuestionError } from "./api/questions";
import type { QuestionResponse } from "./api/questions";
import { AnswerDetails, QueryScope } from "./QuestionDetails";

type State =
  | { phase: "idle"; notice?: string }
  | { phase: "loading"; action: "ask" | "confirm" }
  | { phase: "error"; message: string }
  | {
      phase: "result";
      data: QuestionResponse;
      question: string;
      expiresAt: number;
    };

function ScopeReview({
  data,
  expiresAt,
  onConfirm,
  onRevise,
}: {
  data: QuestionResponse;
  expiresAt: number;
  onConfirm: () => void;
  onRevise: () => void;
}) {
  const [expired, setExpired] = useState(Date.now() >= expiresAt);
  useEffect(() => {
    const timer = setTimeout(
      () => setExpired(true),
      Math.max(0, expiresAt - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [expiresAt]);
  return (
    <>
      <p className="eyebrow">SCOPE CHECK</p>
      <h2>Confirm the search area</h2>
      <p>
        This proposal can cover more than one facility. Check that every filter
        matches your question before retrieving records.
      </p>
      <p className="scope-warning">
        No evidence query has run yet. If a facility or restriction is missing,
        revise your question instead of confirming.
      </p>
      <QueryScope data={data} />
      <p role="status">
        {expired
          ? "This review has expired. Submit your question again for a fresh review."
          : "This review is temporary. Expired or previously used reviews require a new submission."}
      </p>
      <div className="question-actions">
        <button
          className="primary-button"
          disabled={expired || !data.confirmation}
          onClick={onConfirm}
        >
          Confirm scope and retrieve
        </button>
        <button onClick={onRevise}>Revise question</button>
      </div>
    </>
  );
}

export function QuestionScreen() {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<State>({ phase: "idle" });
  const active = useRef<AbortController | null>(null);
  const waitTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const input = useRef<HTMLTextAreaElement>(null);
  const result = useRef<HTMLElement>(null);
  const busy = state.phase === "loading";
  useEffect(
    () => () => {
      active.current?.abort();
      clearTimeout(waitTimer.current);
      active.current = null;
    },
    [],
  );
  useEffect(() => {
    if (state.phase === "result" || state.phase === "error")
      result.current?.focus();
  }, [state.phase]);

  function discard(notice?: string) {
    clearTimeout(waitTimer.current);
    active.current?.abort();
    active.current = null;
    setState({ phase: "idle", notice });
  }
  function revise() {
    discard();
    input.current?.focus();
  }

  async function send(action: "ask" | "confirm") {
    // The ref closes the gap before React disables the button after a rapid second click.
    if (active.current) return;
    const pending = state.phase === "result" ? state : null;
    if (
      action === "confirm" &&
      (!pending?.data.confirmation || Date.now() >= pending.expiresAt)
    ) {
      setState({
        phase: "error",
        message:
          "This review has expired. Submit the question again for a new review.",
      });
      return;
    }
    const submitted =
      action === "confirm" && pending ? pending.question : question;
    if (!submitted.trim() || submitted.length > 4000) {
      setState({
        phase: "error",
        message:
          "Enter a question between 1 and 4,000 characters, including at least one non-space character.",
      });
      input.current?.focus();
      return;
    }
    const controller = new AbortController();
    active.current = controller;
    const started = Date.now();
    setState({ phase: "loading", action });
    const timeout = setTimeout(() => {
      if (active.current !== controller) return;
      controller.abort();
      active.current = null;
      setState({
        phase: "error",
        message:
          "The service did not respond in time. It may still finish the request. Submit again when ready; any previous review cannot be reused.",
      });
    }, 120_000);
    waitTimer.current = timeout;
    try {
      const data =
        action === "ask"
          ? await postQuestion(
              "/questions",
              { question: submitted, page: { limit: 50, offset: 0 } },
              controller.signal,
            )
          : await postQuestion(
              "/questions/confirm",
              { confirmation_id: pending!.data.confirmation!.confirmation_id },
              controller.signal,
            );
      if (active.current !== controller || controller.signal.aborted) return;
      // Start expiry at submission rather than receipt: conservatively account for transit time.
      setState({
        phase: "result",
        data,
        question: submitted,
        expiresAt:
          started + (data.confirmation?.expires_in_seconds ?? 0) * 1000,
      });
    } catch (error) {
      if (active.current !== controller || controller.signal.aborted) return;
      setState({
        phase: "error",
        message:
          error instanceof QuestionError
            ? error.message
            : "The response could not be read safely. Submit the question again.",
      });
    } finally {
      clearTimeout(timeout);
      if (active.current === controller) active.current = null;
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void send("ask");
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">MISSION CONTROL / QUESTIONS</p>
          <h1>Ask the operations desk</h1>
          <p className="lede">
            Check the equipment, track the work, or take stock across the Space
            Corp network.
          </p>
        </div>
        <span className="read-only">Read only</span>
      </div>
      <form className="panel question-form" onSubmit={submit} noValidate>
        <label htmlFor="operational-question">What do you need to know?</label>
        <p id="question-help" className="scope-note">
          Ask about facilities, equipment, stock, incidents, or work orders.
          Name the facility or include a record ID when you need a specific
          scope.
        </p>
        <textarea
          id="operational-question"
          ref={input}
          value={question}
          disabled={busy}
          rows={4}
          maxLength={4000}
          aria-describedby="question-help question-length"
          placeholder="Which inventory items are below their reorder point?"
          onChange={(event) => {
            discard();
            setQuestion(event.target.value);
          }}
        />
        <div className="question-form-footer">
          <span id="question-length">
            {question.length.toLocaleString()} / 4,000 characters
          </span>
          <div className="question-actions">
            {busy && (
              <button
                type="button"
                onClick={() =>
                  discard(
                    "Stopped waiting for this response. The server may still finish the request. Any previous review must be submitted again.",
                  )
                }
              >
                Stop waiting
              </button>
            )}
            <button className="primary-button" type="submit" disabled={busy}>
              {busy
                ? state.action === "confirm"
                  ? "Retrieving records…"
                  : "Reading your question…"
                : "Submit question"}
            </button>
          </div>
        </div>
        <p className="question-hint">
          Each submission is a new question. Browsing a facility does not
          automatically limit this search.
        </p>
      </form>
      {state.phase === "idle" && state.notice && (
        <p role="status" className="notice">
          {state.notice}
        </p>
      )}
      {busy && (
        <p className="notice" role="status">
          {state.action === "confirm"
            ? "Retrieving the records you approved…"
            : "Interpreting your question and checking its scope…"}
        </p>
      )}
      {state.phase === "error" && (
        <section
          ref={result}
          tabIndex={-1}
          className="panel question-result"
          aria-label="Question error"
        >
          <div role="alert">
            <h2>Unable to complete the request</h2>
            <p>{state.message}</p>
          </div>
          <button onClick={revise}>Edit question</button>
        </section>
      )}
      {state.phase === "result" && (
        <section
          ref={result}
          tabIndex={-1}
          className="panel question-result"
          aria-label="Question result"
        >
          <p className="submitted-question">
            <strong>Your question</strong>
            {state.question}
          </p>
          {state.data.scope_status === "awaiting_confirmation" ? (
            <ScopeReview
              data={state.data}
              expiresAt={state.expiresAt}
              onConfirm={() => void send("confirm")}
              onRevise={revise}
            />
          ) : (
            <AnswerDetails data={state.data} />
          )}
        </section>
      )}
    </>
  );
}
