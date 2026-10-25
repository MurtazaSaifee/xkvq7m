import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "./client";

export const healthQueryKey = ["health"] as const;

export function useHealthQuery() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
  });
}
