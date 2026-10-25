import { describe, expect, it } from "vitest";

import type { DecisionHour, HalfHourActual } from "../api/client";
import { actualPoints, forecastSteps } from "./series";

const hour = (target: string, forecast: number | null): DecisionHour => ({
  target_time: target,
  publish_time: forecast === null ? null : "2026-01-01T07:30:00Z",
  forecast_mw: forecast,
  actual_mw: null,
  error_mw: null,
});

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
