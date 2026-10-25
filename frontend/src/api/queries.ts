import { useQuery } from "@tanstack/react-query";

import { fetchHealth, fetchMeta } from "./client";

export const healthQueryKey = ["health"] as const;
export const metaQueryKey = ["meta"] as const;

export function useHealthQuery() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
  });
}

// The snapshot only changes when ingestion is re-run, so this does not need frequent polling.
export function useMetaQuery() {
  return useQuery({
    queryKey: metaQueryKey,
    queryFn: ({ signal }) => fetchMeta(signal),
    staleTime: 5 * 60_000,
  });
}
