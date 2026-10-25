import { describe, expect, it } from "vitest";

import { formatMwh, formatSignedMwh, formatUkTime, outlookSentence } from "./format";

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

describe("formatUkTime", () => {
  it("shows an instant as UK clock time, so the cutoff reads as the desk says it", () => {
    expect(formatUkTime("2026-01-31T09:20:00Z")).toBe("09:20");
  });
});
