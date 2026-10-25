import { describe, expect, it } from "vitest";

import type { DecisionHour, HalfHourActual } from "../api/client";
import { actualPoints, bandAreas, forecastSteps } from "./series";

const hour = (target: string, forecast: number | null): DecisionHour => ({
  target_time: target,
  publish_time: forecast === null ? null : "2026-01-01T07:30:00Z",
  forecast_mw: forecast,
  actual_mw: null,
  error_mw: null,
  band_low_mw: null,
  band_high_mw: null,
});

const bandedHour = (
  target: string,
  forecast: number | null,
  low: number | null,
  high: number | null,
): DecisionHour => ({ ...hour(target, forecast), band_low_mw: low, band_high_mw: high });

describe("forecastSteps", () => {
  it("draws each hourly forecast as a flat step across its hour", () => {
    const points = forecastSteps([
      hour("2026-01-02T00:00:00Z", 10000),
      hour("2026-01-02T01:00:00Z", 12000),
    ]);

    expect(points).toEqual([
      [Date.parse("2026-01-02T00:00:00Z"), 10000],
      [Date.parse("2026-01-02T01:00:00Z"), 10000],
      [Date.parse("2026-01-02T01:00:00Z"), 12000],
      [Date.parse("2026-01-02T02:00:00Z"), 12000],
    ]);
  });

  it("breaks the line across an hour with no decision forecast", () => {
    const points = forecastSteps([
      hour("2026-01-02T00:00:00Z", 10000),
      hour("2026-01-02T01:00:00Z", null),
    ]);

    expect(points[2]).toEqual([Date.parse("2026-01-02T01:00:00Z"), null]);
    expect(points[3]).toEqual([Date.parse("2026-01-02T02:00:00Z"), null]);
  });
});

describe("actualPoints", () => {
  it("keeps every half-hour in time order and leaves missing values null", () => {
    const actuals: HalfHourActual[] = [
      { target_time: "2026-01-02T00:00:00Z", generation_mw: 14000 },
      { target_time: "2026-01-02T00:30:00Z", generation_mw: null },
    ];

    expect(actualPoints(actuals)).toEqual([
      [Date.parse("2026-01-02T00:00:00Z"), 14000],
      [Date.parse("2026-01-02T00:30:00Z"), null],
    ]);
  });
});

describe("bandAreas", () => {
  it("gives each hour with a band range its own shaded area, from low to high", () => {
    const areas = bandAreas([
      bandedHour("2026-01-02T00:00:00Z", 10000, 9400, 10000),
      bandedHour("2026-01-02T01:00:00Z", 12000, 11400, 12000),
    ]);

    expect(areas).toEqual([
      {
        start: Date.parse("2026-01-02T00:00:00Z"),
        end: Date.parse("2026-01-02T01:00:00Z"),
        low: 9400,
        high: 10000,
      },
      {
        start: Date.parse("2026-01-02T01:00:00Z"),
        end: Date.parse("2026-01-02T02:00:00Z"),
        low: 11400,
        high: 12000,
      },
    ]);
  });

  it("leaves out an hour that has no band range, so it is not shaded", () => {
    const areas = bandAreas([
      bandedHour("2026-01-02T00:00:00Z", 10000, null, null),
      bandedHour("2026-01-02T01:00:00Z", null, null, null),
    ]);

    expect(areas).toEqual([]);
  });
});
