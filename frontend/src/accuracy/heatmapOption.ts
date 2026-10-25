import type {
  DefaultLabelFormatterCallbackParams as CallbackDataParams,
  EChartsOption,
  TooltipComponentFormatterCallbackParams as TopLevelFormatterParams,
} from "echarts";

import type { HeatmapCell } from "../api/client";
import { CHART_COLORS } from "../decision/chartOption";
import { formatDay, formatSignedMw } from "../format";

// The same two hues as the error histogram, so over- and under-forecast read alike in both charts.
const OVER_FORECAST = "#b5532a";
const UNDER_FORECAST = "#2b7a78";
const NEUTRAL = "#f7f7f4";

const HOURS = 24;

type HeatmapPoint = [number, number, number | null];

const hourLabel = (hour: number) => `${String(hour).padStart(2, "0")}:00`;

/** The delivery days in the order they first appear, so the rows follow the response. */
function daysOf(cells: HeatmapCell[]): string[] {
  return [...new Set(cells.map((cell) => cell.delivery_day))];
}

/**
 * The error heatmap: one row per delivery day, one column per UK hour of day, each cell the decision
 * forecast error in MW (forecast minus actual). The colour scale is centred on zero and runs out to
 * the largest error on either side, so a cell's hue shows its direction and its depth its size.
 */
export function buildHeatmapOption(cells: HeatmapCell[], reduceMotion: boolean): EChartsOption {
  const days = daysOf(cells);
  const dayIndex = new Map(days.map((day, index) => [day, index]));
  const largest = Math.max(
    1,
    ...cells.flatMap((cell) => (cell.error_mw === null ? [] : [Math.abs(cell.error_mw)])),
  );

  const points: HeatmapPoint[] = cells.map((cell) => [
    cell.hour,
    dayIndex.get(cell.delivery_day) ?? 0,
    cell.error_mw,
  ]);

  return {
    animation: !reduceMotion,
    grid: { left: 96, right: 24, top: 16, bottom: 96 },
    tooltip: {
      trigger: "item",
      formatter: (params: TopLevelFormatterParams) => {
        const item = (Array.isArray(params) ? params[0] : params) as CallbackDataParams | undefined;
        const point = item?.value as HeatmapPoint | undefined;
        if (point === undefined) {
          return "";
        }
        const [hour, row, error] = point;
        const when = `${formatDay(days[row] ?? "")}, ${hourLabel(hour)} UK`;
        const value = error === null ? "No measured error" : formatSignedMw(error);
        return `${when}<br/>${value}`;
      },
    },
    xAxis: {
      type: "category",
      data: Array.from({ length: HOURS }, (_, hour) => hourLabel(hour)),
      splitArea: { show: false },
      axisLine: { lineStyle: { color: CHART_COLORS.rule } },
      // Every sixth hour is labelled, so the labels stay apart in a narrow chart.
      axisLabel: { color: CHART_COLORS.muted, interval: (index: number) => index % 6 === 0 },
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: days.map((day) => formatDay(day)),
      axisLine: { show: false },
      axisLabel: { color: CHART_COLORS.muted },
      axisTick: { show: false },
    },
    visualMap: {
      type: "continuous",
      min: -largest,
      max: largest,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      itemWidth: 14,
      itemHeight: 180,
      textStyle: { color: CHART_COLORS.muted },
      inRange: { color: [UNDER_FORECAST, NEUTRAL, OVER_FORECAST] },
    },
    series: [
      {
        name: "Forecast error",
        type: "heatmap",
        data: points,
        label: { show: false },
        itemStyle: { borderColor: NEUTRAL, borderWidth: 1 },
      },
    ],
  };
}
