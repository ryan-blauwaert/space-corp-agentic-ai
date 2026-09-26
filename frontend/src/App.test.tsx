import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import { App } from "./App";

const facility = {
  id: "abc",
  name: "Selene Base",
  code: "SEL",
  location: "Moon",
  facility_type: "lunar_installation",
  operational_status: "operational",
};
const page = (items: unknown[], offset = 0, total = items.length) => ({
  items,
  pagination: { limit: 10, offset, total },
});
const response = (data: unknown, status = 200) => ({
  ok: status === 200,
  status,
  json: async () => data,
});
function setup(
  route = "/",
  fetcher = vi.fn().mockResolvedValue(response(page([facility]))),
) {
  vi.stubGlobal("fetch", fetcher);
  render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
  return { fetcher, user: userEvent.setup() };
}
describe("operational context", () => {
  it("shows loading, API facilities, selected facility and scoped equipment", async () => {
    const fetcher = vi.fn(async (url: string) =>
      response(
        url.includes("equipment-units")
          ? page([
              {
                id: "unit-1",
                asset_tag: "THERM-01",
                operational_status: "degraded",
              },
            ])
          : url === "/api/facilities/abc"
            ? facility
            : page([facility]),
      ),
    );
    const { user } = setup("/", fetcher);
    expect(screen.getByText("Loading facilities…")).toBeInTheDocument();
    await user.click(await screen.findByRole("link", { name: /Selene Base/ }));
    expect(
      await screen.findByRole("heading", { name: "Selene Base" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("THERM-01")).toBeInTheDocument();
    expect(
      fetcher.mock.calls.some(
        ([url]) =>
          url === "/api/equipment-units?facility_id=abc&limit=10&offset=0",
      ),
    ).toBe(true);
    await user.click(screen.getByRole("link", { name: "All facilities" }));
    expect(
      await screen.findByRole("heading", { name: "Mission control" }),
    ).toBeInTheDocument();
  });
  it("paginates using API totals and restores the previous page", async () => {
    const { user, fetcher } = setup(
      "/",
      vi.fn(async (url: string) =>
        response(page([facility], url.includes("offset=10") ? 10 : 0, 11)),
      ),
    );
    await screen.findByText("Selene Base");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Next" })).toBeDisabled(),
    );
    expect(fetcher.mock.calls.some(([url]) => url.includes("offset=10"))).toBe(
      true,
    );
    await user.click(screen.getByRole("button", { name: "Previous" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled(),
    );
  });
  it("shows an empty workspace", async () => {
    setup("/", vi.fn().mockResolvedValue(response(page([]))));
    expect(
      await screen.findByText("No facilities are available in this workspace."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
  it.each([404, 422, 503])(
    "handles status %s safely and retries",
    async (status) => {
      const fetcher = vi
        .fn()
        .mockResolvedValueOnce(
          response({ detail: "PRIVATE DATABASE ERROR" }, status),
        )
        .mockResolvedValue(response(page([facility])));
      const { user } = setup("/", fetcher);
      expect(await screen.findByRole("alert")).not.toHaveTextContent("PRIVATE");
      await user.click(screen.getByRole("button", { name: "Try again" }));
      expect(await screen.findByText("Selene Base")).toBeInTheDocument();
    },
  );
  it("handles network failures safely", async () => {
    setup("/", vi.fn().mockRejectedValue(new Error("SECRET NETWORK DETAILS")));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Operational data is unavailable",
    );
    expect(screen.queryByText(/SECRET/)).not.toBeInTheDocument();
  });
  it("rejects invalid pagination without a request", () => {
    const { fetcher } = setup("/?offset=-1");
    expect(
      screen.getByRole("heading", { name: "Invalid page" }),
    ).toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("offers keyboard navigation and opens Ask without making model calls", async () => {
    const { user, fetcher } = setup();
    await screen.findByText("Selene Base");
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();
    await user.click(screen.getByRole("link", { name: /Ask a question/ }));
    expect(
      screen.getByRole("heading", { name: "Ask the operations desk" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveFocus();
    expect(
      fetcher.mock.calls.every(([url]) => !String(url).includes("questions")),
    ).toBe(true);
  });
  it("does not fetch equipment for a missing facility", async () => {
    const { fetcher } = setup(
      "/facilities/missing",
      vi.fn().mockResolvedValue(response({}, 404)),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This record is not available",
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("shows empty equipment and preserves facility context", async () => {
    setup(
      "/facilities/abc",
      vi.fn(async (url: string) =>
        response(url.includes("equipment-units") ? page([]) : facility),
      ),
    );
    expect(
      await screen.findByText("No equipment is recorded at this facility."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Selene Base" }),
    ).toBeInTheDocument();
  });
  it("aborts obsolete requests on navigation", async () => {
    let signal: AbortSignal | undefined;
    const fetcher = vi.fn((_url: string, options: RequestInit) => {
      signal = options.signal as AbortSignal;
      return new Promise(() => {});
    });
    const { user } = setup("/", fetcher);
    await user.click(screen.getByRole("link", { name: /Ask a question/ }));
    expect(signal?.aborted).toBe(true);
  });
});

it.each([
  ["Earth’s Moon", "Mare Imbrium", "Earth’s Moon · Mare Imbrium"],
  ["Earth–Moon system", "Earth-Moon L1", "Earth–Moon system · L1"],
  [null, "Unknown region", "Unknown region"],
])(
  "shows recorded body/system context with the location",
  async (body, location, expected) => {
    setup(
      "/",
      vi
        .fn()
        .mockResolvedValue(
          response(page([{ ...facility, body_or_system: body, location }])),
        ),
    );
    expect(await screen.findByText(expected)).toBeInTheDocument();
  },
);
