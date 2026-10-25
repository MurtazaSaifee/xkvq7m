import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];

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
