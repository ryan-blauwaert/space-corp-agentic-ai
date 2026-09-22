import type { components, paths } from "./generated";

export type QuestionResponse = components["schemas"]["QuestionResponse"];
type QuestionPath = "/questions" | "/questions/confirm";
type Body<P extends QuestionPath> =
  paths[P]["post"]["requestBody"]["content"]["application/json"];

export class QuestionError extends Error {
  constructor(
    public status: number,
    confirmation: boolean,
  ) {
    const messages: Record<number, string> = {
      0: "Mission control could not reach the service. Check your connection and submit again.",
      400: "That question exceeds the query limits. Try a narrower scope.",
      404: confirmation
        ? "This review has expired or is no longer available. Submit the question again for a new review."
        : "A referenced record is not available. Check the question and submit again.",
      422: "The question could not be accepted. Check your input and submit again.",
      502: "The service could not interpret that question safely. Try rephrasing it.",
      503: "The question service is unavailable. Please try again later.",
      504: "The query took too long. Try a narrower question.",
    };
    super(
      (messages[status] ??
        "The question could not be completed. Please submit again.") +
        (confirmation && status !== 404
          ? " This review cannot be reused; submit again for a new review."
          : ""),
    );
  }
}

export async function postQuestion<P extends QuestionPath>(
  path: P,
  body: Body<P>,
  signal: AbortSignal,
): Promise<QuestionResponse> {
  const confirming = path === "/questions/confirm";
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new QuestionError(0, confirming);
  }
  if (!response.ok) throw new QuestionError(response.status, confirming);
  try {
    return (await response.json()) as QuestionResponse;
  } catch {
    throw new QuestionError(502, confirming);
  }
}
