/** The decision cutoff: a UK time of day on the decision day, written HH:MM. */

export const DEFAULT_CUTOFF = "09:20";

/** The same pattern the API accepts, so a value that passes here is never rejected by the API. */
const CUTOFF_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

export const CUTOFF_QUERY_PARAM = "cutoff";

export interface CutoffPreset {
  time: string;
  label: string;
}

/** The auctions a desk decides against, in the order the picker lists them. */
export const CUTOFF_PRESETS: readonly CutoffPreset[] = [
  { time: DEFAULT_CUTOFF, label: "EPEX 09:20 (default)" },
  { time: "09:50", label: "N2EX 09:50" },
  { time: "14:30", label: "Half-hourly auction 14:30" },
  { time: "15:30", label: "Half-hourly auction 15:30" },
];

export function isValidCutoff(value: string): boolean {
  return CUTOFF_PATTERN.test(value);
}

/** The cutoff named in a query string, or the default when it is missing or not HH:MM. */
export function cutoffFromSearch(search: string): string {
  const value = new URLSearchParams(search).get(CUTOFF_QUERY_PARAM);
  return value !== null && isValidCutoff(value) ? value : DEFAULT_CUTOFF;
}
