import { describe, expect, it } from "vitest";
import {
  MAX_USER_TURNS,
  canSend,
  httpErrorText,
  initialState,
  reducer,
  statusFor,
  userTurns,
  type TwinState,
} from "@/twin/state";

describe("reducer: open/close", () => {
  it("open sets open to true", () => {
    expect(reducer(initialState, { type: "open" }).open).toBe(true);
  });

  it("close sets open to false", () => {
    const opened = reducer(initialState, { type: "open" });
    expect(reducer(opened, { type: "close" }).open).toBe(false);
  });
});

describe("reducer: send", () => {
  it("appends a user message and starts a pending reply", () => {
    const next = reducer(initialState, { type: "send", text: "hi" });
    expect(next.messages).toEqual([{ role: "user", text: "hi" }]);
    expect(next.pending).toEqual({ text: "", cards: [] });
    expect(next.error).toBeNull();
  });

  it("clears any previous error", () => {
    const withError = reducer(initialState, {
      type: "fail",
      text: "oops",
      retryable: true,
    });
    const next = reducer(withError, { type: "send", text: "again" });
    expect(next.error).toBeNull();
  });

  it("does not mutate the original state", () => {
    const before = JSON.parse(JSON.stringify(initialState));
    reducer(initialState, { type: "send", text: "hi" });
    expect(initialState).toEqual(before);
  });
});

describe("reducer: frame - delta", () => {
  it("appends text to the pending reply", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "frame", event: "delta", data: { text: "Hello" } });
    const next2 = reducer(next, { type: "frame", event: "delta", data: { text: " there" } });
    expect(next2.pending?.text).toBe("Hello there");
  });
});

describe("reducer: frame - project", () => {
  it("appends a project card derived from slug/title/summary, ignoring url", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, {
      type: "frame",
      event: "project",
      data: { slug: "twin", title: "Digital Twin", summary: "It's me.", url: "https://x/y" },
    });
    expect(next.pending?.cards).toEqual([
      { slug: "twin", title: "Digital Twin", summary: "It's me." },
    ]);
  });

  it("appends multiple cards across frames", () => {
    let state = reducer(initialState, { type: "send", text: "hi" });
    state = reducer(state, {
      type: "frame",
      event: "project",
      data: { slug: "a", title: "A", summary: "a" },
    });
    state = reducer(state, {
      type: "frame",
      event: "project",
      data: { slug: "b", title: "B", summary: "b" },
    });
    expect(state.pending?.cards.map((c) => c.slug)).toEqual(["a", "b"]);
  });
});

describe("reducer: frame - step/tool status", () => {
  it("sets status from a step frame", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "frame", event: "step", data: { phase: "thinking" } });
    expect(next.status).toBe("thinking");
  });

  it("sets status from a tool frame", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "frame", event: "tool", data: { label: "Search" } });
    expect(next.status).toBe("search");
  });
});

describe("reducer: frame - tool_result and unknown events", () => {
  it("tool_result leaves state unchanged", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "frame", event: "tool_result", data: { ok: true } });
    expect(next).toEqual(sent);
  });

  it("unknown event leaves state unchanged", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "frame", event: "mystery", data: {} });
    expect(next).toEqual(sent);
  });
});

describe("reducer: frame - done", () => {
  it("finalizes the pending reply into a message using reply text, with cards, and clears status/pending", () => {
    let state = reducer(initialState, { type: "send", text: "hi" });
    state = reducer(state, { type: "frame", event: "delta", data: { text: "draft" } });
    state = reducer(state, {
      type: "frame",
      event: "project",
      data: { slug: "twin", title: "Twin", summary: "s" },
    });
    state = reducer(state, { type: "frame", event: "step", data: { phase: "thinking" } });
    state = reducer(state, { type: "frame", event: "done", data: { reply: "Final answer", rounds: 1 } });

    expect(state.pending).toBeNull();
    expect(state.status).toBeNull();
    expect(state.messages[1]).toEqual({
      role: "assistant",
      text: "Final answer",
      cards: [{ slug: "twin", title: "Twin", summary: "s" }],
    });
  });
});

describe("reducer: frame - agent_error", () => {
  it("finalizes the pending reply using the error message", () => {
    let state = reducer(initialState, { type: "send", text: "hi" });
    state = reducer(state, {
      type: "frame",
      event: "agent_error",
      data: { code: "deflect", message: "I'll pass that along to Adam." },
    });
    expect(state.pending).toBeNull();
    expect(state.messages[1]).toEqual({
      role: "assistant",
      text: "I'll pass that along to Adam.",
      cards: [],
    });
  });
});

describe("reducer: fail", () => {
  it("drops pending and sets an error", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "fail", text: "Couldn't reach the twin.", retryable: true });
    expect(next.pending).toBeNull();
    expect(next.error).toEqual({
      text: "Couldn't reach the twin.",
      retryable: true,
      retryAfter: undefined,
      cap: undefined,
    });
  });

  it("keeps the user message in the transcript so retry can resend it", () => {
    const sent = reducer(initialState, { type: "send", text: "hi" });
    const next = reducer(sent, { type: "fail", text: "err", retryable: true });
    expect(next.messages).toEqual([{ role: "user", text: "hi" }]);
  });
});

describe("reducer: timeout", () => {
  it("sets the lost-thread error and clears pending/status", () => {
    let state = reducer(initialState, { type: "send", text: "hi" });
    state = reducer(state, { type: "frame", event: "step", data: { phase: "thinking" } });
    state = reducer(state, { type: "timeout" });
    expect(state.pending).toBeNull();
    expect(state.status).toBeNull();
    expect(state.error).toEqual({
      text: "The twin lost the thread. Try again.",
      retryable: true,
      retryAfter: undefined,
      cap: undefined,
    });
  });
});

describe("reducer: reset", () => {
  it("empties messages and clears cap/error/pending but keeps open", () => {
    let state = reducer(initialState, { type: "open" });
    state = reducer(state, { type: "send", text: "hi" });
    state = reducer(state, { type: "capReached" });
    state = reducer(state, { type: "reset" });
    expect(state.messages).toEqual([]);
    expect(state.pending).toBeNull();
    expect(state.error).toBeNull();
    expect(state.capReached).toBe(false);
    expect(state.open).toBe(true);
  });
});

describe("reducer: capReached", () => {
  it("sets the capReached flag", () => {
    const next = reducer(initialState, { type: "capReached" });
    expect(next.capReached).toBe(true);
  });
});

describe("reducer immutability", () => {
  it("never mutates the input state object across every action type", () => {
    const original: TwinState = {
      messages: [{ role: "user", text: "hi" }],
      pending: { text: "partial", cards: [] },
      status: "thinking",
      error: null,
      open: true,
      capReached: false,
    };
    const snapshot = JSON.parse(JSON.stringify(original));

    reducer(original, { type: "open" });
    reducer(original, { type: "close" });
    reducer(original, { type: "send", text: "more" });
    reducer(original, { type: "frame", event: "delta", data: { text: "x" } });
    reducer(original, { type: "frame", event: "done", data: { reply: "y" } });
    reducer(original, { type: "fail", text: "e", retryable: true });
    reducer(original, { type: "timeout" });
    reducer(original, { type: "reset" });
    reducer(original, { type: "capReached" });

    expect(original).toEqual(snapshot);
  });
});

describe("userTurns", () => {
  it("counts only user messages", () => {
    const state: TwinState = {
      ...initialState,
      messages: [
        { role: "user", text: "a" },
        { role: "assistant", text: "b" },
        { role: "user", text: "c" },
      ],
    };
    expect(userTurns(state)).toBe(2);
  });
});

describe("canSend / MAX_USER_TURNS boundary", () => {
  it("MAX_USER_TURNS is 8", () => {
    expect(MAX_USER_TURNS).toBe(8);
  });

  it("allows sending on the 8th turn (7 turns so far)", () => {
    const state: TwinState = {
      ...initialState,
      messages: Array.from({ length: 7 }, () => ({ role: "user" as const, text: "x" })),
    };
    expect(canSend(state)).toBe(true);
  });

  it("blocks sending once 8 user turns exist", () => {
    const state: TwinState = {
      ...initialState,
      messages: Array.from({ length: 8 }, () => ({ role: "user" as const, text: "x" })),
    };
    expect(canSend(state)).toBe(false);
  });

  it("blocks sending while a reply is pending", () => {
    const state: TwinState = { ...initialState, pending: { text: "", cards: [] } };
    expect(canSend(state)).toBe(false);
  });

  it("blocks sending once capReached is set", () => {
    const state: TwinState = { ...initialState, capReached: true };
    expect(canSend(state)).toBe(false);
  });
});

describe("statusFor", () => {
  it("returns 'thinking' for a step phase of thinking", () => {
    expect(statusFor("step", { phase: "thinking" })).toBe("thinking");
  });

  it("returns 'composing' for a step phase of composing", () => {
    expect(statusFor("step", { phase: "composing" })).toBe("composing");
  });

  it("appends the round suffix only when round is above 1", () => {
    expect(statusFor("step", { phase: "thinking", round: 1 })).toBe("thinking");
    expect(statusFor("step", { phase: "thinking", round: 2 })).toBe("thinking · round 2");
    expect(statusFor("step", { phase: "composing", round: 3 })).toBe("composing · round 3");
  });

  it("returns the tool label lower-cased", () => {
    expect(statusFor("tool", { label: "Search" })).toBe("search");
    expect(statusFor("tool", { label: "PASSING THIS ALONG TO ADAM" })).toBe(
      "passing this along to adam",
    );
  });
});

describe("httpErrorText", () => {
  it("429 uses body.retry_after when present", () => {
    expect(httpErrorText(429, { retry_after: 30 })).toEqual({
      text: "Too many questions for the moment. Try again in 30 seconds.",
      retryable: true,
      retryAfter: 30,
    });
  });

  it("429 falls back to the Retry-After header, then 60", () => {
    expect(httpErrorText(429, undefined, 45)).toEqual({
      text: "Too many questions for the moment. Try again in 45 seconds.",
      retryable: true,
      retryAfter: 45,
    });
    expect(httpErrorText(429)).toEqual({
      text: "Too many questions for the moment. Try again in 60 seconds.",
      retryable: true,
      retryAfter: 60,
    });
  });

  it("503 uses the body message verbatim", () => {
    expect(httpErrorText(503, { code: "resting", message: "The twin is resting." })).toEqual({
      text: "The twin is resting.",
      retryable: true,
      retryAfter: undefined,
    });
  });

  it("503 falls back to a generic message and carries the Retry-After header", () => {
    expect(httpErrorText(503, undefined, 5)).toEqual({
      text: "The twin is not available right now.",
      retryable: true,
      retryAfter: 5,
    });
  });

  it("413 conversation_too_long uses the body message and sets cap", () => {
    expect(
      httpErrorText(413, { code: "conversation_too_long", message: "That's a full conversation." }),
    ).toEqual({
      text: "That's a full conversation.",
      retryable: false,
      cap: true,
    });
  });

  it("400 maps to the generic client-bug sentence", () => {
    expect(httpErrorText(400, { code: "bad_request", message: "whatever" })).toEqual({
      text: "That message didn't go through",
      retryable: false,
    });
  });

  it("413 with any other code maps to the generic client-bug sentence", () => {
    expect(httpErrorText(413, { code: "something_else", message: "whatever" })).toEqual({
      text: "That message didn't go through",
      retryable: false,
    });
  });

  it("500 maps to the unreachable sentence", () => {
    expect(httpErrorText(500)).toEqual({
      text: "Couldn't reach the twin.",
      retryable: true,
    });
  });

  it("no status (network failure) maps to the unreachable sentence", () => {
    expect(httpErrorText(undefined)).toEqual({
      text: "Couldn't reach the twin.",
      retryable: true,
    });
  });
});
