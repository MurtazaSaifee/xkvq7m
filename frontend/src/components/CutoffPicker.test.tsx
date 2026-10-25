import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useDecisionCutoff } from "../decision/DecisionCutoffContext";
import { CutoffPicker } from "./CutoffPicker";
import { DecisionCutoffProvider } from "./DecisionCutoffProvider";

/** Shows the shared cutoff, so each test can see what the picker set. */
function SharedCutoff() {
  return <p>Shared cutoff: {useDecisionCutoff().cutoff}</p>;
}

function renderPicker() {
  return render(
    <DecisionCutoffProvider>
      <CutoffPicker />
      <SharedCutoff />
    </DecisionCutoffProvider>,
  );
}

function picker() {
  return screen.getByRole("combobox", { name: "Decision cutoff" });
}

describe("CutoffPicker", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("offers the four auction presets and a custom time, with EPEX 09:20 selected", () => {
    renderPicker();

    expect(picker()).toHaveValue("09:20");
    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual([
      "EPEX 09:20 (default)",
      "N2EX 09:50",
      "Half-hourly auction 14:30",
      "Half-hourly auction 15:30",
      "Custom time",
    ]);
  });

  it("sets the shared cutoff when a preset is chosen", () => {
    renderPicker();

    fireEvent.change(picker(), { target: { value: "09:50" } });

    expect(screen.getByText("Shared cutoff: 09:50")).toBeInTheDocument();
    expect(picker()).toHaveValue("09:50");
    expect(screen.queryByLabelText("Custom cutoff time")).not.toBeInTheDocument();
  });

  it("opens a time field for a custom cutoff, and sets the shared cutoff from it", () => {
    renderPicker();

    fireEvent.change(picker(), { target: { value: "custom" } });
    const time = screen.getByLabelText("Custom cutoff time");
    expect(time).toHaveValue("09:20");

    fireEvent.change(time, { target: { value: "01:00" } });

    expect(screen.getByText("Shared cutoff: 01:00")).toBeInTheDocument();
    expect(picker()).toHaveValue("custom");
  });

  it("keeps the last valid cutoff while the custom time is being cleared", () => {
    renderPicker();
    fireEvent.change(picker(), { target: { value: "custom" } });

    fireEvent.change(screen.getByLabelText("Custom cutoff time"), { target: { value: "" } });

    expect(screen.getByText("Shared cutoff: 09:20")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a time as HH:MM");
  });

  it("opens in custom mode when the URL names a cutoff that is not a preset", () => {
    window.history.replaceState(null, "", "/?cutoff=01:00");

    renderPicker();

    expect(picker()).toHaveValue("custom");
    expect(screen.getByLabelText("Custom cutoff time")).toHaveValue("01:00");
  });
});
