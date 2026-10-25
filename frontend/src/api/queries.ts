import { useQuery } from "@tanstack/react-query";

import { fetchDecisionSnapshot, fetchHealth, fetchMeta } from "./client";

export const healthQueryKey = ["health"] as const;
export const metaQueryKey = ["meta"] as const;

export function decisionSnapshotQueryKey(deliveryDay: string, cutoff: string) {
  return ["decision-snapshot", deliveryDay, cutoff] as const;
}

// The snapshot is fixed for a given day and cutoff, so it is kept until the page is reloaded.
export function useDecisionSnapshotQuery(deliveryDay: string | null, cutoff: string) {
  return useQuery({
    queryKey: decisionSnapshotQueryKey(deliveryDay ?? "", cutoff),
    queryFn: ({ signal }) => fetchDecisionSnapshot(deliveryDay ?? "", cutoff, signal),
    enabled: deliveryDay !== null,
    staleTime: Infinity,
  });
}

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
