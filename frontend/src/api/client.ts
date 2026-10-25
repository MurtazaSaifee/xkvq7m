import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type MetaResponse = components["schemas"]["MetaResponse"];
export type DecisionSnapshot = components["schemas"]["DecisionSnapshotResponse"];
export type DecisionHour = components["schemas"]["HourResponse"];
export type HalfHourActual = components["schemas"]["ActualResponse"];
export type DayKpis = components["schemas"]["KpisResponse"];
export type AccuracyResponse = components["schemas"]["AccuracyResponse"];
export type AccuracySummary = components["schemas"]["AccuracySummaryResponse"];
export type ErrorBin = components["schemas"]["ErrorBinResponse"];
export type HeatmapCell = components["schemas"]["HeatmapCellResponse"];
export type WorstDay = components["schemas"]["WorstDayResponse"];
export type HorizonBucket = components["schemas"]["HorizonBucketResponse"];
export type HorizonRange = components["schemas"]["HorizonRangeResponse"];
export type AlignmentSensitivity = components["schemas"]["AlignmentSensitivityResponse"];
export type AlignmentMetrics = components["schemas"]["AlignmentMetricsResponse"];

/** The problem document a route returns for an error (RFC 7807). */
type ProblemBody = { title?: string; detail?: string };

/** Reads the problem detail from an error response, falling back to the status code. */
async function problemMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as ProblemBody;
    if (body.detail) {
      return body.detail;
    }
  } catch {
    // The body was not JSON; the status code is the best description left.
  }
  return fallback;
}

/**
 * GETs a JSON resource. A failed request throws the problem detail the route sent, or a message with
 * the status code when the body carries none. ``label`` names the request in that fallback message.
 */
async function getJson<T>(path: string, label: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    const fallback = `${label} failed with HTTP ${response.status}`;
    throw new Error(await problemMessage(response, fallback));
  }
  return (await response.json()) as T;
}

export function fetchDecisionSnapshot(
  deliveryDay: string,
  cutoff: string,
  signal?: AbortSignal,
): Promise<DecisionSnapshot> {
  const params = new URLSearchParams({ delivery_day: deliveryDay, cutoff });
  return getJson<DecisionSnapshot>(
    `/api/v1/decision-snapshot?${params.toString()}`,
    "Decision snapshot request",
    signal,
  );
}

export function fetchAccuracy(cutoff: string, signal?: AbortSignal): Promise<AccuracyResponse> {
  const params = new URLSearchParams({ cutoff });
  return getJson<AccuracyResponse>(
    `/api/v1/accuracy?${params.toString()}`,
    "Accuracy request",
    signal,
  );
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/v1/health", "Health check", signal);
}

export function fetchMeta(signal?: AbortSignal): Promise<MetaResponse> {
  return getJson<MetaResponse>("/api/v1/meta", "Coverage request", signal);
}
