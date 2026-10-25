import type { WorstDay } from "../../api/client";
import { searchForDay } from "../../decision/dayQuery";
import { formatDay, formatMwh, formatSignedMwh } from "../../format";
import { searchForView } from "../../views/views";

/** The Decision view for one delivery day, as a link that keeps the shared cutoff. */
function decisionHref(day: string): string {
  const search = searchForView(searchForDay(window.location.search, day), "decision");
  return `${window.location.pathname}${search}`;
}

/**
 * The delivery days with the largest energy error, ranked by its size either way. Each row opens the
 * Decision view for its day. The day's link is a real link, so the view can be shared; a click
 * anywhere else in the row opens the same day.
 */
export function WorstDaysTable({
  worstDays,
  onOpenDay,
}: {
  worstDays: WorstDay[];
  onOpenDay: (day: string) => void;
}) {
  if (worstDays.length === 0) {
    return (
      <p className="text-sm text-muted">
        No delivery day has a measured hour at this cutoff.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm tabular-nums">
        <thead className="border-b border-rule text-muted">
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">Delivery day</th>
            <th scope="col" className="py-2 pr-4 text-right font-medium">Energy error</th>
            <th scope="col" className="hidden py-2 pr-4 text-right font-medium sm:table-cell">Forecast</th>
            <th scope="col" className="hidden py-2 pr-4 text-right font-medium sm:table-cell">Actual</th>
            <th scope="col" className="py-2 text-right font-medium">Measured hours</th>
          </tr>
        </thead>
        <tbody>
          {worstDays.map((worst) => (
            <tr
              key={worst.delivery_day}
              onClick={() => onOpenDay(worst.delivery_day)}
              className="cursor-pointer border-b border-rule hover:bg-surface"
            >
              <td className="py-2 pr-4">
                <a
                  href={decisionHref(worst.delivery_day)}
                  onClick={(event) => {
                    // The row handles the click, so the link must not open the day a second time.
                    event.preventDefault();
                    event.stopPropagation();
                    onOpenDay(worst.delivery_day);
                  }}
                  className="font-medium text-ink underline decoration-rule underline-offset-4 hover:decoration-forecast focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forecast"
                >
                  {formatDay(worst.delivery_day)}
                </a>
              </td>
              <td className="whitespace-nowrap py-2 pr-4 text-right font-medium text-ink">
                {formatSignedMwh(worst.error_mwh)}
              </td>
              <td className="hidden whitespace-nowrap py-2 pr-4 text-right text-muted sm:table-cell">
                {formatMwh(worst.forecast_mwh)}
              </td>
              <td className="hidden whitespace-nowrap py-2 pr-4 text-right text-muted sm:table-cell">
                {formatMwh(worst.actual_mwh)}
              </td>
              <td className="py-2 text-right text-muted">{worst.paired_hours}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
