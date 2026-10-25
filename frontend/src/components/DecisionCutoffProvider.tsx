import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  cutoffFromSearch,
  CUTOFF_QUERY_PARAM,
  DEFAULT_CUTOFF,
  isValidCutoff,
} from "../decision/cutoffs";
import { DecisionCutoffContext, type DecisionCutoffState } from "../decision/DecisionCutoffContext";

/**
 * Holds the decision cutoff for the whole app. It starts from the ``cutoff`` query parameter, so a
 * view can be shared, and writes it back whenever it changes. The default leaves the URL clean.
 */
export function DecisionCutoffProvider({ children }: { children: ReactNode }) {
  const [cutoff, setCutoffState] = useState(() => cutoffFromSearch(window.location.search));

  useEffect(() => {
    const url = new URL(window.location.href);
    if (cutoff === DEFAULT_CUTOFF) {
      url.searchParams.delete(CUTOFF_QUERY_PARAM);
    } else {
      url.searchParams.set(CUTOFF_QUERY_PARAM, cutoff);
    }
    window.history.replaceState(window.history.state, "", url);
  }, [cutoff]);

  const value = useMemo<DecisionCutoffState>(
    () => ({
      cutoff,
      setCutoff: (next) => {
        if (isValidCutoff(next)) {
          setCutoffState(next);
        }
      },
    }),
    [cutoff],
  );

  return <DecisionCutoffContext.Provider value={value}>{children}</DecisionCutoffContext.Provider>;
}
