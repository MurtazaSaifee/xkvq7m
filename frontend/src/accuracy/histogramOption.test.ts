import type { EChartsOption } from "echarts";
import { describe, expect, it } from "vitest";

import type { ErrorBin } from "../api/client";
import { buildHistogramOption } from "./histogramOption";

const BINS: ErrorBin[] = [
  { lower_mw: -500, upper_mw: 0, count: 2 },
  { lower_mw: 0, upper_mw: 500, count: 5 },
  { lower_mw: 500, upper_mw: 1000, count: 1 },
];

type BarSeries = { type: string; data: { value: number; itemStyle: { color: string } }[] };

function seriesOf(option: EChartsOption): BarSeries {
  return (option.series as unknown as BarSeries[])[0];
}

describe("buildHistogramOption", () => {
  it("draws one bar per bin, sized by its hour count", () => {
    const series = seriesOf(buildHistogramOption(BINS, true));

    expect(series.type).toBe("bar");
    expect(series.data.map((bar) => bar.value)).toEqual([2, 5, 1]);
  });

  it("labels each bin by its lower edge with a sign, so the axis reads as signed error", () => {
    const option = buildHistogramOption(BINS, true);

    expect((option.xAxis as { data: string[] }).data).toEqual(["−500", "0", "+500"]);
  });

  it("colours under-forecast bins and over-forecast bins with the two error hues", () => {
    const colours = seriesOf(buildHistogramOption(BINS, true)).data.map((bar) => bar.itemStyle.color);

    expect(colours[0]).not.toBe(colours[1]);
    expect(colours[1]).toBe(colours[2]);
  });

  it("says in its tooltip which error range a bar covers and how many hours fall in it", () => {
    const option = buildHistogramOption(BINS, true);
    const formatter = (option.tooltip as { formatter: (params: { dataIndex: number }) => string })
      .formatter;

    expect(formatter({ dataIndex: 0 })).toBe("−500 to 0 MW: 2 hours");
    expect(formatter({ dataIndex: 2 })).toBe("+500 to +1,000 MW: 1 hour");
  });

  it("turns animation off when the user prefers reduced motion", () => {
    expect(buildHistogramOption(BINS, true).animation).toBe(false);
    expect(buildHistogramOption(BINS, false).animation).toBe(true);
  });
});
