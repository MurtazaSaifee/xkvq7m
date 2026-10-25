import { useMemo } from "react";

import type { AccuracyResponse } from "../../api/client";
import { buildHeatmapOption } from "../../accuracy/heatmapOption";
import { formatDayRange } from "../../format";
import { prefersReducedMotion } from "../../motion";
import { EChart } from "../EChart";

type Heatmap = AccuracyResponse["heatmap"];
type DeliveryDays = AccuracyResponse["delivery_days"];

/** The decision forecast error for each UK hour of each delivery day, as a colour grid. */
export function ErrorHeatmapPanel({
  heatmap,
  cutoff,
  deliveryDays,
}: {
  heatmap: Heatmap;
  cutoff: string;
  deliveryDays: DeliveryDays;
}) {
  const option = useMemo(
    () => buildHeatmapOption(heatmap.cells, prefersReducedMotion()),
    [heatmap.cells],
  );
  const measured = heatmap.cells.some((cell) => cell.error_mw !== null);
  const scope = formatDayRange(deliveryDays.first, deliveryDays.last);

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight text-ink">Error by hour and delivery day</h2>
      <p className="text-sm text-muted">
        Each cell is the decision forecast error for one UK hour of one delivery day, in MW (forecast
        minus actual). Orange cells were over-forecast and teal cells under-forecast, and a deeper
        colour is a bigger miss. Blank cells could not be measured.
      </p>
      {measured ? (
        <EChart
          option={option}
          label={`Heatmap of decision forecast error by delivery day and UK hour, ${scope}, at the ${cutoff} cutoff`}
        />
      ) : (
        <p className="text-sm text-muted">No cell can be measured at this cutoff, so there is no grid.</p>
      )}
    </section>
  );
}
