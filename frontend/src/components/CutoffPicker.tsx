import { useState } from "react";

import { CUTOFF_PRESETS, isValidCutoff } from "../decision/cutoffs";
import { useDecisionCutoff } from "../decision/DecisionCutoffContext";

const CUSTOM = "custom";
const CONTROL_CLASS =
  "rounded-md border border-rule bg-surface px-3 py-1.5 font-medium text-ink tabular-nums focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forecast";

/** Picks the decision cutoff from the auction presets, or a custom time of day. */
export function CutoffPicker() {
  const { cutoff, setCutoff } = useDecisionCutoff();
  const [customChosen, setCustomChosen] = useState(false);
  // The custom field keeps its own text, so a half-typed time does not reset while it is typed.
  const [draft, setDraft] = useState(cutoff);

  const isPreset = CUTOFF_PRESETS.some((preset) => preset.time === cutoff);
  const isCustom = customChosen || !isPreset;
  const draftIsValid = isValidCutoff(draft);

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
      <span aria-hidden="true">Decision cutoff</span>
      <select
        aria-label="Decision cutoff"
        value={isCustom ? CUSTOM : cutoff}
        onChange={(event) => {
          const next = event.target.value;
          if (next === CUSTOM) {
            setCustomChosen(true);
            setDraft(cutoff);
          } else {
            setCustomChosen(false);
            setDraft(next);
            setCutoff(next);
          }
        }}
        className={CONTROL_CLASS}
      >
        {CUTOFF_PRESETS.map((preset) => (
          <option key={preset.time} value={preset.time}>
            {preset.label}
          </option>
        ))}
        <option value={CUSTOM}>Custom time</option>
      </select>
      {isCustom ? (
        <>
          <input
            type="time"
            aria-label="Custom cutoff time"
            aria-invalid={!draftIsValid}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setCutoff(event.target.value);
            }}
            className={CONTROL_CLASS}
          />
          {draftIsValid ? null : (
            <p role="alert" className="text-danger">
              Enter a time as HH:MM.
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}
