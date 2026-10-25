import { useAccuracyQuery } from "../api/queries";
import { useDecisionCutoff } from "../decision/DecisionCutoffContext";
import { formatDayRange } from "../format";
import { CutoffPicker } from "./CutoffPicker";
import { ErrorHistogram } from "./accuracy/ErrorHistogram";
import { HeadlineMetrics } from "./accuracy/HeadlineMetrics";

/**
 * The Accuracy view: how accurate the decision forecasts were across every delivery day in scope,
 * at the shared cutoff. The view is a layout of independent panels. A new panel is a new file under
 * ``accuracy/`` and one line in the layout below.
 */
export function AccuracyView() {
  const { cutoff } = useDecisionCutoff();
  const accuracy = useAccuracyQuery(cutoff);

  if (accuracy.isError) {
    return (
      <section className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <p role="alert" className="text-lg text-danger">
            Could not load the accuracy figures: {accuracy.error.message}
          </p>
          <CutoffPicker />
        </div>
      </section>
    );
  }

  if (!accuracy.data) {
    return (
      <section className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <p className="text-lg text-muted">
            Loading the accuracy figures for the {cutoff} cutoff.
          </p>
          <CutoffPicker />
        </div>
      </section>
    );
  }

  const data = accuracy.data;
  return (
    <section className="space-y-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h2 className="max-w-2xl text-2xl font-semibold leading-snug tracking-tight text-ink">
          Decision forecast accuracy, {formatDayRange(data.delivery_days.first, data.delivery_days.last)}, at the {data.cutoff} cutoff
        </h2>
        <CutoffPicker />
      </div>

      <HeadlineMetrics summary={data.summary} deliveryDays={data.delivery_days} />

      <ErrorHistogram
        histogram={data.histogram}
        cutoff={data.cutoff}
        deliveryDays={data.delivery_days}
      />
    </section>
  );
}
