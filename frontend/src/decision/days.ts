import { formatDay } from "../format";

const DAY_MS = 24 * 60 * 60 * 1000;

const weekdayFormat = new Intl.DateTimeFormat("en-GB", { weekday: "short", timeZone: "UTC" });

/** Every delivery day from ``first`` to ``last`` inclusive, as YYYY-MM-DD. */
export function deliveryDaysBetween(first: string, last: string): string[] {
  const end = Date.parse(`${last}T00:00:00Z`);
  const days: string[] = [];
  for (let time = Date.parse(`${first}T00:00:00Z`); time <= end; time += DAY_MS) {
    days.push(new Date(time).toISOString().slice(0, 10));
  }
  return days;
}

/** "Sun 1 Feb 2026", for the picker. */
export function deliveryDayLabel(isoDay: string): string {
  const weekday = weekdayFormat.format(new Date(`${isoDay}T00:00:00Z`));
  return `${weekday} ${formatDay(isoDay)} ${isoDay.slice(0, 4)}`;
}
