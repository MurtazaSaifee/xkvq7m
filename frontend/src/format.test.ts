import { describe, expect, it } from "vitest";

import {
  formatDayRange,
  formatMw,
  formatMwh,
  formatPercent,
  formatSignedMw,
  formatSignedMwh,
  formatUkTime,
  outlookSentence,
} from "./format";

describe("megawatt formatting", () => {
  it("rounds MW to whole megawatts with a thousands separator", () => {
    expect(formatMw(11283.56)).toBe("11,284 MW");
  });

  it("signs an MW value, with zero unsigned", () => {
    expect(formatSignedMw(-500)).toBe("−500 MW");
    expect(formatSignedMw(1000)).toBe("+1,000 MW");
    expect(formatSignedMw(0)).toBe("0 MW");
  });

  it("shows a percentage to one decimal place", () => {
    expect(formatPercent(18.0697)).toBe("18.1%");
    expect(formatPercent(3.5)).toBe("3.5%");
  });
});

describe("outlookSentence", () => {
  it("says which delivery day, cutoff and forecast run the view shows", () => {
    expect(
      outlookSentence({
        deliveryDay: "2026-02-01",
        decisionDay: "2026-01-31",
        cutoff: "09:20",
        runPublishTime: "2026-01-31T07:30:00Z",
      }),
    ).toBe("Wind outlook for 1 Feb as known at 09:20 on 31 Jan (07:30 run)");
  });

  it("says plainly when no forecast was published before the cutoff", () => {
    expect(
      outlookSentence({
        deliveryDay: "2026-01-02",
        decisionDay: "2026-01-01",
        cutoff: "09:20",
        runPublishTime: null,
      }),
    ).toBe("Wind outlook for 2 Jan as known at 09:20 on 1 Jan (no forecast run before the cutoff)");
  });
});

describe("number formatting", () => {
  it("rounds MWh to whole megawatt-hours with a thousands separator", () => {
    expect(formatMwh(438696.4)).toBe("438,696 MWh");
  });

  it("signs the error so over-forecast reads as positive", () => {
    expect(formatSignedMwh(74638)).toBe("+74,638 MWh");
    expect(formatSignedMwh(-4000)).toBe("−" + "4,000 MWh");
  });
});

describe("formatDayRange", () => {
  it("names a range of delivery days with the year once, at the end", () => {
    expect(formatDayRange("2026-01-02", "2026-02-01")).toBe("2 Jan to 1 Feb 2026");
  });
});

describe("formatUkTime", () => {
  it("shows an instant as UK clock time, so the cutoff reads as the desk says it", () => {
    expect(formatUkTime("2026-01-31T09:20:00Z")).toBe("09:20");
  });
});
