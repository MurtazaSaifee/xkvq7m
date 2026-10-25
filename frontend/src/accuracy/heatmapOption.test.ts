import type { EChartsOption } from "echarts";
import { describe, expect, it } from "vitest";

import type { HeatmapCell } from "../api/client";
import { buildHeatmapOption } from "./heatmapOption";

function cell(deliveryDay: string, hour: number, errorMw: number | null): HeatmapCell {
  return { delivery_day: deliveryDay, hour, error_mw: errorMw };
}

type HeatmapData = [number, number, number | null];

function optionData(option: EChartsOption): HeatmapData[] {
  const series = option.series as unknown as { data: HeatmapData[] }[];
  return series[0]?.data ?? [];
}

function scale(option: EChartsOption): { min: number; max: number } {
  const visualMap = option.visualMap as unknown as { min: number; max: number };
  return { min: visualMap.min, max: visualMap.max };
}

describe("buildHeatmapOption", () => {
  it("centres the colour scale on zero, out to the largest error on either side", () => {
    const option = buildHeatmapOption(
      [cell("2026-01-02", 0, -1500), cell("2026-01-02", 1, 500), cell("2026-01-02", 2, 200)],
      false,
    );

    expect(scale(option)).toEqual({ min: -1500, max: 1500 });
  });

  it("keeps a usable scale when every measured error is zero", () => {
    const option = buildHeatmapOption([cell("2026-01-02", 0, 0)], false);

    expect(scale(option)).toEqual({ min: -1, max: 1 });
  });

  it("places each cell at its hour and day, and leaves an unmeasured hour empty", () => {
    const option = buildHeatmapOption(
      [
        cell("2026-01-02", 0, 900),
        cell("2026-01-02", 1, null),
        cell("2026-01-03", 0, -400),
        cell("2026-01-03", 1, 100),
      ],
      false,
    );

    // Each point is [hour, day index, error]. Days run down the rows in the order given.
    expect(optionData(option)).toEqual([
      [0, 0, 900],
      [1, 0, null],
      [0, 1, -400],
      [1, 1, 100],
    ]);
  });
});
