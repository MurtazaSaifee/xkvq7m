import { describe, expect, it } from "vitest";

import { DEFAULT_VIEW, searchForView, VIEWS, viewFromSearch } from "./views";

describe("viewFromSearch", () => {
  it("opens the Decision view when no view is named", () => {
    expect(viewFromSearch("")).toBe("decision");
    expect(viewFromSearch("?cutoff=14:30")).toBe("decision");
  });

  it("reads the Accuracy view from the view parameter, beside the cutoff", () => {
    expect(viewFromSearch("?view=accuracy")).toBe("accuracy");
    expect(viewFromSearch("?cutoff=14:30&view=accuracy")).toBe("accuracy");
  });

  it("reads the Methodology view from the view parameter", () => {
    expect(viewFromSearch("?view=methodology")).toBe("methodology");
    expect(viewFromSearch("?cutoff=14:30&view=methodology")).toBe("methodology");
  });

  it("falls back to the default view for an unknown name", () => {
    expect(viewFromSearch("?view=heatmap")).toBe(DEFAULT_VIEW);
  });

  it("lists the Decision, Accuracy and Methodology views in that order", () => {
    expect(VIEWS.map((view) => view.label)).toEqual(["Decision", "Accuracy", "Methodology"]);
  });
});

describe("searchForView", () => {
  it("names the view in the query string, leaving the cutoff alone", () => {
    const search = searchForView("?cutoff=14:30", "accuracy");
    const params = new URLSearchParams(search);

    expect(params.get("view")).toBe("accuracy");
    expect(params.get("cutoff")).toBe("14:30");
  });

  it("drops the view parameter for the default view so the URL stays clean", () => {
    expect(searchForView("?view=accuracy", "decision")).toBe("");
    expect(searchForView("?view=accuracy&cutoff=14:30", "decision")).toBe("?cutoff=14%3A30");
  });
});
