import { describe, expect, it } from "vitest";

import { CUTOFF_PRESETS, cutoffFromSearch, DEFAULT_CUTOFF, isValidCutoff } from "./cutoffs";

describe("isValidCutoff", () => {
  it.each(["00:00", "09:20", "14:30", "23:59"])("accepts %s", (value) => {
    expect(isValidCutoff(value)).toBe(true);
  });

  it.each(["9:20", "24:00", "09:60", "0920", "09:20:00", "", "noon"])("rejects %j", (value) => {
    expect(isValidCutoff(value)).toBe(false);
  });
});

describe("CUTOFF_PRESETS", () => {
  it("offers the four auctions the desk trades against, with EPEX 09:20 as the default", () => {
    expect(CUTOFF_PRESETS.map((preset) => preset.time)).toEqual([
      "09:20",
      "09:50",
      "14:30",
      "15:30",
    ]);
    expect(DEFAULT_CUTOFF).toBe("09:20");
    expect(CUTOFF_PRESETS[0]?.time).toBe(DEFAULT_CUTOFF);
  });
});

describe("cutoffFromSearch", () => {
  it("uses the default when the URL has no cutoff", () => {
    expect(cutoffFromSearch("")).toBe(DEFAULT_CUTOFF);
  });

  it("reads a valid cutoff from the query string", () => {
    expect(cutoffFromSearch("?cutoff=14:30")).toBe("14:30");
  });

  it("falls back to the default for a cutoff that is not HH:MM", () => {
    expect(cutoffFromSearch("?cutoff=2pm")).toBe(DEFAULT_CUTOFF);
    expect(cutoffFromSearch("?cutoff=25:00")).toBe(DEFAULT_CUTOFF);
  });
});
