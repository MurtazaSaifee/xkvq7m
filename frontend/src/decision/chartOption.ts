import type {
  DefaultLabelFormatterCallbackParams as CallbackDataParams,
  EChartsOption,
  TooltipComponentFormatterCallbackParams as TopLevelFormatterParams,
} from "echarts";

import type { DecisionHour, DecisionSnapshot } from "../api/client";
import { formatMw, formatMwRange, formatUkTime } from "../format";
import { actualPoints, bandAreas, forecastSteps, hourOfStep, type Point } from "./series";

export const CHART_COLORS = {
  forecast: "#2F6690",
  actual: "#1C2330",
  band: "rgba(47, 102, 144, 0.16)",
  rule: "#E2E2DC",
  muted: "#5B6372",
} as const;

const FORECAST_SERIES = "Decision forecast";

const ukTimeOf = (epochMs: number) => formatUkTime(new Date(epochMs).toISOString());

function describeValue(value: number | null | undefined): string {
  return value === null || value === undefined ? "no value" : formatMw(value);
}

/**
 * The expected-error range of the hour the hovered forecast belongs to, if it has one. The item's
 * data index is its forecast step, so the range is the one for the forecast value shown, even when
 * the cursor sits on an hour edge.
 */
function bandRows(items: CallbackDataParams[], hours: DecisionHour[]): string[] {
  const forecast = items.find((item) => item.seriesName === FORECAST_SERIES);
  if (forecast === undefined) {
    return [];
  }
  const hour = hours[hourOfStep(forecast.dataIndex)];
  if (hour === undefined || hour.band_low_mw === null || hour.band_high_mw === null) {
    return [];
  }
  return [`Expected range: ${formatMwRange(hour.band_low_mw, hour.band_high_mw)}`];
}

/** One line per series at the hovered time, in legend order, then the hour's expected range. */
function tooltipFormatter(hours: DecisionHour[]) {
  return (params: TopLevelFormatterParams): string => {
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
    return [`<strong>${ukTimeOf(x)} UK</strong>`, ...rows, ...bandRows(items, hours)].join("<br/>");
  };
}

/**
 * The decision chart: the decision forecast as hourly steps, over the half-hourly actuals.
 * Time is on the x axis and generation in MW on the y axis.
 */
export function buildChartOption(snapshot: DecisionSnapshot, reduceMotion: boolean): EChartsOption {
  return {
    animation: !reduceMotion,
    // Time ticks are placed in UTC. Otherwise ECharts places them in the viewer's zone, so a viewer
    // at UTC+05:30 would see ticks at 02:30 and 06:30. The labels are UK time from ukTimeOf.
    useUTC: true,
    grid: { left: 64, right: 24, top: 24, bottom: 84 },
    tooltip: { trigger: "axis", formatter: tooltipFormatter(snapshot.hours) },
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
        name: FORECAST_SERIES,
        type: "line",
        data: forecastSteps(snapshot.hours),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 2.5, color: CHART_COLORS.forecast },
        itemStyle: { color: CHART_COLORS.forecast },
        // The expected-error band, one shaded hour per hour that has a band range. It is drawn
        // from the decision forecast's series, so the band shares its hourly steps.
        markArea: {
          silent: true,
          itemStyle: { color: CHART_COLORS.band },
          data: bandAreas(snapshot.hours).map((area) => [
            { xAxis: area.start, yAxis: area.high },
            { xAxis: area.end, yAxis: area.low },
          ]),
        },
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
