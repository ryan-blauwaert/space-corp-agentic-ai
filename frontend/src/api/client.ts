import type { paths } from "./generated";

type GetPath = {
  [P in keyof paths]: paths[P] extends { get: object } ? P : never;
}[keyof paths];
type Result<P extends GetPath> = paths[P] extends {
  get: { responses: { 200: { content: { "application/json": infer R } } } };
}
  ? R
  : never;

export class ApiError extends Error {
  constructor(public status: number) {
    super(
      status === 404
        ? "This record is not available."
        : status === 422
          ? "The requested view is not valid. Return to Operations and try again."
          : "Operational data is unavailable. Please try again.",
    );
  }
}

// The route parameter ties each response type to the generated OpenAPI operation.
export async function get<P extends GetPath>(
  route: P,
  url: string,
  signal: AbortSignal,
): Promise<Result<P>> {
  void route;
  let response: Response;
  try {
    response = await fetch(`/api${url}`, { signal });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new ApiError(0);
  }
  if (!response.ok) throw new ApiError(response.status);
  try {
    return (await response.json()) as Result<P>;
  } catch {
    throw new ApiError(502);
  }
}
