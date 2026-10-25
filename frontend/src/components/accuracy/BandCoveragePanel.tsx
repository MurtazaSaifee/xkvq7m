import type { AccuracyResponse } from "../../api/client";
import { formatPercent } from "../../format";
import { Figure } from "../Figure";

type BandCoverage = AccuracyResponse["band_coverage"];

const EM_DASH = "—";
const NO_BAND_TO_MEASURE = "No hour has a band to measure against";
const COVERAGE_CAPTION = "Hours whose actual generation fell inside the expected-error band.";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/**
 * Band coverage: how often the actual generation fell inside its expected-error band, with the
 * hours counted and a plain account of how the band is built.
 */
export function BandCoveragePanel({ coverage }: { coverage: BandCoverage }) {
  const counted = coverage.counted_hours;
  const outside = counted - coverage.inside_hours;
  const value =
    coverage.coverage_percent === null ? EM_DASH : formatPercent(coverage.coverage_percent);
  const caption =
    counted === 0 ? NO_BAND_TO_MEASURE : `${COVERAGE_CAPTION} The target is about 80%.`;

  return (
    <section className="space-y-4">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <Figure label="Band coverage" value={value} caption={caption} />
      </div>
      <p className="text-sm text-muted">
        Counted {plural(counted, "hour", "hours")}: {coverage.inside_hours} inside the band and{" "}
        {outside} outside it.
      </p>
      <p className="text-sm text-muted">
        Left out: {plural(coverage.excluded_no_band, "hour with no band", "hours with no band")}.
      </p>
      <p className="text-sm text-muted">
        Each day's band is the P10 to P90 of the forecast errors over the {coverage.lookback_days}{" "}
        delivery days before it, at this cutoff. It uses no later day.
      </p>
    </section>
  );
}
