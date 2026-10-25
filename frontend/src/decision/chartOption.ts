import type {
  DefaultLabelFormatterCallbackParams as CallbackDataParams,
  EChartsOption,
  TooltipComponentFormatterCallbackParams as TopLevelFormatterParams,
} from "echarts";

import type { DecisionSnapshot } from "../api/client";
import { formatMwh, formatUkTime } from "../format";
import { actualPoints, forecastSteps, type Point } from "./series";

export const CHART_COLORS = {
  forecast: "#2F6690",
  actual: "#1C2330",
  rule: "#E2E2DC",
  muted: "#5B6372",
} as const;

const ukTimeOf = (epochMs: number) => formatUkTime(new Date(epochMs).toISOString());

function describeValue(value: number | null | undefined): string {
  return value === null || value === undefined ? "no value" : formatMwh(value);
}

/** One line per series at the hovered time, in the same order as the legend. */
function tooltip(params: TopLevelFormatterParams): string {
  const items: CallbackDataParams[] = Array.isArray(params) ? params : [params];
  const first = items[0];
  if (!first) {
    return "";
  }
  const x = (first.value as Point)[0];
  const rows = items.map((item) => {
    const value = (item.value as Point)[1];
    return `${item.marker ?? ""} ${item.seriesName}: ${describeValue(value)}`;
  });
  return [`<strong>${ukTimeOf(x)} UK</strong>`, ...rows].join("<br/>");
}

/**
 * The decision chart: the decision forecast as hourly steps, over the half-hourly actuals.
 * Time is on the x axis and generation in MW on the y axis.
 */
export function buildChartOption(snapshot: DecisionSnapshot, reduceMotion: boolean): EChartsOption {
  return {
    animation: !reduceMotion,
    grid: { left: 64, right: 24, top: 24, bottom: 84 },
    tooltip: { trigger: "axis", formatter: tooltip },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: CHART_COLORS.rule } },
      axisLabel: { color: CHART_COLORS.muted, formatter: (value: number) => ukTimeOf(value) },
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
    dataZoom: [
      { type: "inside" },
      {
        type: "slider",
        height: 24,
        bottom: 16,
        borderColor: CHART_COLORS.rule,
        fillerColor: "rgba(47, 102, 144, 0.12)",
        handleStyle: { color: CHART_COLORS.forecast },
        moveHandleStyle: { color: CHART_COLORS.forecast },
        textStyle: { color: CHART_COLORS.muted },
      },
    ],
    series: [
      {
        name: "Decision forecast",
        type: "line",
        data: forecastSteps(snapshot.hours),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 2.5, color: CHART_COLORS.forecast },
        itemStyle: { color: CHART_COLORS.forecast },
        z: 2,
      },
      {
        name: "Actual",
        type: "line",
        data: actualPoints(snapshot.actuals),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: CHART_COLORS.actual },
        itemStyle: { color: CHART_COLORS.actual },
        z: 3,
      },
    ],
  };
}
