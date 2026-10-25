import type { DecisionHour, HalfHourActual } from "../api/client";

/** A chart point: epoch milliseconds and a value. A null value breaks the line. */
export type Point = [number, number | null];

const HOUR_MS = 60 * 60 * 1000;

/**
 * Each hourly decision forecast as a flat step across its hour. Two points per hour give the step
 * its vertical edges; an hour without a forecast is a null run, so the line breaks there.
 */
export function forecastSteps(hours: DecisionHour[]): Point[] {
  return hours.flatMap((hour): Point[] => {
    const start = Date.parse(hour.target_time);
    return [
      [start, hour.forecast_mw],
      [start + HOUR_MS, hour.forecast_mw],
    ];
  });
}

/** The hour a forecast step belongs to: forecastSteps gives each hour two consecutive steps. */
export function hourOfStep(stepIndex: number): number {
  return Math.floor(stepIndex / 2);
}

/** Half-hourly actual generation in time order. Missing half-hours stay null. */
export function actualPoints(actuals: HalfHourActual[]): Point[] {
  return actuals.map((actual): Point => [Date.parse(actual.target_time), actual.generation_mw]);
}

/** One hour's expected-error band: the hour's span in epoch milliseconds, and its MW edges. */
export interface BandArea {
  start: number;
  end: number;
  low: number;
  high: number;
}

/** The shaded band for each hour that has a band range. Hours without one are left out. */
export function bandAreas(hours: DecisionHour[]): BandArea[] {
  return hours.flatMap((hour): BandArea[] => {
    if (hour.band_low_mw === null || hour.band_high_mw === null) {
      return [];
    }
    const start = Date.parse(hour.target_time);
    return [{ start, end: start + HOUR_MS, low: hour.band_low_mw, high: hour.band_high_mw }];
  });
}
