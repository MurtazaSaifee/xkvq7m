import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AccuracyResponse, MetaResponse } from "../api/client";
import { CUTOFF_PRESETS } from "../decision/cutoffs";
import { DecisionCutoffProvider } from "./DecisionCutoffProvider";
import { MethodologyView } from "./MethodologyView";

const ACCURACY: AccuracyResponse = {
  cutoff: "09:20",
  delivery_days: { first: "2026-01-02", last: "2026-02-01" },
  summary: {
    target_hours: 744,
    measured_hours: 742,
    excluded_no_decision_forecast: 0,
    excluded_no_actual: 2,
    mae_mw: 2038.9,
    bias_mw: 1747.9,
    rmse_mw: 2504.8,
    p90_abs_error_mw: 4097.9,
    mean_actual_mw: 11283.6,
    nmae_percent: 18.07,
  },
  histogram: { bin_width_mw: 500, bins: [] },
  band_coverage: {
    lookback_days: 14,
    min_history_days: 7,
    counted_hours: 744,
    inside_hours: 597,
    coverage_percent: 80.24,
    excluded_no_band: 0,
    excluded_no_decision_forecast: 0,
    excluded_no_actual: 0,
  },
  heatmap: { cells: [] },
  worst_days: [],
  horizon_curve: {
    buckets: [],
    excluded_no_actual: 2,
    decision_horizon_range_hours: { min_hours: 16.5, max_hours: 39.5 },
  },
  alignment_sensitivity: {
    hourly_mean: {
      measured_hours: 742,
      mae_mw: 2038.9,
      bias_mw: 1747.9,
      rmse_mw: 2504.8,
      p90_abs_error_mw: 4097.9,
      nmae_percent: 18.07,
    },
    top_of_hour: {
      measured_hours: 742,
      mae_mw: 2022.5,
      bias_mw: 1745.9,
      rmse_mw: 2497.4,
      p90_abs_error_mw: 4150,
      nmae_percent: 17.9,
    },
  },
};

const META: MetaResponse = {
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

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Answers the accuracy and meta requests of the view, and rejects anything else. */
function stubApi(respondAccuracy: () => Response) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    if (url.pathname === "/api/v1/accuracy") {
      return Promise.resolve(respondAccuracy());
    }
    if (url.pathname === "/api/v1/meta") {
      return Promise.resolve(jsonResponse(META));
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
      <DecisionCutoffProvider>
        <MethodologyView />
      </DecisionCutoffProvider>
    </QueryClientProvider>,
  );
}

describe("MethodologyView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it("states the scope: decisions for 2 Jan to 1 Feb 2026, with December used only as warm-up", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    expect(
      await screen.findByText(/headline metrics cover only the delivery days 2 Jan to 1 Feb 2026/),
    ).toBeVisible();
    expect(screen.getByText(/December 2025 data is used only as band warm-up/)).toBeVisible();
    expect(
      screen.getByText(/includes forecasts published after the cutoff, to show what waiting would buy/),
    ).toBeVisible();
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("takes the delivery days from the snapshot metadata, not from fixed copy", async () => {
    const shiftedMeta = { ...META, delivery_days: { first: "2026-03-01", last: "2026-03-31" } };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = new URL(String(input), "http://localhost");
        if (url.pathname === "/api/v1/meta") {
          return Promise.resolve(jsonResponse(shiftedMeta));
        }
        return Promise.resolve(jsonResponse(ACCURACY));
      }),
    );

    renderView();

    expect(
      await screen.findByText(/headline metrics cover only the delivery days 1 Mar to 31 Mar 2026/),
    ).toBeVisible();
    expect(screen.queryByText(/2 Jan to 1 Feb 2026/)).not.toBeInTheDocument();
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("lists the cutoff presets in the picker's order, with the 09:20 default first", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    const presets = screen.getByRole("list", { name: "Cutoff presets" });
    const labels = within(presets)
      .getAllByRole("listitem")
      .map((item) => item.textContent);
    expect(labels).toEqual(CUTOFF_PRESETS.map((preset) => preset.label));
    expect(labels[0]).toBe("EPEX 09:20 (default)");
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("explains each metric and says why MAPE is not shown", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    const metrics = screen.getByLabelText("Metric definitions");
    expect(within(metrics).getByText("Forecast error")).toBeVisible();
    expect(within(metrics).getByText("Average miss (MAE)")).toBeVisible();
    expect(within(metrics).getByText("Bias")).toBeVisible();
    expect(within(metrics).getByText("Large misses (RMSE)")).toBeVisible();
    expect(within(metrics).getByText("Nine-in-ten miss (P90)")).toBeVisible();
    expect(within(metrics).getByText("Relative miss (nMAE)")).toBeVisible();
    expect(screen.getByText(/MAPE is not shown/)).toBeVisible();
    expect(screen.getByText(/divides each miss by the actual generation/)).toBeVisible();
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("describes the band from the rules the API applies: 14 delivery days ending D-2, at least 7", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    expect(
      await screen.findByText(/14 delivery days that end two days before it \(D-15 to D-2\)/),
    ).toBeVisible();
    expect(screen.getByText(/the P10 and P90/)).toBeVisible();
    expect(screen.getByText(/fewer than 7 days with errors/)).toBeVisible();
    expect(screen.getByText(/The target is about 80%/)).toBeVisible();
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("takes the band lookback and minimum history from the accuracy response, not from fixed copy", async () => {
    const accuracy = {
      ...ACCURACY,
      band_coverage: { ...ACCURACY.band_coverage, lookback_days: 10, min_history_days: 5 },
    };
    stubApi(() => jsonResponse(accuracy));

    renderView();

    expect(
      await screen.findByText(/10 delivery days that end two days before it \(D-11 to D-2\)/),
    ).toBeVisible();
    expect(screen.getByText(/fewer than 5 days with errors/)).toBeVisible();
    expect(screen.queryByText(/fewer than 7 days/)).not.toBeInTheDocument();
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("describes the horizon buckets as one hour wide, with bucket k holding (k-1, k] hours", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    expect(
      screen.getByText(/bucket k holds horizons above k−1 and up to k hours/),
    ).toBeVisible();
    expect(screen.getByText(/0\.5 hours is in bucket 1/)).toBeVisible();
    await screen.findByRole("table", { name: "Alignment sensitivity" });
  });

  it("shows the decision forecast horizons at the cutoff from the API", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    expect(
      await screen.findByText(/decision forecasts are 16\.5 to 39\.5 hours ahead/),
    ).toBeVisible();
  });

  it("reports the live sensitivity figures for both alignment rules, with the difference", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    const table = await screen.findByRole("table", { name: "Alignment sensitivity" });
    const mae = within(table).getByRole("row", { name: /^MAE/ });
    expect(within(mae).getByText("2,039 MW")).toBeVisible();
    expect(within(mae).getByText("2,023 MW")).toBeVisible();
    expect(within(mae).getByText("−16 MW")).toBeVisible();
    const measured = within(table).getByRole("row", { name: /^Measured hours/ });
    expect(within(measured).getAllByText("742")).toHaveLength(2);
  });

  it("reports the P90 and nMAE under both alignment rules, with the difference", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    const table = await screen.findByRole("table", { name: "Alignment sensitivity" });
    const p90 = within(table).getByRole("row", { name: /^P90/ });
    expect(within(p90).getByText("4,098 MW")).toBeVisible();
    expect(within(p90).getByText("4,150 MW")).toBeVisible();
    expect(within(p90).getByText("+52 MW")).toBeVisible();
    const nmae = within(table).getByRole("row", { name: /^nMAE/ });
    expect(within(nmae).getByText("18.1%")).toBeVisible();
    expect(within(nmae).getByText("17.9%")).toBeVisible();
    expect(within(nmae).getByText("−0.2 pp")).toBeVisible();
  });

  it("reports how many forecasts the snapshot excluded for publishing after their target", async () => {
    stubApi(() => jsonResponse(ACCURACY));

    renderView();

    expect(
      await screen.findByText(/5,521 forecasts were excluded for being published after their target time/),
    ).toBeVisible();
  });

  it("keeps the method on screen when the live figures cannot load, and says so beside them", async () => {
    stubApi(() =>
      jsonResponse({ title: "Service Unavailable", detail: "Data snapshot is not available" }, 503),
    );

    renderView();

    expect(await screen.findByRole("alert")).toHaveTextContent("Data snapshot is not available");
    expect(await screen.findByText(/headline metrics cover only the delivery days/)).toBeVisible();
  });
});
