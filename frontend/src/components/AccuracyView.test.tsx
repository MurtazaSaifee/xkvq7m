import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { EChartsOption } from "echarts";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AccuracyResponse } from "../api/client";
import { DecisionCutoffProvider } from "./DecisionCutoffProvider";
import { AccuracyView } from "./AccuracyView";

// The chart needs a canvas, which jsdom does not provide. Its option is tested separately, but the
// view's wiring to it is checked here through the props the mock receives.
const charts = vi.hoisted(() => [] as { option: EChartsOption; label: string }[]);
vi.mock("./EChart", () => ({
  EChart: (props: { option: EChartsOption; label: string }) => {
    charts.push(props);
    return null;
  },
}));

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
  histogram: {
    bin_width_mw: 500,
    bins: [
      { lower_mw: -500, upper_mw: 0, count: 3 },
      { lower_mw: 0, upper_mw: 500, count: 4 },
    ],
  },
  heatmap: { cells: [] },
  worst_days: [],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubAccuracy(respond: () => Response) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    if (url.pathname === "/api/v1/accuracy") {
      return Promise.resolve(respond());
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
        <AccuracyView onOpenDecision={() => {}} />
      </DecisionCutoffProvider>
    </QueryClientProvider>,
  );
}

describe("AccuracyView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    charts.length = 0;
    window.history.replaceState(null, "", "/");
  });

  it("shows the headline metrics with plain-language captions", async () => {
    stubAccuracy(() => jsonResponse(ACCURACY));

    renderView();

    const average = await screen.findByRole("group", { name: "Average miss (MAE)" });
    expect(within(average).getByText("2,039 MW")).toBeInTheDocument();

    const bias = screen.getByRole("group", { name: "Bias" });
    expect(within(bias).getByText("+1,748 MW")).toBeInTheDocument();
    expect(
      within(bias).getByText("Forecast ran high on average: wind came in below it"),
    ).toBeVisible();

    const nineInTen = screen.getByRole("group", { name: "Nine-in-ten miss (P90)" });
    expect(within(nineInTen).getByText("4,098 MW")).toBeInTheDocument();
    expect(
      within(nineInTen).getByText("9 times out of 10 the miss is under this"),
    ).toBeVisible();

    const relative = screen.getByRole("group", { name: "Relative miss (nMAE)" });
    expect(within(relative).getByText("18.1%")).toBeInTheDocument();
  });

  it("states how many target hours were measured and counts each reason for leaving one out", async () => {
    stubAccuracy(() => jsonResponse(ACCURACY));

    renderView();

    expect(
      await screen.findByText("Measured on 742 of 744 target hours, 2 Jan to 1 Feb 2026."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Left out: 0 hours with no decision forecast and 2 hours with no actual."),
    ).toBeInTheDocument();
  });

  it("feeds the error histogram the bin counts from the response", async () => {
    stubAccuracy(() => jsonResponse(ACCURACY));

    renderView();

    await screen.findByRole("group", { name: "Average miss (MAE)" });
    const chart = charts.at(-1);
    expect(chart?.label).toBe("Histogram of forecast error, 2 Jan to 1 Feb 2026, at the 09:20 cutoff");
    const series = (chart?.option.series as unknown as { data: { value: number }[] }[])[0];
    expect(series?.data.map((bar) => bar.value)).toEqual([3, 4]);
  });

  it("asks for the accuracy at the cutoff named in the URL, so the view respects the shared cutoff", async () => {
    window.history.replaceState(null, "", "/?cutoff=14:30");
    const fetchMock = stubAccuracy(() => jsonResponse({ ...ACCURACY, cutoff: "14:30" }));

    renderView();

    await screen.findByRole("group", { name: "Average miss (MAE)" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/accuracy?cutoff=14%3A30",
      expect.anything(),
    );
  });

  it("says plainly when no hour can be measured, and shows dashes rather than zeros", async () => {
    stubAccuracy(() =>
      jsonResponse({
        ...ACCURACY,
        summary: {
          ...ACCURACY.summary,
          measured_hours: 0,
          excluded_no_decision_forecast: 744,
          excluded_no_actual: 0,
          mae_mw: null,
          bias_mw: null,
          rmse_mw: null,
          p90_abs_error_mw: null,
          mean_actual_mw: null,
          nmae_percent: null,
        },
        histogram: { bin_width_mw: 500, bins: [] },
      }),
    );

    renderView();

    const average = await screen.findByRole("group", { name: "Average miss (MAE)" });
    expect(within(average).getByText("—")).toBeInTheDocument();
    expect(within(average).getByText("Nothing to measure")).toBeInTheDocument();
    expect(
      screen.getByText("No hour has both a decision forecast and an actual at this cutoff."),
    ).toBeInTheDocument();
  });

  it("shows the API's problem detail when the accuracy cannot be loaded", async () => {
    stubAccuracy(() =>
      jsonResponse({ title: "Service Unavailable", detail: "Data snapshot is not available" }, 503),
    );

    renderView();

    expect(await screen.findByRole("alert")).toHaveTextContent("Data snapshot is not available");
  });

  it("plots the decision forecast error of each heatmap cell, by delivery day and UK hour", async () => {
    stubAccuracy(() =>
      jsonResponse({
        ...ACCURACY,
        heatmap: {
          cells: [
            { delivery_day: "2026-01-02", hour: 0, error_mw: 900 },
            { delivery_day: "2026-01-02", hour: 1, error_mw: -500 },
            { delivery_day: "2026-01-03", hour: 0, error_mw: null },
          ],
        },
      }),
    );

    renderView();

    await screen.findByRole("group", { name: "Average miss (MAE)" });
    const chart = charts.filter((c) => c.label.startsWith("Heatmap")).at(-1);
    expect(chart?.label).toBe(
      "Heatmap of decision forecast error by delivery day and UK hour, 2 Jan to 1 Feb 2026, at the 09:20 cutoff",
    );
    const series = (chart?.option.series as unknown as { data: unknown[] }[])[0];
    expect(series?.data).toEqual([
      [0, 0, 900],
      [1, 0, -500],
      [0, 1, null],
    ]);
  });

  it("says plainly when no heatmap cell can be measured, rather than drawing an empty grid", async () => {
    stubAccuracy(() =>
      jsonResponse({
        ...ACCURACY,
        heatmap: { cells: [{ delivery_day: "2026-01-02", hour: 0, error_mw: null }] },
      }),
    );

    renderView();

    await screen.findByRole("group", { name: "Average miss (MAE)" });
    expect(
      screen.getByText("No cell can be measured at this cutoff, so there is no grid."),
    ).toBeInTheDocument();
    expect(charts.some((c) => c.label.startsWith("Heatmap"))).toBe(false);
  });

  it("hands the chosen worst day to the app, so its row opens the Decision view", async () => {
    stubAccuracy(() =>
      jsonResponse({
        ...ACCURACY,
        worst_days: [
          {
            delivery_day: "2026-01-02",
            error_mwh: 1300,
            forecast_mwh: 93500,
            actual_mwh: 92200,
            paired_hours: 6,
          },
        ],
      }),
    );
    const onOpenDecision = vi.fn();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <DecisionCutoffProvider>
          <AccuracyView onOpenDecision={onOpenDecision} />
        </DecisionCutoffProvider>
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("link", { name: "2 Jan" }));

    expect(onOpenDecision).toHaveBeenCalledWith("2026-01-02");
  });
});
