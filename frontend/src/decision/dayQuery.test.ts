import { describe, expect, it } from "vitest";

import { dayFromSearch, searchForDay } from "./dayQuery";

describe("dayFromSearch", () => {
  it("reads the delivery day named in the day parameter", () => {
    expect(dayFromSearch("?day=2026-01-15")).toBe("2026-01-15");
    expect(dayFromSearch("?cutoff=14:30&day=2026-01-15")).toBe("2026-01-15");
  });

  it("is null when no day is named, or the value is not a calendar date", () => {
    expect(dayFromSearch("")).toBeNull();
    expect(dayFromSearch("?cutoff=14:30")).toBeNull();
    expect(dayFromSearch("?day=15-01-2026")).toBeNull();
    expect(dayFromSearch("?day=2026-1-5")).toBeNull();
  });
});

describe("searchForDay", () => {
  it("names the day in the query string, keeping the cutoff and the view", () => {
    const params = new URLSearchParams(searchForDay("?view=accuracy&cutoff=14:30", "2026-01-15"));

    expect(params.get("day")).toBe("2026-01-15");
    expect(params.get("cutoff")).toBe("14:30");
    expect(params.get("view")).toBe("accuracy");
  });

  it("replaces a day that was already named", () => {
    const params = new URLSearchParams(searchForDay("?day=2026-01-02", "2026-01-15"));

    expect(params.getAll("day")).toEqual(["2026-01-15"]);
  });
});
