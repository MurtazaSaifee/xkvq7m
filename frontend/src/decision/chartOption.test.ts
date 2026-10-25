import { describe, expect, it } from "vitest";

import type { DecisionHour, DecisionSnapshot } from "../api/client";
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
  axisValue?: number;
};

/** The tooltip text the built option gives for the hovered items. */
function tooltipText(snapshot: DecisionSnapshot, items: TooltipItem[]): string {
  const option = buildChartOption(snapshot, true) as unknown as {
    tooltip: { formatter: (items: TooltipItem[]) => string };
  };
  return option.tooltip.formatter(items);
}

function countOf(text: string, phrase: string): number {
  return text.split(phrase).length - 1;
}

/** One delivery hour in the shape the API returns. */
function decisionHour(
  targetTime: string,
  forecastMw: number | null,
  band: [number, number] | null,
): DecisionHour {
  return {
    target_time: targetTime,
    publish_time: forecastMw === null ? null : "2026-01-03T22:30:00Z",
    forecast_mw: forecastMw,
    actual_mw: null,
    error_mw: null,
    band_low_mw: band?.[0] ?? null,
    band_high_mw: band?.[1] ?? null,
  };
}

/**
 * Four delivery hours and the half-hourly actuals across them. 20:00 is a gap with no decision
 * forecast, 23:00 has a forecast but no band, and 00:00 on 6 Jan is past the last hour.
 */
const TOOLTIP_SNAPSHOT: DecisionSnapshot = {
  ...SNAPSHOT,
  hours: [
    decisionHour("2026-01-05T20:00:00Z", null, null),
    decisionHour("2026-01-05T21:00:00Z", 15500, [15000, 15800]),
    decisionHour("2026-01-05T22:00:00Z", 16000, [15400, 16400]),
    decisionHour("2026-01-05T23:00:00Z", 16200, null),
  ],
  actuals: [
    { target_time: "2026-01-05T20:00:00Z", generation_mw: 14800 },
    { target_time: "2026-01-05T20:30:00Z", generation_mw: null },
    { target_time: "2026-01-05T21:00:00Z", generation_mw: 15000 },
    { target_time: "2026-01-05T21:30:00Z", generation_mw: 15250 },
    { target_time: "2026-01-05T22:00:00Z", generation_mw: 16100 },
    { target_time: "2026-01-05T22:30:00Z", generation_mw: 16300 },
  ],
};

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

  it("shows one forecast row at an hour boundary, for the later hour, with that hour's range", () => {
    // ECharts passes both steps at 22:00: the end of the 21:00 hour and the start of the 22:00 hour.
    const boundary = Date.parse("2026-01-05T22:00:00Z");
    const text = tooltipText(TOOLTIP_SNAPSHOT, [
      {
        seriesName: "Decision forecast",
        dataIndex: 3,
        value: [boundary, 15500],
        marker: "",
        axisValue: boundary,
      },
      {
        seriesName: "Decision forecast",
        dataIndex: 4,
        value: [boundary, 16000],
        marker: "",
        axisValue: boundary,
      },
    ]);

    expect(text).toContain("22:00 UK");
    expect(countOf(text, "Decision forecast")).toBe(1);
    expect(text).toContain("Decision forecast: 16,000 MW");
    expect(text).toContain("Expected range: 15,400–16,400 MW");
    expect(text).not.toContain("15,500");
    expect(text).not.toContain("15,800");
  });

  it("shows the forecast and range of the hour holding a half-hour, and that half-hour's actual", () => {
    const halfHour = Date.parse("2026-01-05T21:30:00Z");
    const text = tooltipText(TOOLTIP_SNAPSHOT, [
      {
        seriesName: "Actual",
        dataIndex: 3,
        value: [halfHour, 15250],
        marker: "",
        axisValue: halfHour,
      },
    ]);

    expect(text).toContain("21:30 UK");
    expect(countOf(text, "Decision forecast")).toBe(1);
    expect(text).toContain("Decision forecast: 15,500 MW");
    expect(text).toContain("Expected range: 15,000–15,800 MW");
    expect(text).toContain("Actual: 15,250 MW");
  });

  it("leaves out the range when the hour has none, and says the forecast has no value", () => {
    // Point 2 starts the 22:00 hour, which has no decision forecast and so no band.
    const text = tooltipText(SNAPSHOT, [
      { seriesName: "Decision forecast", dataIndex: 2, value: [HOUR_22, null], marker: "" },
    ]);

    expect(text).toContain("Decision forecast: no value");
    expect(text).not.toContain("Expected range");
  });

  it("says the forecast has no value for a gap hour, and still shows that half-hour's actual", () => {
    const gapHour = Date.parse("2026-01-05T20:00:00Z");
    const text = tooltipText(TOOLTIP_SNAPSHOT, [
      {
        seriesName: "Decision forecast",
        dataIndex: 0,
        value: [gapHour, null],
        marker: "",
        axisValue: gapHour,
      },
    ]);

    expect(text).toContain("Decision forecast: no value");
    expect(text).toContain("Actual: 14,800 MW");
    expect(text).not.toContain("Expected range");
  });

  it("leaves out the range for an hour that has a forecast but no band", () => {
    const noBandHour = Date.parse("2026-01-05T23:00:00Z");
    const text = tooltipText(TOOLTIP_SNAPSHOT, [
      {
        seriesName: "Decision forecast",
        dataIndex: 6,
        value: [noBandHour, 16200],
        marker: "",
        axisValue: noBandHour,
      },
    ]);

    expect(text).toContain("Decision forecast: 16,200 MW");
    expect(text).not.toContain("Expected range");
  });

  it("shows only the heading when the hovered time is past every hour and has no actual", () => {
    // The last hour ends at 24:00, which belongs to no hour, and no half-hour actual starts there.
    const end = Date.parse("2026-01-06T00:00:00Z");
    const text = tooltipText(TOOLTIP_SNAPSHOT, [
      {
        seriesName: "Decision forecast",
        dataIndex: 7,
        value: [end, 16200],
        marker: "",
        axisValue: end,
      },
    ]);

    expect(text).toContain("00:00 UK");
    expect(text).not.toContain("Decision forecast");
    expect(text).not.toContain("Actual");
    expect(text).not.toContain("Expected range");
  });

  it("takes the hovered time from the axis value, not from the item's own value", () => {
    const halfHour = Date.parse("2026-01-05T21:30:00Z");
    const text = tooltipText(TOOLTIP_SNAPSHOT, [
      { seriesName: "Actual", dataIndex: 2, value: [HOUR_21, 15000], marker: "", axisValue: halfHour },
    ]);

    expect(text).toContain("21:30 UK");
    expect(text).toContain("Actual: 15,250 MW");
  });
});
