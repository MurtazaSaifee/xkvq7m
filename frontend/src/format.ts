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
