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
export type HorizonBucket = components["schemas"]["HorizonBucketResponse"];
export type HorizonRange = components["schemas"]["HorizonRangeResponse"];

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

export async function fetchDecisionSnapshot(
  deliveryDay: string,
  cutoff: string,
  signal?: AbortSignal,
): Promise<DecisionSnapshot> {
  const params = new URLSearchParams({ delivery_day: deliveryDay, cutoff });
  const response = await fetch(`/api/v1/decision-snapshot?${params.toString()}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const fallback = `Decision snapshot request failed with HTTP ${response.status}`;
    throw new Error(await problemMessage(response, fallback));
  }
  return (await response.json()) as DecisionSnapshot;
}

export async function fetchAccuracy(cutoff: string, signal?: AbortSignal): Promise<AccuracyResponse> {
  const params = new URLSearchParams({ cutoff });
  const response = await fetch(`/api/v1/accuracy?${params.toString()}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const fallback = `Accuracy request failed with HTTP ${response.status}`;
    throw new Error(await problemMessage(response, fallback));
  }
  return (await response.json()) as AccuracyResponse;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health", {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

export async function fetchMeta(signal?: AbortSignal): Promise<MetaResponse> {
  const response = await fetch("/api/v1/meta", {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Coverage request failed with HTTP ${response.status}`);
  }
  return (await response.json()) as MetaResponse;
}
