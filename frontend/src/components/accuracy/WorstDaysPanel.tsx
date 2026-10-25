import type { WorstDay } from "../../api/client";
import { WorstDaysTable } from "./WorstDaysTable";

/** The worst delivery days of the scope, with a table row that opens each day's Decision view. */
export function WorstDaysPanel({
  worstDays,
  onOpenDay,
}: {
  worstDays: WorstDay[];
  onOpenDay: (day: string) => void;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight text-ink">Worst delivery days</h2>
      <p className="text-sm text-muted">
        Ranked by the size of each day's energy error, forecast minus actual, over its measured
        hours. A positive error means wind was over-forecast. Select a day to open its Decision view.
      </p>
      <WorstDaysTable worstDays={worstDays} onOpenDay={onOpenDay} />
    </section>
  );
}
