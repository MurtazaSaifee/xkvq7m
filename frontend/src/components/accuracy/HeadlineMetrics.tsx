import type { AccuracyResponse } from "../../api/client";
import {
  formatDayRange,
  formatMw,
  formatPercent,
  formatSignedMw,
} from "../../format";
import { Figure, type FigureTone } from "../Figure";

type Summary = AccuracyResponse["summary"];
type DeliveryDays = AccuracyResponse["delivery_days"];

const EM_DASH = "—";
const NOTHING_TO_MEASURE = "Nothing to measure";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function biasCaption(bias: number): string {
  if (bias > 0) {
    return "Forecast ran high on average: wind came in below it";
  }
  if (bias < 0) {
    return "Forecast ran low on average: wind came in above it";
  }
  return "No net bias over the period";
}

function biasTone(bias: number | null): FigureTone {
  if (bias === null || bias === 0) {
    return "ink";
  }
  return bias > 0 ? "over" : "under";
}

/** Coverage line: how many target hours are measured, and why each other hour was left out. */
function coverage(summary: Summary, deliveryDays: DeliveryDays): string[] {
  const measured = `Measured on ${summary.measured_hours} of ${summary.target_hours} target hours, ${formatDayRange(deliveryDays.first, deliveryDays.last)}.`;
  const left = `Left out: ${plural(summary.excluded_no_decision_forecast, "hour with no decision forecast", "hours with no decision forecast")} and ${plural(summary.excluded_no_actual, "hour with no actual", "hours with no actual")}.`;
  return [measured, left];
}

/** The headline accuracy figures, each with a plain-language caption. */
export function HeadlineMetrics({
  summary,
  deliveryDays,
}: {
  summary: Summary;
  deliveryDays: DeliveryDays;
}) {
  const [measured, left] = coverage(summary, deliveryDays);
  const hasMeasure = summary.measured_hours > 0;

  return (
    <div className="space-y-4">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <Figure
          label="Average miss (MAE)"
          value={summary.mae_mw === null ? EM_DASH : formatMw(summary.mae_mw)}
          caption={
            hasMeasure
              ? "The typical size of a miss, ignoring its direction"
              : NOTHING_TO_MEASURE
          }
        />
        <Figure
          label="Bias"
          value={summary.bias_mw === null ? EM_DASH : formatSignedMw(summary.bias_mw)}
          tone={biasTone(summary.bias_mw)}
          caption={summary.bias_mw === null ? NOTHING_TO_MEASURE : biasCaption(summary.bias_mw)}
        />
        <Figure
          label="Large misses (RMSE)"
          value={summary.rmse_mw === null ? EM_DASH : formatMw(summary.rmse_mw)}
          caption={
            hasMeasure
              ? "Counts big misses more than small ones, so it rises above the average miss when a few hours are far out"
              : NOTHING_TO_MEASURE
          }
        />
        <Figure
          label="Nine-in-ten miss (P90)"
          value={summary.p90_abs_error_mw === null ? EM_DASH : formatMw(summary.p90_abs_error_mw)}
          caption={
            hasMeasure ? "9 times out of 10 the miss is under this" : NOTHING_TO_MEASURE
          }
        />
        <Figure
          label="Relative miss (nMAE)"
          value={summary.nmae_percent === null ? EM_DASH : formatPercent(summary.nmae_percent)}
          caption={
            summary.mean_actual_mw === null
              ? NOTHING_TO_MEASURE
              : `The average miss as a share of average actual wind, ${formatMw(summary.mean_actual_mw)}`
          }
        />
      </div>
      <p className="text-sm text-muted">{measured}</p>
      <p className="text-sm text-muted">{left}</p>
    </div>
  );
}
