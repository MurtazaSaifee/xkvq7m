import { describe, expect, it } from "vitest";

import type { DecisionSnapshot } from "../api/client";
import { buildChartOption } from "./chartOption";

type LineSeries = {
  name: string;
  data: [number, number | null][];
  connectNulls?: boolean;
  markArea?: { data: { xAxis: number; yAxis: number }[][] };
};

/** 21:00 has a decision forecast from the 22:30 run. 22:00 has none, so it must draw as a gap. */
const SNAPSHOT: DecisionSnapshot = {
  delivery_day: "2026-01-05",
  decision_day: "2026-01-04",
  cutoff: "01:00",
  cutoff_time: "2026-01-04T01:00:00Z",
  forecast_run_publish_time: "2026-01-03T22:30:00Z",
  band: { lower_error_mw: -300, upper_error_mw: 500, history_days: 14 },
  hours: [
    {
      target_time: "2026-01-05T21:00:00Z",
      publish_time: "2026-01-03T22:30:00Z",
      forecast_mw: 15500,
      actual_mw: 15000,
      error_mw: 500,
      band_low_mw: 15000,
      band_high_mw: 15800,
    },
    {
      target_time: "2026-01-05T22:00:00Z",
      publish_time: null,
      forecast_mw: null,
      actual_mw: null,
      error_mw: null,
      band_low_mw: null,
      band_high_mw: null,
    },
  ],
  actuals: [
    { target_time: "2026-01-05T21:00:00Z", generation_mw: 15000 },
    { target_time: "2026-01-05T21:30:00Z", generation_mw: null },
  ],
  kpis: {
    forecast_mwh: null,
    actual_mwh: null,
    error_mwh: null,
    paired_hours: 0,
    missing_forecast_hours: 1,
    missing_actual_hours: 0,
  },
};

function lineSeries(snapshot: DecisionSnapshot): LineSeries[] {
  const option = buildChartOption(snapshot, true);
  return option.series as unknown as LineSeries[];
}

describe("buildChartOption", () => {
  it("draws the hour without a decision forecast as a break in the line, not a zero", () => {
    const [forecast] = lineSeries(SNAPSHOT);

    expect(forecast?.name).toBe("Decision forecast");
    expect(forecast?.data).toEqual([
      [Date.parse("2026-01-05T21:00:00Z"), 15500],
      [Date.parse("2026-01-05T22:00:00Z"), 15500],
      [Date.parse("2026-01-05T22:00:00Z"), null],
      [Date.parse("2026-01-05T23:00:00Z"), null],
    ]);
    expect(forecast?.data.some(([, value]) => value === 0)).toBe(false);
  });

  it("does not connect across missing values in either series", () => {
    const [forecast, actual] = lineSeries(SNAPSHOT);

    expect(forecast?.connectNulls).toBe(false);
    expect(actual?.connectNulls).toBe(false);
  });

  it("keeps a missing half-hour actual as a gap", () => {
    const [, actual] = lineSeries(SNAPSHOT);

    expect(actual?.data).toEqual([
      [Date.parse("2026-01-05T21:00:00Z"), 15000],
      [Date.parse("2026-01-05T21:30:00Z"), null],
    ]);
  });

  it("shades the expected-error band over each hour that has one, between its edges", () => {
    const [forecast] = lineSeries(SNAPSHOT);

    expect(forecast?.markArea?.data).toEqual([
      [
        { xAxis: Date.parse("2026-01-05T21:00:00Z"), yAxis: 15800 },
        { xAxis: Date.parse("2026-01-05T22:00:00Z"), yAxis: 15000 },
      ],
    ]);
  });

  it("draws no band when the day has none", () => {
    const withoutBand: DecisionSnapshot = {
      ...SNAPSHOT,
      band: null,
      hours: SNAPSHOT.hours.map((hour) => ({ ...hour, band_low_mw: null, band_high_mw: null })),
    };
    const [forecast] = lineSeries(withoutBand);

    expect(forecast?.markArea?.data ?? []).toEqual([]);
  });

  it("reads the time axis in UTC, so ticks sit on whole UK hours for any viewer's zone", () => {
    const option = buildChartOption(SNAPSHOT, true) as { useUTC?: boolean; xAxis: { type: string } };

    expect(option.xAxis.type).toBe("time");
    expect(option.useUTC).toBe(true);
  });
});

/** The fields of an ECharts axis-tooltip item that the formatter reads. */
type TooltipItem = {
  seriesName: string;
  dataIndex: number;
  value: [number, number | null];
  marker: string;
};

/** The tooltip text the built option gives for the hovered items. */
function tooltipText(snapshot: DecisionSnapshot, items: TooltipItem[]): string {
  const option = buildChartOption(snapshot, true) as unknown as {
    tooltip: { formatter: (items: TooltipItem[]) => string };
  };
  return option.tooltip.formatter(items);
}

describe("the hover tooltip", () => {
  const HOUR_21 = Date.parse("2026-01-05T21:00:00Z");
  const HOUR_22 = Date.parse("2026-01-05T22:00:00Z");

  it("reads the decision forecast and the actual in MW, not MWh", () => {
    const text = tooltipText(SNAPSHOT, [
      {
        seriesName: "Decision forecast",
        dataIndex: 0,
        value: [HOUR_21, 15500],
        marker: "",
      },
      { seriesName: "Actual", dataIndex: 0, value: [HOUR_21, 15000], marker: "" },
    ]);

    expect(text).toContain("Decision forecast: 15,500 MW");
    expect(text).toContain("Actual: 15,000 MW");
    expect(text).not.toContain("MWh");
  });

  it("gives the expected range of the hour, low to high", () => {
    const text = tooltipText(SNAPSHOT, [
      { seriesName: "Decision forecast", dataIndex: 0, value: [HOUR_21, 15500], marker: "" },
    ]);

    expect(text).toContain("Expected range: 15,000–15,800 MW");
  });

  it("takes the range of the hour the forecast value comes from, at an hour boundary", () => {
    // Point 1 is the end of the 21:00 step, so it carries the 21:00 forecast and its band.
    const text = tooltipText(SNAPSHOT, [
      { seriesName: "Decision forecast", dataIndex: 1, value: [HOUR_22, 15500], marker: "" },
    ]);

    expect(text).toContain("Expected range: 15,000–15,800 MW");
  });

  it("leaves out the range when the hour has none, and says the forecast has no value", () => {
    // Point 2 starts the 22:00 hour, which has no decision forecast and so no band.
    const text = tooltipText(SNAPSHOT, [
      { seriesName: "Decision forecast", dataIndex: 2, value: [HOUR_22, null], marker: "" },
    ]);

    expect(text).toContain("Decision forecast: no value");
    expect(text).not.toContain("Expected range");
  });
});
