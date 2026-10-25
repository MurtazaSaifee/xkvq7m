import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DayKpis } from "../api/client";
import { KpiTiles } from "./KpiTiles";

const KPIS: DayKpis = {
  forecast_mwh: 438696,
  actual_mwh: 364058,
  error_mwh: 74638,
  paired_hours: 24,
  missing_forecast_hours: 0,
  missing_actual_hours: 0,
};

describe("KpiTiles", () => {
  it("shows forecast, actual and the signed error for the day", () => {
    render(<KpiTiles kpis={KPIS} />);

    const forecast = screen.getByRole("group", { name: "Forecast" });
    expect(within(forecast).getByText("438,696 MWh")).toBeInTheDocument();

    const actual = screen.getByRole("group", { name: "Actual" });
    expect(within(actual).getByText("364,058 MWh")).toBeInTheDocument();

    const error = screen.getByRole("group", { name: "Forecast error" });
    expect(within(error).getByText("+74,638 MWh")).toBeInTheDocument();
    expect(within(error).getByText("Over-forecast: wind came in below the forecast")).toBeVisible();
  });

  it("names the direction of an under-forecast", () => {
    render(<KpiTiles kpis={{ ...KPIS, error_mwh: -1200 }} />);

    const error = screen.getByRole("group", { name: "Forecast error" });
    expect(within(error).getByText("−1,200 MWh")).toBeInTheDocument();
    expect(within(error).getByText("Under-forecast: wind came in above the forecast")).toBeVisible();
  });

  it("states that no hour can be compared when nothing is paired", () => {
    render(
      <KpiTiles
        kpis={{
          forecast_mwh: null,
          actual_mwh: null,
          error_mwh: null,
          paired_hours: 0,
          missing_forecast_hours: 24,
          missing_actual_hours: 24,
        }}
      />,
    );

    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.getByText("No hour has both a decision forecast and an actual.")).toBeVisible();
  });

  it("reports the hours left out of the totals", () => {
    render(
      <KpiTiles
        kpis={{
          ...KPIS,
          paired_hours: 22,
          missing_forecast_hours: 2,
          missing_actual_hours: 1,
        }}
      />,
    );

    expect(
      screen.getByText("Left out: 2 hours without a decision forecast and 1 hour without an actual."),
    ).toBeVisible();
  });
});
