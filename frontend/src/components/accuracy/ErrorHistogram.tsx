import { useMemo } from "react";

import type { AccuracyResponse } from "../../api/client";
import { buildHistogramOption } from "../../accuracy/histogramOption";
import { formatDayRange } from "../../format";
import { prefersReducedMotion } from "../../motion";
import { EChart } from "../EChart";

type Histogram = AccuracyResponse["histogram"];
type DeliveryDays = AccuracyResponse["delivery_days"];

/** How often each size of forecast error occurred over the scope, in fixed-width bins. */
export function ErrorHistogram({
  histogram,
  cutoff,
  deliveryDays,
}: {
  histogram: Histogram;
  cutoff: string;
  deliveryDays: DeliveryDays;
}) {
  const option = useMemo(
    () => buildHistogramOption(histogram.bins, prefersReducedMotion()),
    [histogram.bins],
  );
  const scope = formatDayRange(deliveryDays.first, deliveryDays.last);

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight text-ink">Forecast error distribution</h2>
      <p className="text-sm text-muted">
        Each bar counts the hours whose error fell in a {histogram.bin_width_mw} MW range. Bars to
        the left are under-forecasts (wind came in above the forecast); bars to the right are
        over-forecasts.
      </p>
      {histogram.bins.length === 0 ? (
        <p className="text-sm text-muted">
          No hour has both a decision forecast and an actual at this cutoff.
        </p>
      ) : (
        <EChart
          option={option}
          label={`Histogram of forecast error, ${scope}, at the ${cutoff} cutoff`}
        />
      )}
    </section>
  );
}
