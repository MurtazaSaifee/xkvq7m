import type { MetaResponse } from "../api/client";
import { useMetaQuery } from "../api/queries";
import { StatusBadge } from "./StatusBadge";

// Dates are formatted in UTC so the badge never shifts with the viewer's timezone.
const dayFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const formatDay = (iso: string) => dayFormat.format(new Date(iso));

function describeRange(first: string | null, last: string | null): string {
  if (first === null || last === null) {
    return "no data";
  }
  return `${formatDay(first)} to ${formatDay(last)}`;
}

function coverageTitle(meta: MetaResponse): string {
  const forecasts = describeRange(
    meta.forecasts.first_target_time,
    meta.forecasts.last_target_time,
  );
  const actuals = describeRange(meta.actuals.first_target_time, meta.actuals.last_target_time);
  return `Forecasts ${forecasts}; actuals ${actuals}`;
}

export function CoverageBadge() {
  const meta = useMetaQuery();

  if (meta.isError) {
    return <StatusBadge tone="danger" label="Data coverage unavailable" />;
  }
  if (meta.isSuccess) {
    return (
      <StatusBadge
        tone="neutral"
        label={`Data as of ${formatDay(meta.data.ingested_at)}`}
        title={coverageTitle(meta.data)}
      />
    );
  }
  return <StatusBadge tone="neutral" label="Loading data coverage" />;
}
