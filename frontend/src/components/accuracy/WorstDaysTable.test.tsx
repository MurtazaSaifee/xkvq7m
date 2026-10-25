import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorstDay } from "../../api/client";
import { viewFromSearch } from "../../views/views";
import { WorstDaysTable } from "./WorstDaysTable";

const WORST_DAYS: WorstDay[] = [
  {
    delivery_day: "2026-01-03",
    error_mwh: -7200,
    forecast_mwh: 237600,
    actual_mwh: 244800,
    paired_hours: 24,
  },
  {
    delivery_day: "2026-01-19",
    error_mwh: 5400,
    forecast_mwh: 300000,
    actual_mwh: 294600,
    paired_hours: 23,
  },
];

describe("WorstDaysTable", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("lists each day with its signed energy error and the energy behind it", () => {
    render(<WorstDaysTable worstDays={WORST_DAYS} onOpenDay={() => {}} />);

    const first = screen.getByRole("row", { name: /3 Jan/ });
    expect(within(first).getByText("−7,200 MWh")).toBeInTheDocument();
    expect(within(first).getByText("237,600 MWh")).toBeInTheDocument();
    expect(within(first).getByText("244,800 MWh")).toBeInTheDocument();
    expect(within(first).getByText("24")).toBeInTheDocument();

    const second = screen.getByRole("row", { name: /19 Jan/ });
    expect(within(second).getByText("+5,400 MWh")).toBeInTheDocument();
    expect(within(second).getByText("23")).toBeInTheDocument();
  });

  it("opens the Decision view for a day when its link is followed", () => {
    const onOpenDay = vi.fn();
    render(<WorstDaysTable worstDays={WORST_DAYS} onOpenDay={onOpenDay} />);

    fireEvent.click(screen.getByRole("link", { name: "3 Jan" }));

    expect(onOpenDay).toHaveBeenCalledTimes(1);
    expect(onOpenDay).toHaveBeenCalledWith("2026-01-03");
  });

  it("opens the Decision view when anywhere in the row is clicked, and only once per click", () => {
    const onOpenDay = vi.fn();
    render(<WorstDaysTable worstDays={WORST_DAYS} onOpenDay={onOpenDay} />);

    fireEvent.click(within(screen.getByRole("row", { name: /19 Jan/ })).getByText("294,600 MWh"));

    expect(onOpenDay).toHaveBeenCalledTimes(1);
    expect(onOpenDay).toHaveBeenCalledWith("2026-01-19");
  });

  it("links each day to the Decision view for that day, so the link can be shared", () => {
    window.history.replaceState(null, "", "/?cutoff=14:30");
    render(<WorstDaysTable worstDays={WORST_DAYS} onOpenDay={() => {}} />);

    const link = screen.getByRole("link", { name: "3 Jan" });
    const url = new URL(link.getAttribute("href") ?? "", "http://localhost");
    // The Decision view is the default, so its link leaves the view parameter out.
    expect(viewFromSearch(url.search)).toBe("decision");
    expect(url.searchParams.get("day")).toBe("2026-01-03");
    expect(url.searchParams.get("cutoff")).toBe("14:30");
  });

  it("says plainly when no day has a measured hour to rank", () => {
    render(<WorstDaysTable worstDays={[]} onOpenDay={() => {}} />);

    expect(
      screen.getByText("No delivery day has a measured hour at this cutoff."),
    ).toBeInTheDocument();
  });
});
