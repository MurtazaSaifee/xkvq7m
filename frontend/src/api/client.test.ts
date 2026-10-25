import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAccuracy, fetchDecisionSnapshot, fetchHealth, fetchMeta } from "./client";

function problem(detail: string, status: number): Response {
  return new Response(
    JSON.stringify({ type: "about:blank", title: "Service Unavailable", status, detail, instance: "/" }),
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

function stubFetch(response: Response) {
  const fetchMock = vi.fn(() => Promise.resolve(response));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("API client errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reports the problem detail when the health check fails", async () => {
    stubFetch(problem("The API is restarting", 503));

    await expect(fetchHealth()).rejects.toThrow("The API is restarting");
  });

  it("reports the problem detail when the coverage request fails", async () => {
    stubFetch(problem("Data snapshot is not available", 503));

    await expect(fetchMeta()).rejects.toThrow("Data snapshot is not available");
  });

  it("reports the problem detail for the decision snapshot and the accuracy requests", async () => {
    stubFetch(problem("delivery_day must be between 2026-01-02 and 2026-02-01", 422));
    await expect(fetchDecisionSnapshot("2025-06-01", "09:20")).rejects.toThrow(
      "delivery_day must be between 2026-01-02 and 2026-02-01",
    );

    stubFetch(problem("Data snapshot is not available", 503));
    await expect(fetchAccuracy("09:20")).rejects.toThrow("Data snapshot is not available");
  });

  it("falls back to the request and status when the error body is not a problem", async () => {
    stubFetch(new Response("<html>bad gateway</html>", { status: 502 }));

    await expect(fetchMeta()).rejects.toThrow("Coverage request failed with HTTP 502");
  });

  it("names the health check in the fallback message", async () => {
    stubFetch(new Response("", { status: 500 }));

    await expect(fetchHealth()).rejects.toThrow("Health check failed with HTTP 500");
  });

  it("asks for JSON and returns the parsed body on success", async () => {
    const fetchMock = stubFetch(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchHealth()).resolves.toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health", {
      signal: undefined,
      headers: { Accept: "application/json" },
    });
  });
});
