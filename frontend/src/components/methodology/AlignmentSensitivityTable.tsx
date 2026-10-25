import type { AlignmentSensitivity } from "../../api/client";
import { formatCount, formatMw, formatSignedMw, formatSignedNumber } from "../../format";

const EM_DASH = "—";

interface Row {
  label: string;
  hourly: number | null;
  top: number | null;
  show: (value: number) => string;
  change: (value: number) => string;
}

const COUNT = { show: formatCount, change: formatSignedNumber };
const MW = { show: formatMw, change: formatSignedMw };

function cell(value: number | null, show: (value: number) => string): string {
  return value === null ? EM_DASH : show(value);
}

/**
 * The headline metrics under the two alignment rules, side by side, with the difference. The
 * difference is top of hour minus hourly mean, so a negative figure means the top-of-hour rule
 * reads lower.
 */
export function AlignmentSensitivityTable({
  sensitivity,
}: {
  sensitivity: AlignmentSensitivity;
}) {
  const hourly = sensitivity.hourly_mean;
  const top = sensitivity.top_of_hour;
  const rows: Row[] = [
    {
      label: "Measured hours",
      hourly: hourly.measured_hours,
      top: top.measured_hours,
      ...COUNT,
    },
    { label: "MAE", hourly: hourly.mae_mw, top: top.mae_mw, ...MW },
    { label: "Bias", hourly: hourly.bias_mw, top: top.bias_mw, ...MW },
    { label: "RMSE", hourly: hourly.rmse_mw, top: top.rmse_mw, ...MW },
  ];

  return (
    <table aria-label="Alignment sensitivity" className="w-full text-left text-sm tabular-nums">
      <thead>
        <tr className="border-b border-rule text-muted">
          <th scope="col" className="py-2 font-medium" />
          <th scope="col" className="py-2 text-right font-medium">
            Hourly mean (headline)
          </th>
          <th scope="col" className="py-2 text-right font-medium">
            Top of hour
          </th>
          <th scope="col" className="py-2 text-right font-medium">
            Difference
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const difference =
            row.hourly === null || row.top === null ? null : row.top - row.hourly;
          return (
            <tr key={row.label} className="border-b border-rule last:border-b-0">
              <th scope="row" className="py-2 font-medium text-ink">
                {row.label}
              </th>
              <td className="py-2 text-right text-ink">{cell(row.hourly, row.show)}</td>
              <td className="py-2 text-right text-ink">{cell(row.top, row.show)}</td>
              <td className="py-2 text-right text-muted">
                {cell(difference, row.change)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
