import type {
  EChartsOption,
  MarkAreaComponentOption,
  TooltipComponentFormatterCallbackParams,
} from "echarts";

import type { HorizonBucket, HorizonRange } from "../api/client";
import { CHART_COLORS } from "../decision/chartOption";
import { formatMw, formatSignedMw } from "../format";

// The forecast hue at low opacity, the same fill the decision view uses for its zoom slider.
const DECISION_RANGE_FILL = "rgba(47, 102, 144, 0.12)";

function bucketSpan(bucket: HorizonBucket): string {
  return `${bucket.lower_hours}–${bucket.upper_hours} h`;
}

function bucketMidpoint(bucket: HorizonBucket): number {
  return (bucket.lower_hours + bucket.upper_hours) / 2;
}

function forecastsLabel(count: number): string {
  return `${count} ${count === 1 ? "forecast" : "forecasts"}`;
}

/** The tooltip for one bucket: its horizon, how many forecasts it holds, then MAE and bias. */
function describeBucket(bucket: HorizonBucket): string {
  const heading = `Horizon ${bucketSpan(bucket)}`;
  if (bucket.mae_mw === null || bucket.bias_mw === null || bucket.sample_count === 0) {
    return `${heading}<br/>No measured forecast`;
  }
  return [
    heading,
    forecastsLabel(bucket.sample_count),
    `MAE ${formatMw(bucket.mae_mw)}`,
    `Bias ${formatSignedMw(bucket.bias_mw)}`,
  ].join("<br/>");
}

/**
 * Error by forecast horizon: MAE and bias (forecast minus actual, MW) for each one-hour bucket of
 * horizon. Each point sits at the middle of its bucket, so the decision range's ends fall on bucket
 * centres. The shaded band marks the horizons of the decision forecasts at the cutoff.
 */
export function buildHorizonOption(
  buckets: HorizonBucket[],
  decisionRange: HorizonRange | null,
  cutoff: string,
  reduceMotion: boolean,
): EChartsOption {
  const highlight: MarkAreaComponentOption["data"] =
    decisionRange === null
      ? []
      : [
          [
            {
              name: `Decision forecasts at ${cutoff}: ${decisionRange.min_hours}–${decisionRange.max_hours} h`,
              xAxis: decisionRange.min_hours,
              itemStyle: { color: DECISION_RANGE_FILL },
              label: { position: "insideBottom", color: CHART_COLORS.muted },
            },
            { xAxis: decisionRange.max_hours },
          ],
        ];

  return {
    animation: !reduceMotion,
    grid: { left: 64, right: 24, top: 48, bottom: 64 },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 14,
      itemHeight: 3,
      textStyle: { color: CHART_COLORS.muted },
      data: ["MAE", "Bias"],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", snap: true },
      formatter: (params: TooltipComponentFormatterCallbackParams) => {
        const first = Array.isArray(params) ? params[0] : params;
        const bucket = first === undefined ? undefined : buckets[first.dataIndex];
        return bucket ? describeBucket(bucket) : "";
      },
    },
    xAxis: {
      type: "value",
      name: "Forecast horizon, hours (target time minus publish time)",
      nameLocation: "middle",
      nameGap: 36,
      nameTextStyle: { color: CHART_COLORS.muted },
      min: 0,
      max: buckets.at(-1)?.upper_hours,
      minInterval: 1,
      axisLine: { lineStyle: { color: CHART_COLORS.rule } },
      axisLabel: { color: CHART_COLORS.muted },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      name: "MW",
      nameTextStyle: { color: CHART_COLORS.muted, align: "right" },
      axisLabel: {
        color: CHART_COLORS.muted,
        formatter: (value: number) => value.toLocaleString("en-GB"),
      },
      splitLine: { lineStyle: { color: CHART_COLORS.rule } },
    },
    series: [
      {
        name: "MAE",
        type: "line",
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: CHART_COLORS.forecast, width: 2 },
        itemStyle: { color: CHART_COLORS.forecast },
        data: buckets.map((bucket) => [bucketMidpoint(bucket), bucket.mae_mw]),
        markArea: { silent: true, data: highlight },
      },
      {
        name: "Bias",
        type: "line",
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: CHART_COLORS.actual, width: 1.5, type: "dashed" },
        itemStyle: { color: CHART_COLORS.actual },
        data: buckets.map((bucket) => [bucketMidpoint(bucket), bucket.bias_mw]),
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: CHART_COLORS.muted, width: 1 },
          label: { show: false },
          data: [{ yAxis: 0 }],
        },
      },
    ],
  };
}
