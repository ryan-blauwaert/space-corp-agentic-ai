import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuestionScreen } from "./QuestionScreen";
import { AnswerDetails, QueryScope } from "./QuestionDetails";
import type { QuestionResponse } from "./api/questions";

const plan: QuestionResponse["plan"] = {
  operation: "inventory",
  facility: { facility_id: null, facility_type: null, location: null },
  component_id: null,
  compatible_model_id: null,
  quantity: { operator: "lte", value: 2 },
  below_reorder_point: true,
};
const answered: QuestionResponse = {
  request_id: "request",
  query_operation_id: "query",
  synthesis_operation_id: "answer",
  plan,
  scope_status: "confirmed",
  page: { limit: 50, offset: 0 },
  confirmation: null,
  outcome: {
    status: "answered",
    coverage: "complete",
    answer: {
      text: "Recorded stock is 0. One inventory item was returned within the approved scope.",
      references: [{ entity: "inventory", record_id: "inventory-1" }],
    },
  },
  evidence: {
    operation: "inventory",
    page: {
      limit: 50,
      offset: 0,
      total: 1,
      rows: [
        {
          inventory_id: "inventory-1",
          facility_id: "facility-1",
          component_id: "component-1",
          quantity_on_hand: 0,
          reorder_point: 2,
          shortfall: 2,
        },
      ],
    },
  },
};
const pending: QuestionResponse = {
  ...answered,
  scope_status: "awaiting_confirmation",
  evidence: null,
  confirmation: { confirmation_id: "private-handle", expires_in_seconds: 300 },
  outcome: {
    status: "cautious",
    reason: "awaiting_confirmation",
    text: "Review the proposed scope.",
  },
};
const reply = (value: unknown, status = 200) => ({
  ok: status === 200,
  status,
  json: async () => value,
});
function setup(fetcher = vi.fn().mockResolvedValue(reply(answered))) {
  vi.stubGlobal("fetch", fetcher);
  const view = render(<QuestionScreen />);
  return { ...view, fetcher, user: userEvent.setup() };
}
async function ask(
  user: ReturnType<typeof userEvent.setup>,
  text = "Show stock below reorder point.",
) {
  await user.type(screen.getByRole("textbox"), text);
  await user.click(screen.getByRole("button", { name: "Submit question" }));
}
afterEach(() => vi.useRealTimers());

describe("question journey", () => {
  it("makes no request on mount and validates blank input", async () => {
    const { user, fetcher } = setup();
    expect(fetcher).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "between 1 and 4,000",
    );
    expect(fetcher).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toHaveAttribute("maxlength", "4000");
  });
  it("sends only the question and bounded page; preserves answer and supporting records", async () => {
    const { user, fetcher } = setup();
    await ask(user);
    expect(
      await screen.findByRole("heading", { name: "Mission briefing" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Recorded stock is 0. One inventory item was returned within the approved scope.",
      ),
    ).toBeInTheDocument();
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      question: "Show stock below reorder point.",
      page: { limit: 50, offset: 0 },
    });
    expect(fetcher.mock.calls[0][0]).toBe("/api/questions");
    await user.click(screen.getByText("Supporting records · 1 returned of 1"));
    expect(screen.getByText("Shortfall")).toBeInTheDocument();
    expect(screen.getByText("Quantity on hand")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("requires explicit scope approval and sends only its handle", async () => {
    const { user, fetcher } = setup(
      vi
        .fn()
        .mockResolvedValueOnce(reply(pending))
        .mockResolvedValueOnce(reply(answered)),
    );
    await ask(user);
    expect(
      await screen.findByRole("heading", { name: "Confirm the search area" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Less than or equal to")).toBeInTheDocument();
    expect(screen.getByText("Quantity threshold")).toBeInTheDocument();
    expect(screen.getByText("Below reorder point")).toBeInTheDocument();
    expect(screen.getAllByText("No restriction")).toHaveLength(5);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(document.body).not.toHaveTextContent("private-handle");
    await user.click(
      screen.getByRole("button", { name: "Confirm scope and retrieve" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Mission briefing" }),
    ).toBeInTheDocument();
    expect(fetcher.mock.calls[1][0]).toBe("/api/questions/confirm");
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({
      confirmation_id: "private-handle",
    });
    expect(
      screen.queryByRole("button", { name: "Confirm scope and retrieve" }),
    ).not.toBeInTheDocument();
  });
  it("discards pending review when editing and requires a new submission", async () => {
    const { user, fetcher } = setup(vi.fn().mockResolvedValue(reply(pending)));
    await ask(user);
    await screen.findByRole("heading", { name: "Confirm the search area" });
    await user.type(screen.getByRole("textbox"), " at Selene");
    expect(
      screen.queryByText("Confirm the search area"),
    ).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Submit question" }));
    await screen.findByRole("heading", { name: "Confirm the search area" });
    await user.click(screen.getByRole("button", { name: "Revise question" }));
    expect(screen.getByRole("textbox")).toHaveFocus();
    expect(
      screen.queryByText("Confirm the search area"),
    ).not.toBeInTheDocument();
    expect(fetcher.mock.calls.every(([url]) => url === "/api/questions")).toBe(
      true,
    );
  });
  it("expires review locally without a confirmation request", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValue(
      reply({
        ...pending,
        confirmation: { ...pending.confirmation, expires_in_seconds: 1 },
      }),
    );
    setup(fetcher);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Stock" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Submit question" }));
    });
    expect(
      screen.getByRole("button", { name: "Confirm scope and retrieve" }),
    ).toBeEnabled();
    act(() => vi.advanceTimersByTime(1001));
    expect(
      screen.getByRole("button", { name: "Confirm scope and retrieve" }),
    ).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("review has expired");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each([404, 503, 504, 500])(
    "discards a failed confirmation (%s), with no automatic replay",
    async (status) => {
      const { user, fetcher } = setup(
        vi
          .fn()
          .mockResolvedValueOnce(reply(pending))
          .mockResolvedValueOnce(reply({ detail: "SECRET" }, status)),
      );
      await ask(user);
      await screen.findByText("Confirm the search area");
      await user.click(
        screen.getByRole("button", { name: "Confirm scope and retrieve" }),
      );
      const alert = await screen.findByRole("alert");
      expect(alert.textContent?.toLowerCase()).toContain("submit");
      expect(alert).not.toHaveTextContent("SECRET");
      expect(
        screen.queryByText("Confirm scope and retrieve"),
      ).not.toBeInTheDocument();
      expect(fetcher).toHaveBeenCalledTimes(2);
    },
  );
  it.each([400, 404, 422, 500, 502, 503, 504])(
    "shows a safe request failure for HTTP %s",
    async (status) => {
      const { user } = setup(
        vi.fn().mockResolvedValue(reply({ detail: "SECRET SQL" }, status)),
      );
      await ask(user);
      expect(await screen.findByRole("alert")).not.toHaveTextContent(
        "SECRET SQL",
      );
      expect(screen.queryByText("No matching records")).not.toBeInTheDocument();
    },
  );
  it("handles network errors without raw exception text", async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error("PRIVATE")));
    await ask(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not reach",
    );
    expect(document.body).not.toHaveTextContent("PRIVATE");
  });
  it("prevents duplicate sends and ignores a dismissed response arriving after a new answer", async () => {
    let complete!: (value: unknown) => void;
    const old = new Promise((resolve) => {
      complete = resolve;
    });
    const { user, fetcher } = setup(
      vi.fn().mockReturnValueOnce(old).mockResolvedValueOnce(reply(answered)),
    );
    await ask(user);
    expect(screen.getByRole("textbox")).toBeDisabled();
    fireEvent.submit(screen.getByRole("textbox").closest("form")!);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent("Interpreting");
    await user.click(screen.getByRole("button", { name: "Stop waiting" }));
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
    await user.click(screen.getByRole("button", { name: "Submit question" }));
    await screen.findByText("Mission briefing");
    await act(async () => complete(reply(pending)));
    expect(
      screen.queryByText("Confirm the search area"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Mission briefing")).toBeInTheDocument();
  });
  it("does not duplicate confirmation while it is in flight", async () => {
    const { user, fetcher } = setup(
      vi
        .fn()
        .mockResolvedValueOnce(reply(pending))
        .mockReturnValueOnce(new Promise(() => {})),
    );
    await ask(user);
    await screen.findByText("Confirm the search area");
    await user.dblClick(
      screen.getByRole("button", { name: "Confirm scope and retrieve" }),
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent("Retrieving");
  });
  it("aborts an active request when leaving the screen", async () => {
    const { user, fetcher, unmount } = setup(
      vi.fn().mockReturnValue(new Promise(() => {})),
    );
    await ask(user);
    unmount();
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
  });
  it("bounds waiting and does not retry on timeout", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockReturnValue(new Promise(() => {}));
    setup(fetcher);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Stock" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit question" }));
    act(() => vi.advanceTimersByTime(120_000));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "did not respond in time",
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
  });
});

it("supports keyboard submission and explicit keyboard confirmation", async () => {
  const { user, fetcher } = setup(
    vi
      .fn()
      .mockResolvedValueOnce(reply(pending))
      .mockResolvedValueOnce(reply(answered)),
  );
  await user.click(screen.getByRole("textbox"));
  await user.keyboard("Inventory below reorder point");
  await user.tab();
  expect(screen.getByRole("button", { name: "Submit question" })).toHaveFocus();
  await user.keyboard("{Enter}");
  await screen.findByRole("heading", { name: "Confirm the search area" });
  await user.tab();
  expect(
    screen.getByRole("button", { name: "Confirm scope and retrieve" }),
  ).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(
    await screen.findByRole("heading", { name: "Mission briefing" }),
  ).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("handles a non-JSON response as a safe failure", async () => {
  const { user } = setup(
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error("PRIVATE HTML");
      },
    }),
  );
  await ask(user);
  expect(await screen.findByRole("alert")).not.toHaveTextContent(
    "PRIVATE HTML",
  );
});

describe("faithful answer presentation", () => {
  it.each([
    "no_results",
    "insufficient_evidence",
    "declined",
    "invalid_answer",
    "model_failure",
  ] as const)("preserves cautious %s wording", (reason) => {
    render(
      <AnswerDetails
        data={{
          ...answered,
          evidence: null,
          outcome: {
            status: "cautious",
            reason,
            text: `Backend explanation: ${reason}`,
          },
        }}
      />,
    );
    expect(
      screen.getByText(`Backend explanation: ${reason}`),
    ).toBeInTheDocument();
    expect(screen.queryByText("Complete result")).not.toBeInTheDocument();
  });
  it("keeps partial coverage and does not fetch other pages", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    if (answered.evidence?.operation !== "inventory")
      throw new Error("Inventory fixture required");
    render(
      <AnswerDetails
        data={{
          ...answered,
          outcome: {
            status: "answered",
            coverage: "partial",
            answer: { text: "Only 1 of 5 records is shown.", references: [] },
          },
          evidence: {
            ...answered.evidence!,
            page: { ...answered.evidence!.page, total: 5 },
          },
        }}
      />,
    );
    expect(screen.getByText("Partial results")).toBeInTheDocument();
    expect(
      screen.getByText("Only 1 of 5 records is shown."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Supporting records · 1 returned of 5"),
    ).toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("renders answer and evidence text literally, without executing markup", () => {
    const text = "<img src=x onerror=alert(1)> **invented markup**";
    const { container } = render(
      <AnswerDetails
        data={{
          ...answered,
          outcome: {
            status: "answered",
            coverage: "complete",
            answer: { text, references: [] },
          },
          evidence: {
            operation: "incidents",
            count: 1,
            page: {
              limit: 50,
              offset: 0,
              total: 1,
              rows: [
                {
                  incident_id: "i",
                  facility_id: "f",
                  unit_id: null,
                  status: "open",
                  severity: "low",
                  fault_code: text,
                  occurred_at: "2026-09-22T00:00:00Z",
                },
              ],
            },
          },
        }}
      />,
    );
    expect(screen.getAllByText(text)).toHaveLength(2);
    expect(container.querySelector("img")).toBeNull();
  });
  it("shows exact timestamps, false filters, entity IDs, and pagination during review", () => {
    render(
      <QueryScope
        data={{
          ...pending,
          page: { limit: 10, offset: 20 },
          plan: {
            operation: "work_orders",
            facility: {
              facility_id: "facility-id",
              facility_type: null,
              location: "Mare Imbrium",
            },
            statuses: ["open", "blocked"],
            priorities: null,
            target_equipment_unit_id: "target-id",
            originating_incident_id: null,
            as_of: "2026-09-22T00:00:00Z",
            overdue: false,
          },
        }}
      />,
    );
    expect(screen.getByText("2026-09-22T00:00:00Z")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
    expect(screen.getByText("Any of: open, blocked")).toBeInTheDocument();
    expect(screen.getByText("target-id")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
  });
  it("distinguishes compatibility with unknown inventory from zero stock", () => {
    render(
      <AnswerDetails
        data={{
          ...answered,
          evidence: {
            operation: "compatible_stock",
            status: "matched",
            incident_ids: ["incident-a"],
            incident_codes: ["INC-A"],
            page: {
              limit: 50,
              offset: 0,
              total: 2,
              rows: [
                {
                  model_id: "model",
                  component_id: "first",
                  inventory_id: null,
                  quantity_on_hand: null,
                },
                {
                  model_id: "model",
                  component_id: "second",
                  inventory_id: "inventory",
                  quantity_on_hand: 0,
                },
              ],
            },
          },
        }}
      />,
    );
    expect(screen.getByText("incident-a")).toBeInTheDocument();
    expect(screen.getAllByText("Not recorded / unknown")).toHaveLength(2);
    expect(screen.getByText("0")).toBeInTheDocument();
  });
  it("retains nested equipment/incident evidence and separate work-order relationships", () => {
    const { rerender } = render(
      <AnswerDetails
        data={{
          ...answered,
          evidence: {
            operation: "facility_equipment",
            page: {
              limit: 50,
              offset: 0,
              total: 1,
              rows: [
                {
                  facility_id: "f",
                  units: [{ unit_id: "unit-a", operational_status: "offline" }],
                  incidents: [
                    {
                      incident_id: "incident-a",
                      equipment_unit_id: "unit-a",
                      status: "open",
                    },
                  ],
                },
              ],
            },
          },
        }}
      />,
    );
    expect(screen.getByText("incident-a")).toBeInTheDocument();
    expect(screen.getAllByText("unit-a")).toHaveLength(2);
    rerender(
      <AnswerDetails
        data={{
          ...answered,
          evidence: {
            operation: "work_orders",
            page: {
              limit: 50,
              offset: 0,
              total: 1,
              rows: [
                {
                  work_order_id: "work",
                  facility_id: "f",
                  status: "blocked",
                  priority: "high",
                  due_at: null,
                  overdue: false,
                  blocked: true,
                  originating_incident_id: "incident-a",
                  incident_equipment_unit_id: "affected-unit",
                  target_equipment_unit_id: "target-unit",
                },
              ],
            },
          },
        }}
      />,
    );
    expect(screen.getByText("Incident-affected unit ID")).toBeInTheDocument();
    expect(screen.getByText("affected-unit")).toBeInTheDocument();
    expect(screen.getByText("Direct work target unit ID")).toBeInTheDocument();
    expect(screen.getByText("target-unit")).toBeInTheDocument();
  });
});
