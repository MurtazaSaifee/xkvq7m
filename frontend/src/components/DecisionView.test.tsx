import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DecisionSnapshot } from "../api/client";
import { DecisionView } from "./DecisionView";

// The chart needs a canvas, which jsdom does not provide. Its option is tested separately.
vi.mock("./DecisionChart", () => ({ DecisionChart: () => null }));

const META = {
  ingested_at: "2026-10-25T04:45:25Z",
  forecasts: {
    first_target_time: "2025-12-17T21:00:00Z",
    last_target_time: "2026-02-03T21:00:00Z",
    row_count: 21343,
  },
  actuals: {
    first_target_time: "2025-12-19T00:00:00Z",
    last_target_time: "2026-01-31T23:30:00Z",
    row_count: 2160,
  },
  excluded_forecasts: 5521,
  delivery_days: { first: "2026-01-02", last: "2026-02-01" },
};

function snapshotFor(deliveryDay: string, overrides: Partial<DecisionSnapshot> = {}): DecisionSnapshot {
  return {
    delivery_day: deliveryDay,
    decision_day: "2026-01-31",
    cutoff: "09:20",
    cutoff_time: "2026-01-31T09:20:00Z",
    forecast_run_publish_time: "2026-01-31T07:30:00Z",
    hours: [],
    actuals: [],
    kpis: {
      forecast_mwh: 438696,
      actual_mwh: 364058,
      error_mwh: 74638,
      paired_hours: 24,
      missing_forecast_hours: 0,
      missing_actual_hours: 0,
    },
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Routes the two API paths. The snapshot handler receives the requested delivery day. */
function stubApi(handlers: {
  snapshot: (deliveryDay: string | null) => Response;
}) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    if (url.pathname === "/api/v1/meta") {
      return Promise.resolve(jsonResponse(META));
    }
    if (url.pathname === "/api/v1/decision-snapshot") {
      return Promise.resolve(handlers.snapshot(url.searchParams.get("delivery_day")));
    }
    return Promise.reject(new Error(`unexpected request to ${url.pathname}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderView() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DecisionView />
    </QueryClientProvider>,
  );
}

describe("DecisionView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens on the latest delivery day and says what the trader is looking at", async () => {
    const fetchMock = stubApi({
      snapshot: (day) => jsonResponse(snapshotFor(day ?? "")),
    });

    renderView();

    expect(
      await screen.findByRole("heading", {
        name: "Wind outlook for 1 Feb as known at 09:20 on 31 Jan (07:30 run)",
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Delivery day")).toHaveValue("2026-02-01");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/decision-snapshot?delivery_day=2026-02-01&cutoff=09%3A20",
      expect.anything(),
    );
    expect(screen.getByRole("group", { name: "Forecast error" })).toHaveTextContent(
      "+74,638 MWh",
    );
  });

  it("loads the snapshot for another delivery day when the picker changes", async () => {
    const fetchMock = stubApi({
      snapshot: (day) => jsonResponse(snapshotFor(day ?? "")),
    });
    renderView();
    await screen.findByRole("heading", { name: /Wind outlook for 1 Feb/ });

    fireEvent.change(screen.getByLabelText("Delivery day"), {
      target: { value: "2026-01-15" },
    });

    expect(
      await screen.findByRole("heading", { name: /Wind outlook for 15 Jan/ }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/decision-snapshot?delivery_day=2026-01-15&cutoff=09%3A20",
      expect.anything(),
    );
  });

  it("shows the problem detail when the snapshot cannot be loaded", async () => {
    stubApi({
      snapshot: () =>
        jsonResponse(
          {
            type: "about:blank",
            title: "Service Unavailable",
            status: 503,
            detail: "Data snapshot is not available",
          },
          503,
        ),
    });

    renderView();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Could not load the decision snapshot: Data snapshot is not available",
    );
  });

  it("says when no forecast was published before the cutoff", async () => {
    stubApi({
      snapshot: (day) =>
        jsonResponse(
          snapshotFor(day ?? "", {
            forecast_run_publish_time: null,
            kpis: {
              forecast_mwh: null,
              actual_mwh: null,
              error_mwh: null,
              paired_hours: 0,
              missing_forecast_hours: 24,
              missing_actual_hours: 24,
            },
          }),
        ),
    });

    renderView();

    expect(
      await screen.findByRole("heading", {
        name: "Wind outlook for 1 Feb as known at 09:20 on 31 Jan (no forecast run before the cutoff)",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No forecast was published before the cutoff, so there is nothing to compare."),
    ).toBeVisible();
    const error = screen.getByRole("group", { name: "Forecast error" });
    expect(within(error).getByText("—")).toBeInTheDocument();
  });
});
