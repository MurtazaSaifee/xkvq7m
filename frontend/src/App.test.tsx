import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const META = {
  ingested_at: "2026-10-25T04:45:25Z",
  forecasts: {
    first_target_time: "2025-12-17T21:00:00Z",
    last_target_time: "2026-02-03T21:00:00Z",
    row_count: 21343,
  },
  actuals: {
    first_target_time: "2025-12-19T00:00:00Z",
    last_target_time: "2026-01-31T23:30:00Z",
    row_count: 2160,
  },
  excluded_forecasts: 5521,
  delivery_days: { first: "2026-01-02", last: "2026-02-01" },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Routes each API path to its own stub, and returns the fetch mock for assertions. */
function stubApi(
  routes: Record<"/api/v1/health" | "/api/v1/meta", () => Promise<Response>>,
) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const route = routes[String(input) as keyof typeof routes];
    if (!route) {
      return Promise.reject(new Error(`unexpected request to ${String(input)}`));
    }
    return route();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const healthy = () => Promise.resolve(jsonResponse({ status: "ok" }));
const metaOk = () => Promise.resolve(jsonResponse(META));

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the API as healthy when the health endpoint responds ok", async () => {
    const fetchMock = stubApi({ "/api/v1/health": healthy, "/api/v1/meta": metaOk });

    renderApp();

    expect(await screen.findByText("API healthy")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health", expect.anything());
  });

  it("shows the API as unreachable when the request fails", async () => {
    stubApi({
      "/api/v1/health": () => Promise.reject(new TypeError("Failed to fetch")),
      "/api/v1/meta": metaOk,
    });

    renderApp();

    expect(await screen.findByText("API unreachable")).toBeInTheDocument();
  });

  it("shows the data as-of date from the snapshot ingestion time", async () => {
    const fetchMock = stubApi({ "/api/v1/health": healthy, "/api/v1/meta": metaOk });

    renderApp();

    const badge = await screen.findByText("Data as of 25 Oct 2026");
    expect(badge).toHaveAttribute(
      "title",
      "Forecasts 17 Dec 2025 to 3 Feb 2026; actuals 19 Dec 2025 to 31 Jan 2026",
    );
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/meta", expect.anything());
  });

  it("says the coverage is unavailable when the snapshot is missing", async () => {
    stubApi({
      "/api/v1/health": healthy,
      "/api/v1/meta": () => Promise.resolve(jsonResponse({ detail: "missing" }, 503)),
    });

    renderApp();

    expect(await screen.findByText("Data coverage unavailable")).toBeInTheDocument();
  });
});
