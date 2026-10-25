import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useDecisionCutoff } from "../decision/DecisionCutoffContext";
import { DecisionCutoffProvider } from "./DecisionCutoffProvider";

/** Shows the shared cutoff and offers one button that sets it, as a view would. */
function Probe() {
  const { cutoff, setCutoff } = useDecisionCutoff();
  return (
    <div>
      <p>Cutoff: {cutoff}</p>
      <button type="button" onClick={() => setCutoff("14:30")}>
        Set 14:30
      </button>
      <button type="button" onClick={() => setCutoff("nonsense")}>
        Set nonsense
      </button>
      <button type="button" onClick={() => setCutoff("09:20")}>
        Set default
      </button>
    </div>
  );
}

function renderProbe() {
  return render(
    <DecisionCutoffProvider>
      <Probe />
    </DecisionCutoffProvider>,
  );
}

describe("DecisionCutoffProvider", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("defaults to the EPEX 09:20 cutoff when the URL names none", () => {
    renderProbe();

    expect(screen.getByText("Cutoff: 09:20")).toBeInTheDocument();
  });

  it("starts from the cutoff named in the URL", () => {
    window.history.replaceState(null, "", "/?cutoff=15:30");

    renderProbe();

    expect(screen.getByText("Cutoff: 15:30")).toBeInTheDocument();
  });

  it("starts from the default when the URL cutoff is not a valid HH:MM", () => {
    window.history.replaceState(null, "", "/?cutoff=25:00");

    renderProbe();

    expect(screen.getByText("Cutoff: 09:20")).toBeInTheDocument();
  });

  it("writes a changed cutoff into the URL so the view can be shared", () => {
    renderProbe();

    fireEvent.click(screen.getByRole("button", { name: "Set 14:30" }));

    expect(screen.getByText("Cutoff: 14:30")).toBeInTheDocument();
    expect(new URLSearchParams(window.location.search).get("cutoff")).toBe("14:30");
  });

  it("removes the parameter from the URL when the cutoff returns to the default", () => {
    window.history.replaceState(null, "", "/?cutoff=14:30");
    renderProbe();

    fireEvent.click(screen.getByRole("button", { name: "Set default" }));

    expect(screen.getByText("Cutoff: 09:20")).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });

  it("ignores a value that is not HH:MM and leaves the cutoff and URL unchanged", () => {
    window.history.replaceState(null, "", "/?cutoff=14:30");
    renderProbe();

    fireEvent.click(screen.getByRole("button", { name: "Set nonsense" }));

    expect(screen.getByText("Cutoff: 14:30")).toBeInTheDocument();
    expect(new URLSearchParams(window.location.search).get("cutoff")).toBe("14:30");
  });
});
