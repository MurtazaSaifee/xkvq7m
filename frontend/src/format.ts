// Delivery days are UK calendar days with no time of day, so they are formatted in UTC to avoid
// shifting. Instants are shown as UK clock time, since the cutoff is a UK time.

const dayFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

const ukClockFormat = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Europe/London",
});

const numberFormat = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

/** "1 Feb" for a delivery day given as YYYY-MM-DD. */
export function formatDay(isoDay: string): string {
  return dayFormat.format(new Date(`${isoDay}T00:00:00Z`));
}

/** "2 Jan to 1 Feb 2026" for a range of delivery days, with the year given once. */
export function formatDayRange(firstDay: string, lastDay: string): string {
  return `${formatDay(firstDay)} to ${formatDay(lastDay)} ${lastDay.slice(0, 4)}`;
}

/** "09:20" for an instant, in UK clock time. */
export function formatUkTime(isoInstant: string): string {
  return ukClockFormat.format(new Date(isoInstant));
}

/** Whole MWh with a thousands separator, e.g. "438,696 MWh". */
export function formatMwh(value: number): string {
  return `${numberFormat.format(Math.round(value))} MWh`;
}

/** A signed MWh value: "+74,638 MWh" or "−4,000 MWh". Zero has no sign. */
export function formatSignedMwh(value: number): string {
  const rounded = Math.round(value);
  if (rounded === 0) {
    return formatMwh(0);
  }
  const sign = rounded > 0 ? "+" : "−";
  return `${sign}${numberFormat.format(Math.abs(rounded))} MWh`;
}

/** A whole count with a thousands separator, e.g. "5,521". */
export function formatCount(value: number): string {
  return numberFormat.format(value);
}

/** Whole MW with a thousands separator, e.g. "11,284 MW". */
export function formatMw(value: number): string {
  return `${numberFormat.format(Math.round(value))} MW`;
}

/** A range of MW, low to high, with the unit once: "11,100–16,800 MW". */
export function formatMwRange(low: number, high: number): string {
  return `${numberFormat.format(Math.round(low))}–${formatMw(high)}`;
}

/** A signed whole number: "+500", "−500" or "0". Used for error values, which are signed. */
export function formatSignedNumber(value: number): string {
  const rounded = Math.round(value);
  if (rounded === 0) {
    return "0";
  }
  const sign = rounded > 0 ? "+" : "−";
  return `${sign}${numberFormat.format(Math.abs(rounded))}`;
}

/** A signed MW value: "+1,000 MW" or "−500 MW". Zero has no sign. */
export function formatSignedMw(value: number): string {
  return Math.round(value) === 0 ? formatMw(0) : `${formatSignedNumber(value)} MW`;
}

const percentFormat = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** A percentage to one decimal place, e.g. "18.1%". The input is already in percent. */
export function formatPercent(value: number): string {
  return `${percentFormat.format(value)}%`;
}

/** A difference between two percentages, in points to one decimal place: "+0.3 pp" or "−0.2 pp". */
export function formatSignedPercentPoints(value: number): string {
  const tenths = Math.round(value * 10) / 10;
  if (tenths === 0) {
    return `${percentFormat.format(0)} pp`;
  }
  const sign = tenths > 0 ? "+" : "−";
  return `${sign}${percentFormat.format(Math.abs(tenths))} pp`;
}

export interface OutlookFacts {
  deliveryDay: string;
  decisionDay: string;
  cutoff: string;
  runPublishTime: string | null;
}

/** The sentence that states what the trader is looking at. */
export function outlookSentence(facts: OutlookFacts): string {
  const run =
    facts.runPublishTime === null
      ? "no forecast run before the cutoff"
      : `${formatUkTime(facts.runPublishTime)} run`;
  return `Wind outlook for ${formatDay(facts.deliveryDay)} as known at ${facts.cutoff} on ${formatDay(facts.decisionDay)} (${run})`;
}
