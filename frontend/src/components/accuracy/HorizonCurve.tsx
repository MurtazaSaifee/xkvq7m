import { useMemo } from "react";

import type { AccuracyResponse } from "../../api/client";
import { buildHorizonOption } from "../../accuracy/horizonOption";
import { prefersReducedMotion } from "../../motion";
import { EChart } from "../EChart";

type Curve = AccuracyResponse["horizon_curve"];

/**
 * Error by forecast horizon: how the miss grows as a forecast looks further ahead. The shaded band
 * is the horizon range of the decision forecasts at the cutoff, so the desk can see where it sits.
 */
export function HorizonCurve({ curve, cutoff }: { curve: Curve; cutoff: string }) {
  const range = curve.decision_horizon_range_hours;
  const option = useMemo(
    () => buildHorizonOption(curve.buckets, range, cutoff, prefersReducedMotion()),
    [curve.buckets, range, cutoff],
  );
  const hasMeasurement = curve.buckets.some((bucket) => bucket.sample_count > 0);

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight text-ink">Error by forecast horizon</h2>
      <p className="text-sm text-muted">
        Every forecast for the delivery days counts, not only the decision forecasts, grouped by how
        many hours ahead it was published. The shaded band marks the horizons of the decision
        forecasts at the {cutoff} cutoff
        {range === null ? "" : `, ${range.min_hours} to ${range.max_hours} hours`}.
      </p>
      {hasMeasurement ? (
        <EChart
          option={option}
          label={`Forecast error by horizon, MAE and bias in MW, with the decision range at the ${cutoff} cutoff`}
        />
      ) : (
        <p className="text-sm text-muted">No forecast has both a value and an actual to measure.</p>
      )}
      <p className="text-sm text-muted">
        {curve.excluded_no_actual === 1
          ? "1 forecast is left out because its hour has no actual."
          : `${curve.excluded_no_actual} forecasts are left out because their hour has no actual.`}
      </p>
    </section>
  );
}
