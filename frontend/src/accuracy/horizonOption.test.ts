import type { EChartsOption } from "echarts";
import { describe, expect, it } from "vitest";

import type { HorizonBucket, HorizonRange } from "../api/client";
import { buildHorizonOption } from "./horizonOption";

const BUCKETS: HorizonBucket[] = [
  { lower_hours: 0, upper_hours: 1, mae_mw: 1500, bias_mw: 1200, sample_count: 248 },
  { lower_hours: 1, upper_hours: 2, mae_mw: null, bias_mw: null, sample_count: 0 },
  { lower_hours: 2, upper_hours: 3, mae_mw: 1800, bias_mw: -400, sample_count: 1 },
];
const RANGE: HorizonRange = { min_hours: 1.5, max_hours: 2.5 };

type LineSeries = {
  name: string;
  type: string;
  data: [number, number | null][];
  markArea?: { data: [{ name?: string; xAxis: number }, { xAxis: number }][] };
};

function seriesOf(option: EChartsOption): LineSeries[] {
  return option.series as unknown as LineSeries[];
}

function mae(option: EChartsOption): LineSeries {
  return seriesOf(option).find((series) => series.name === "MAE") as LineSeries;
}

type Formatter = (params: { dataIndex: number }) => string;

describe("buildHorizonOption", () => {
  it("plots MAE and bias as two lines against the middle of each one-hour bucket", () => {
    const option = buildHorizonOption(BUCKETS, RANGE, "09:20", true);

    expect(seriesOf(option).map((series) => series.type)).toEqual(["line", "line"]);
    expect(mae(option).data).toEqual([
      [0.5, 1500],
      [1.5, null],
      [2.5, 1800],
    ]);
    expect(seriesOf(option)[1]?.data).toEqual([
      [0.5, 1200],
      [1.5, null],
      [2.5, -400],
    ]);
  });

  it("leaves a gap rather than a zero where a bucket has no measured forecast", () => {
    const option = buildHorizonOption(BUCKETS, RANGE, "09:20", true);

    expect(mae(option).data[1]?.[1]).toBeNull();
  });

  it("runs the horizon axis from zero to the top of the last bucket", () => {
    const option = buildHorizonOption(BUCKETS, RANGE, "09:20", true);

    expect(option.xAxis).toMatchObject({ type: "value", min: 0, max: 3 });
  });

  it("shades the cutoff's decision horizon range and says which cutoff it is", () => {
    const option = buildHorizonOption(BUCKETS, RANGE, "09:20", true);
    const area = mae(option).markArea?.data[0];

    expect(area?.[0].xAxis).toBe(1.5);
    expect(area?.[1].xAxis).toBe(2.5);
    expect(area?.[0].name).toBe("Decision forecasts at 09:20: 1.5–2.5 h");
  });

  it("draws no shaded range when no decision forecast exists at the cutoff", () => {
    const option = buildHorizonOption(BUCKETS, null, "00:01", true);

    expect(mae(option).markArea?.data ?? []).toEqual([]);
  });

  it("says in its tooltip which horizon a point covers, its sample count, MAE and bias", () => {
    const option = buildHorizonOption(BUCKETS, RANGE, "09:20", true);
    const formatter = (option.tooltip as { formatter: Formatter }).formatter;

    expect(formatter({ dataIndex: 2 })).toBe(
      "Horizon 2–3 h<br/>1 forecast<br/>MAE 1,800 MW<br/>Bias −400 MW",
    );
    expect(formatter({ dataIndex: 0 })).toBe(
      "Horizon 0–1 h<br/>248 forecasts<br/>MAE 1,500 MW<br/>Bias +1,200 MW",
    );
  });

  it("says a bucket with no measured forecast has nothing to show", () => {
    const option = buildHorizonOption(BUCKETS, RANGE, "09:20", true);
    const formatter = (option.tooltip as { formatter: Formatter }).formatter;

    expect(formatter({ dataIndex: 1 })).toBe("Horizon 1–2 h<br/>No measured forecast");
  });

  it("turns animation off when the user prefers reduced motion", () => {
    expect(buildHorizonOption(BUCKETS, RANGE, "09:20", true).animation).toBe(false);
    expect(buildHorizonOption(BUCKETS, RANGE, "09:20", false).animation).toBe(true);
  });
});
