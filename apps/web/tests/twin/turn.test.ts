import { describe, expect, it } from "vitest";
import { sawDoneAfter, streamEndedEarly } from "@/twin/turn";

describe("sawDoneAfter", () => {
  it("flips to true on a done frame and stays true afterwards", () => {
    let seen = false;
    seen = sawDoneAfter(seen, { event: "delta", data: { text: "x" } });
    expect(seen).toBe(false);
    seen = sawDoneAfter(seen, { event: "done", data: { reply: "x" } });
    expect(seen).toBe(true);
    seen = sawDoneAfter(seen, { event: "delta", data: { text: "late" } });
    expect(seen).toBe(true);
  });

  it("ignores frames that failed to parse", () => {
    expect(sawDoneAfter(false, null)).toBe(false);
    expect(sawDoneAfter(true, null)).toBe(true);
  });

  it("is not tripped by agent_error alone", () => {
    expect(sawDoneAfter(false, { event: "agent_error", data: { code: "x", message: "y" } })).toBe(false);
  });
});

describe("streamEndedEarly", () => {
  it("is true only when the stream closed without a done frame", () => {
    expect(streamEndedEarly(false)).toBe(true);
    expect(streamEndedEarly(true)).toBe(false);
  });
});
