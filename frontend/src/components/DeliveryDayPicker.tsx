import { deliveryDayLabel } from "../decision/days";

export function DeliveryDayPicker({
  days,
  value,
  onChange,
}: {
  days: string[];
  value: string;
  onChange: (day: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 text-sm text-muted">
      <span aria-hidden="true">Delivery day</span>
      <select
        aria-label="Delivery day"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-rule bg-surface px-3 py-1.5 font-medium text-ink tabular-nums focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forecast"
      >
        {days.map((day) => (
          <option key={day} value={day}>
            {deliveryDayLabel(day)}
          </option>
        ))}
      </select>
    </div>
  );
}
