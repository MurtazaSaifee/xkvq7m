import type { ReactNode } from "react";

import { useAccuracyQuery, useMetaQuery } from "../api/queries";
import { CUTOFF_PRESETS } from "../decision/cutoffs";
import { useDecisionCutoff } from "../decision/DecisionCutoffContext";
import { formatCount, formatDayRange } from "../format";
import { CutoffPicker } from "./CutoffPicker";
import { AlignmentSensitivityTable } from "./methodology/AlignmentSensitivityTable";

// Figures the copy states come from the API. They show a dash until the response arrives.
const EM_DASH = "—";

const METRICS: readonly [term: string, definition: string][] = [
  [
    "Forecast error",
    "Forecast minus actual generation, in MW, for each measured hour. Positive means wind was over-forecast: the desk relied on wind that did not arrive.",
  ],
  [
    "Average miss (MAE)",
    "The average size of the error, ignoring its sign. It is the typical miss.",
  ],
  [
    "Bias",
    "The average error with its sign. Positive means the forecast ran high on average.",
  ],
  [
    "Large misses (RMSE)",
    "Like the average miss, but each error is squared before averaging, so a few large misses raise it more.",
  ],
  [
    "Nine-in-ten miss (P90)",
    "The 90th percentile of the size of the error: nine times in ten the miss is under this.",
  ],
  [
    "Relative miss (nMAE)",
    "The average miss as a percentage of the average actual generation.",
  ],
];

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h3 id={id} className="text-lg font-semibold tracking-tight text-ink">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Paragraph({ children }: { children: ReactNode }) {
  return <p className="leading-relaxed text-ink">{children}</p>;
}

/**
 * The methodology panel: how every figure in the app is made, in the order a decision uses it. The
 * prose is fixed. Only the figures at the end come from the API, at the shared cutoff.
 */
export function MethodologyView() {
  const { cutoff } = useDecisionCutoff();
  const accuracy = useAccuracyQuery(cutoff);
  const meta = useMetaQuery();
  const days = meta.data?.delivery_days;
  const band = accuracy.data?.band_coverage;
  const lookbackDays = band?.lookback_days;
  const oldestBandDay = lookbackDays === undefined ? EM_DASH : `D-${lookbackDays + 1}`;

  return (
    <div className="max-w-3xl space-y-10">
      <header className="space-y-2">
        <h2 className="text-2xl font-semibold leading-snug tracking-tight text-ink">Methodology</h2>
        <p className="text-muted">
          How each figure is made, in the order a decision uses it. Terms follow the glossary. The
          sensitivity check at the end is live from the API.
        </p>
      </header>

      <Section id="methodology-scope" title="What the figures cover">
        <Paragraph>
          Decision snapshots and headline metrics cover only the delivery days{" "}
          {days ? formatDayRange(days.first, days.last) : EM_DASH}, which are bought on decisions made
          the day before.
        </Paragraph>
        <Paragraph>
          December 2025 data is used only as band warm-up. The band for each day reads only errors the
          desk already had at its decision cutoff, so the warm-up is information the desk had at
          decision time.
        </Paragraph>
        <Paragraph>
          The horizon curve deliberately includes forecasts published after the cutoff, to show what
          waiting would buy.
        </Paragraph>
      </Section>

      <Section id="methodology-data" title="Data">
        <Paragraph>
          Actual generation is Elexon&apos;s FUELHH series for national wind: half-hourly, in MW.
          Forecasts are Elexon&apos;s WINDFOR series for national wind: hourly target times, from eight
          runs a day, each stamped with its publish time.
        </Paragraph>
        {meta.data ? (
          <Paragraph>
            {formatCount(meta.data.excluded_forecasts)} forecasts were excluded for being published
            after their target time. A forecast made after its hour has started is not a forecast of
            that hour, so it is left out of the snapshot.
          </Paragraph>
        ) : null}
      </Section>

      <Section id="methodology-cutoff" title="Decision cutoff and decision forecast">
        <Paragraph>
          A decision cutoff is a UK time on the decision day, the day before delivery. The default is
          09:20, the EPEX day-ahead gate closure. The other presets follow the other auctions&apos; gate
          closures.
        </Paragraph>
        <ul aria-label="Cutoff presets" className="list-inside list-disc text-muted">
          {CUTOFF_PRESETS.map((preset) => (
            <li key={preset.time}>{preset.label}</li>
          ))}
        </ul>
        <Paragraph>
          Any HH:MM time can also be entered. For each target hour, the decision forecast is the latest
          forecast published at or before the cutoff. A forecast published after the cutoff is ignored.
          An hour with no such forecast has no decision forecast and is left out of the metrics.
        </Paragraph>
      </Section>

      <Section id="methodology-alignment" title="Hourly alignment">
        <Paragraph>
          Forecasts are hourly and actual generation is half-hourly, so the actual for hour h is the mean
          of the half-hours starting at h:00 and h:30. If either half-hour is missing, the hour has no
          actual and is left out. The sensitivity check below tests this choice.
        </Paragraph>
      </Section>

      <Section id="methodology-metrics" title="Metrics">
        <dl aria-label="Metric definitions" className="space-y-4">
          {METRICS.map(([term, definition]) => (
            <div key={term}>
              <dt className="font-medium text-ink">{term}</dt>
              <dd className="text-muted">{definition}</dd>
            </div>
          ))}
        </dl>
        <Paragraph>
          MAPE is not shown. It divides each miss by the actual generation, so any hour with little wind
          would dominate the figure. nMAE divides by the average actual generation for the period
          instead, so it stays stable.
        </Paragraph>
      </Section>

      <Section id="methodology-band" title="Expected-error band and band coverage">
        <Paragraph>
          For a delivery day D, the expected-error band is the P10 and P90 of the hourly
          decision-forecast errors over the {lookbackDays ?? EM_DASH} delivery days that end two days
          before it ({oldestBandDay} to D-2), at the same cutoff. The errors are pooled hour by hour,
          not averaged by day.
        </Paragraph>
        <Paragraph>
          Nothing from D-1 or later is used. The decision day is still in progress at the cutoff, so its
          actuals are incomplete. A day with fewer than {band?.min_history_days ?? EM_DASH} days with
          errors gets no band. The earliest days have less history, because the actuals start on 19
          December 2025.
        </Paragraph>
        <Paragraph>
          For a forecast F, the band for its actual runs from F minus P90 to F minus P10. Band coverage
          is the share of counted hours whose actual fell inside that band. The target is about 80%, the
          share a P10 to P90 band should contain.
        </Paragraph>
      </Section>

      <Section id="methodology-horizon" title="Error by horizon">
        <Paragraph>
          The forecast horizon is the time from a forecast&apos;s publish time to its target time. The
          horizon curve groups every forecast in scope into one-hour buckets, so bucket k holds horizons
          above k−1 and up to k hours. A horizon of exactly zero joins bucket 1. For example, a horizon
          of 0.5 hours is in bucket 1 and a horizon of 1.5 hours is in bucket 2.
        </Paragraph>
        <Paragraph>
          Every forecast counts here, not only decision forecasts. The shaded range on the chart marks
          the horizons of the decision forecasts at the cutoff.
        </Paragraph>
      </Section>

      <Section id="methodology-sensitivity" title="Alignment sensitivity check (live)">
        <Paragraph>
          The headline metrics recomputed with the other alignment rule: each hour is compared with the
          half-hour starting at h:00 alone. Both use the same decision forecasts, so any difference
          comes from the rule. <code className="text-sm">make sensitivity</code> prints the same table
          for the README.
        </Paragraph>
        <CutoffPicker />
        {accuracy.isError ? (
          <p role="alert" className="text-danger">
            Could not load the sensitivity figures: {accuracy.error.message}
          </p>
        ) : !accuracy.data ? (
          <p className="text-muted">Loading the sensitivity figures for the {cutoff} cutoff.</p>
        ) : (
          <div className="space-y-4">
            <p className="text-muted">
              At the {accuracy.data.cutoff} cutoff, the decision forecasts are{" "}
              {accuracy.data.horizon_curve.decision_horizon_range_hours
                ? `${accuracy.data.horizon_curve.decision_horizon_range_hours.min_hours.toFixed(1)} to ${accuracy.data.horizon_curve.decision_horizon_range_hours.max_hours.toFixed(1)} hours`
                : "not available"}{" "}
              ahead of their target time.
            </p>
            <AlignmentSensitivityTable sensitivity={accuracy.data.alignment_sensitivity} />
          </div>
        )}
      </Section>
    </div>
  );
}
