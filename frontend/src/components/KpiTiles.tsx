import type { DayKpis } from "../api/client";
import { formatMwh, formatSignedMwh } from "../format";
import { Figure } from "./Figure";

const EM_DASH = "—";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function errorCaption(error: number): string {
  if (error > 0) {
    return "Over-forecast: wind came in below the forecast";
  }
  if (error < 0) {
    return "Under-forecast: wind came in above the forecast";
  }
  return "No net error over the day";
}

/** The day's totals over the hours that have both a decision forecast and an actual. */
export function KpiTiles({ kpis }: { kpis: DayKpis }) {
  const hasPairs = kpis.paired_hours > 0;
  const left = [
    kpis.missing_forecast_hours > 0
      ? plural(kpis.missing_forecast_hours, "hour without a decision forecast", "hours without a decision forecast")
      : null,
    kpis.missing_actual_hours > 0
      ? plural(kpis.missing_actual_hours, "hour without an actual", "hours without an actual")
      : null,
  ].filter((part): part is string => part !== null);

  const error = kpis.error_mwh;
  const errorTone = error === null || error === 0 ? "ink" : error > 0 ? "over" : "under";

  return (
    <div className="space-y-4">
      <div className="grid gap-6 sm:grid-cols-3">
        <Figure
          label="Forecast"
          value={kpis.forecast_mwh === null ? EM_DASH : formatMwh(kpis.forecast_mwh)}
          caption="Decision forecast, summed over the hours compared"
        />
        <Figure
          label="Actual"
          value={kpis.actual_mwh === null ? EM_DASH : formatMwh(kpis.actual_mwh)}
          caption="Half-hourly generation, averaged to the hour"
        />
        <Figure
          label="Forecast error"
          value={error === null ? EM_DASH : formatSignedMwh(error)}
          caption={error === null ? "Nothing to compare" : errorCaption(error)}
          tone={errorTone}
        />
      </div>
      {!hasPairs ? (
        <p className="text-sm text-muted">No hour has both a decision forecast and an actual.</p>
      ) : null}
      {left.length > 0 ? (
        <p className="text-sm text-muted">Left out: {left.join(" and ")}.</p>
      ) : null}
    </div>
  );
}
