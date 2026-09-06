import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { loadState, saveState } from "@/twin/storage";

/**
 * The repo has no jsdom dependency, so this stubs a minimal
 * `window.sessionStorage` directly on the Node global rather than switching
 * the test environment.
 */
function createFakeSessionStorage() {
  let store: Record<string, string> = {};
  return {
    getItem(key: string) {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
    },
    setItem(key: string, value: string) {
      store[key] = value;
    },
    removeItem(key: string) {
      delete store[key];
    },
    clear() {
      store = {};
    },
  };
}

describe("storage: save/load round-trip", () => {
  let fakeSessionStorage: ReturnType<typeof createFakeSessionStorage>;

  beforeEach(() => {
    fakeSessionStorage = createFakeSessionStorage();
    (globalThis as { window?: unknown }).window = { sessionStorage: fakeSessionStorage };
  });

  afterEach(() => {
    delete (globalThis as { window?: unknown }).window;
  });

  it("round-trips messages and open", () => {
    const state = {
      messages: [{ role: "user" as const, text: "hi" }],
      open: true,
    };
    saveState(state);
    expect(loadState()).toEqual(state);
  });

  it("persists only messages and open, dropping any other fields", () => {
    const state = {
      messages: [{ role: "assistant" as const, text: "hello" }],
      open: false,
      status: "thinking",
      pending: { text: "draft", cards: [] },
      error: { text: "oops", retryable: true },
    } as unknown as { messages: { role: "assistant"; text: string }[]; open: boolean };

    saveState(state);
    const raw = fakeSessionStorage.getItem("twin:v1");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    expect(Object.keys(parsed).sort()).toEqual(["messages", "open"]);
  });

  it("returns null when nothing is stored", () => {
    expect(loadState()).toBeNull();
  });

  it("returns null on corrupt JSON", () => {
    fakeSessionStorage.setItem("twin:v1", "{not valid json");
    expect(loadState()).toBeNull();
  });

  it("returns null when the stored value has no messages array", () => {
    fakeSessionStorage.setItem("twin:v1", JSON.stringify({ open: true }));
    expect(loadState()).toBeNull();
  });

  it("loadState returns null when sessionStorage access throws", () => {
    (globalThis as { window?: unknown }).window = {
      sessionStorage: {
        getItem() {
          throw new Error("blocked");
        },
      },
    };
    expect(loadState()).toBeNull();
  });

  it("saveState swallows errors when sessionStorage access throws", () => {
    (globalThis as { window?: unknown }).window = {
      sessionStorage: {
        setItem() {
          throw new Error("blocked");
        },
      },
    };
    expect(() => saveState({ messages: [], open: false })).not.toThrow();
  });

  it("loadState returns null when window is unavailable (e.g. SSR)", () => {
    delete (globalThis as { window?: unknown }).window;
    expect(loadState()).toBeNull();
  });

  it("saveState is a no-op when window is unavailable (e.g. SSR)", () => {
    delete (globalThis as { window?: unknown }).window;
    expect(() => saveState({ messages: [], open: false })).not.toThrow();
  });
});
