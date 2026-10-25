import { createContext, useContext } from "react";

export interface DecisionCutoffState {
  /** The shared decision cutoff, HH:MM UK time on the decision day. */
  cutoff: string;
  /** Sets the cutoff. A value that is not HH:MM is ignored. */
  setCutoff: (cutoff: string) => void;
}

export const DecisionCutoffContext = createContext<DecisionCutoffState | null>(null);

/** The cutoff shared by every view that compares against it, such as the Decision and Accuracy views. */
export function useDecisionCutoff(): DecisionCutoffState {
  const state = useContext(DecisionCutoffContext);
  if (state === null) {
    throw new Error("useDecisionCutoff must be used inside a DecisionCutoffProvider");
  }
  return state;
}
