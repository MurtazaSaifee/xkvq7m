/**
 * The views of the app. They switch in place, with no client router: the active view lives in the
 * ``view`` query parameter beside ``cutoff``. The default view leaves the parameter out, so the
 * URL stays clean and no server-side deep-link fallback is needed.
 */

export const VIEWS = [
  { id: "decision", label: "Decision" },
  { id: "accuracy", label: "Accuracy" },
  { id: "methodology", label: "Methodology" },
] as const;

export type ViewId = (typeof VIEWS)[number]["id"];

export const DEFAULT_VIEW: ViewId = "decision";

export const VIEW_QUERY_PARAM = "view";

function isViewId(value: string): value is ViewId {
  return VIEWS.some((view) => view.id === value);
}

/** The view named in a query string, or the default when it is missing or unknown. */
export function viewFromSearch(search: string): ViewId {
  const value = new URLSearchParams(search).get(VIEW_QUERY_PARAM);
  return value !== null && isViewId(value) ? value : DEFAULT_VIEW;
}

/** The query string for ``view``, keeping every other parameter as it is. "" when nothing is set. */
export function searchForView(search: string, view: ViewId): string {
  const params = new URLSearchParams(search);
  if (view === DEFAULT_VIEW) {
    params.delete(VIEW_QUERY_PARAM);
  } else {
    params.set(VIEW_QUERY_PARAM, view);
  }
  const text = params.toString();
  return text === "" ? "" : `?${text}`;
}
