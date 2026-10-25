import type { EChartsOption, TooltipComponentFormatterCallbackParams } from "echarts";

import type { ErrorBin } from "../api/client";
import { CHART_COLORS } from "../decision/chartOption";
import { formatSignedNumber } from "../format";

// Under-forecast and over-forecast use two distinct hues, the same as the day KPI tiles.
const OVER_FORECAST = "#b5532a";
const UNDER_FORECAST = "#2b7a78";

function hoursLabel(count: number): string {
  return `${count} ${count === 1 ? "hour" : "hours"}`;
}

/**
 * The error histogram: one bar per fixed-width bin of forecast error (forecast minus actual, MW).
 * A bin at or above zero is over-forecast, and a bin below zero is under-forecast.
 */
export function buildHistogramOption(bins: ErrorBin[], reduceMotion: boolean): EChartsOption {
  return {
    animation: !reduceMotion,
    grid: { left: 56, right: 24, top: 24, bottom: 64 },
    tooltip: {
      trigger: "item",
      formatter: (params: TooltipComponentFormatterCallbackParams) => {
        const item = Array.isArray(params) ? params[0] : params;
        const bin = item === undefined ? undefined : bins[item.dataIndex];
        if (!bin) {
          return "";
        }
        const range = `${formatSignedNumber(bin.lower_mw)} to ${formatSignedNumber(bin.upper_mw)} MW`;
        return `${range}: ${hoursLabel(bin.count)}`;
      },
    },
    xAxis: {
      type: "category",
      name: "Forecast error, MW (forecast minus actual)",
      nameLocation: "middle",
      nameGap: 36,
      nameTextStyle: { color: CHART_COLORS.muted },
      data: bins.map((bin) => formatSignedNumber(bin.lower_mw)),
      axisLine: { lineStyle: { color: CHART_COLORS.rule } },
      axisLabel: { color: CHART_COLORS.muted, hideOverlap: true },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      name: "Hours",
      nameTextStyle: { color: CHART_COLORS.muted, align: "right" },
      minInterval: 1,
      axisLabel: { color: CHART_COLORS.muted },
      splitLine: { lineStyle: { color: CHART_COLORS.rule } },
    },
    series: [
      {
        name: "Hours",
        type: "bar",
        barCategoryGap: "10%",
        data: bins.map((bin) => ({
          value: bin.count,
          itemStyle: { color: bin.lower_mw >= 0 ? OVER_FORECAST : UNDER_FORECAST },
        })),
      },
    ],
  };
}
