import { useMemo, useState } from "react";

import { useDecisionSnapshotQuery, useMetaQuery } from "../api/queries";
import { buildChartOption, CHART_COLORS } from "../decision/chartOption";
import { deliveryDaysBetween } from "../decision/days";
import { useDecisionCutoff } from "../decision/DecisionCutoffContext";
import { dayFromSearch, searchForDay } from "../decision/dayQuery";
import { formatDay, outlookSentence } from "../format";
import { prefersReducedMotion } from "../motion";
import { CutoffPicker } from "./CutoffPicker";
import { DeliveryDayPicker } from "./DeliveryDayPicker";
import { EChart } from "./EChart";
import { KpiTiles } from "./KpiTiles";

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
      <li className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="h-0.5 w-6"
          style={{ backgroundColor: CHART_COLORS.forecast }}
        />
        Decision forecast, hourly steps
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-px w-6" style={{ backgroundColor: CHART_COLORS.actual }} />
        Actual generation, half-hourly
      </li>
    </ul>
  );
}

/** Writes the chosen delivery day into the URL, keeping the cutoff and the view as they are. */
function writeDayToUrl(day: string) {
  const url = new URL(window.location.href);
  url.search = searchForDay(window.location.search, day);
  window.history.replaceState(window.history.state, "", url);
}

export function DecisionView() {
  const meta = useMetaQuery();
  const { cutoff } = useDecisionCutoff();
  // The day starts from the URL, so a shared link opens on the day it names.
  const [pickedDay, setPickedDay] = useState<string | null>(() =>
    dayFromSearch(window.location.search),
  );

  const deliveryDays = meta.data
    ? deliveryDaysBetween(meta.data.delivery_days.first, meta.data.delivery_days.last)
    : [];
  // A day outside the scope falls back to the latest delivery day, so the view reads as today's decision.
  const latestDay = meta.data?.delivery_days.last ?? null;
  const selectedDay =
    pickedDay !== null && deliveryDays.includes(pickedDay) ? pickedDay : latestDay;
  const snapshot = useDecisionSnapshotQuery(selectedDay, cutoff);
  const option = useMemo(
    () => (snapshot.data ? buildChartOption(snapshot.data, prefersReducedMotion()) : null),
    [snapshot.data],
  );

  if (meta.isError) {
    return (
      <p role="alert" className="text-danger">
        The delivery days could not be loaded, so the decision snapshot is unavailable.
      </p>
    );
  }

  const picker = (
    <div className="flex flex-wrap items-center gap-6">
      {selectedDay === null ? null : (
        <DeliveryDayPicker
          days={deliveryDays}
          value={selectedDay}
          onChange={(day) => {
            setPickedDay(day);
            writeDayToUrl(day);
          }}
        />
      )}
      <CutoffPicker />
    </div>
  );

  if (selectedDay === null || snapshot.isPending) {
    return (
      <section className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <p className="text-lg text-muted">
            {selectedDay === null
              ? "Loading the delivery days."
              : `Loading the decision snapshot for ${formatDay(selectedDay)}.`}
          </p>
          {picker}
        </div>
      </section>
    );
  }

  if (snapshot.isError || !snapshot.data || !option) {
    return (
      <section className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <p role="alert" className="text-lg text-danger">
            Could not load the decision snapshot: {snapshot.error?.message ?? "unknown error"}
          </p>
          {picker}
        </div>
      </section>
    );
  }

  const data = snapshot.data;
  const sentence = outlookSentence({
    deliveryDay: data.delivery_day,
    decisionDay: data.decision_day,
    cutoff: data.cutoff,
    runPublishTime: data.forecast_run_publish_time,
  });
  const noForecast = data.forecast_run_publish_time === null;

  return (
    <section className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h2 className="max-w-2xl text-2xl font-semibold leading-snug tracking-tight text-ink">
          {sentence}
        </h2>
        {picker}
      </div>

      <KpiTiles kpis={data.kpis} />

      {noForecast ? (
        <p className="text-sm text-muted">
          No forecast was published before the cutoff, so there is nothing to compare.
        </p>
      ) : null}

      <div className="space-y-3">
        <Legend />
        <EChart
          option={option}
          label={`Decision forecast against actual wind generation for ${formatDay(data.delivery_day)}`}
        />
      </div>

      <p className="text-sm text-muted">
        Times are UK clock time. Each hour's actual is the average of its two half-hours. Drag the
        slider below the chart to zoom.
      </p>
    </section>
  );
}
