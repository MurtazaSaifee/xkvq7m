import type {
  DefaultLabelFormatterCallbackParams as CallbackDataParams,
  EChartsOption,
  TooltipComponentFormatterCallbackParams as TopLevelFormatterParams,
} from "echarts";

import type { DecisionHour, DecisionSnapshot, HalfHourActual } from "../api/client";
import { formatMw, formatMwRange, formatUkTime } from "../format";
import { actualPoints, bandAreas, forecastSteps, type Point } from "./series";

export const CHART_COLORS = {
  forecast: "#2F6690",
  actual: "#1C2330",
  band: "rgba(47, 102, 144, 0.16)",
  rule: "#E2E2DC",
  muted: "#5B6372",
} as const;

const FORECAST_SERIES = "Decision forecast";
const ACTUAL_SERIES = "Actual";
const HOUR_MS = 60 * 60 * 1000;
const HALF_HOUR_MS = HOUR_MS / 2;

const ukTimeOf = (epochMs: number) => formatUkTime(new Date(epochMs).toISOString());

function describeValue(value: number | null | undefined): string {
  return value === null || value === undefined ? "no value" : formatMw(value);
}

/**
 * A hovered item as ECharts passes it on an axis tooltip. ECharts sets axisValue at run time, but
 * its public types leave the field out.
 */
type AxisItem = CallbackDataParams & { axisValue?: string | number };

/** The hovered time in epoch ms: the axis value, which a time axis gives as a number. */
function hoveredTime(first: AxisItem): number {
  return typeof first.axisValue === "number" ? first.axisValue : (first.value as Point)[0];
}

/** The hour whose span holds the instant: it starts at or before the instant and ends after it. */
function hourAt(hours: DecisionHour[], x: number): DecisionHour | undefined {
  return hours.find((hour) => {
    const start = Date.parse(hour.target_time);
    return start <= x && x < start + HOUR_MS;
  });
}

/** The actual at the start of the half-hour that holds the instant, if the snapshot has one. */
function actualAt(actuals: HalfHourActual[], x: number): HalfHourActual | undefined {
  const halfHourStart = Math.floor(x / HALF_HOUR_MS) * HALF_HOUR_MS;
  return actuals.find((actual) => Date.parse(actual.target_time) === halfHourStart);
}

const MARKER_STYLE =
  "display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;";

/** One tooltip row, with a marker in the series colour. */
function row(color: string, label: string, value: string): string {
  return `<span style="${MARKER_STYLE}background-color:${color};"></span>${label}: ${value}`;
}

/**
 * The rows describe the hour holding the hovered time, and the half-hour actual at it, both read
 * from the snapshot by time. ECharts' own items are not used: an hour edge gives two forecast steps
 * and a half-hour gives none. A row is left out when the snapshot has nothing for it.
 */
function tooltipFormatter(snapshot: DecisionSnapshot) {
  return (params: TopLevelFormatterParams): string => {
    const first = (Array.isArray(params) ? params[0] : params) as AxisItem | undefined;
    if (!first) {
      return "";
    }
    const x = hoveredTime(first);
    const hour = hourAt(snapshot.hours, x);
    const actual = actualAt(snapshot.actuals, x);
    const rows: string[] = [];
    if (hour !== undefined) {
      rows.push(row(CHART_COLORS.forecast, FORECAST_SERIES, describeValue(hour.forecast_mw)));
    }
    if (hour !== undefined || actual !== undefined) {
      rows.push(row(CHART_COLORS.actual, ACTUAL_SERIES, describeValue(actual?.generation_mw)));
    }
    if (hour !== undefined && hour.band_low_mw !== null && hour.band_high_mw !== null) {
      rows.push(`Expected range: ${formatMwRange(hour.band_low_mw, hour.band_high_mw)}`);
    }
    return [`<strong>${ukTimeOf(x)} UK</strong>`, ...rows].join("<br/>");
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
    tooltip: { trigger: "axis", formatter: tooltipFormatter(snapshot) },
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
        name: ACTUAL_SERIES,
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
