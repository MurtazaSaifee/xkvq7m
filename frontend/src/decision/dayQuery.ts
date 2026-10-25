/**
 * The selected delivery day lives in the ``day`` query parameter, beside ``cutoff`` and ``view``, so
 * a link to a day's Decision view can be shared. The helpers keep every other parameter as it is.
 */

export const DAY_QUERY_PARAM = "day";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

/** The delivery day named in a query string as YYYY-MM-DD, or null when none is named. */
export function dayFromSearch(search: string): string | null {
  const value = new URLSearchParams(search).get(DAY_QUERY_PARAM);
  return value !== null && ISO_DAY.test(value) ? value : null;
}

/** The query string with ``day`` set, replacing any day already named. */
export function searchForDay(search: string, day: string): string {
  const params = new URLSearchParams(search);
  params.set(DAY_QUERY_PARAM, day);
  return `?${params.toString()}`;
}
