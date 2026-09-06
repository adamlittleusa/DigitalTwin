import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatHttpError, apiBase, fetchExamples, streamChat } from "@/twin/api";

const encoder = new TextEncoder();

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

describe("apiBase", () => {
  const originalEnv = process.env.NEXT_PUBLIC_TWIN_API;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_TWIN_API;
    } else {
      process.env.NEXT_PUBLIC_TWIN_API = originalEnv;
    }
  });

  it("returns localhost base for localhost", () => {
    delete process.env.NEXT_PUBLIC_TWIN_API;
    expect(apiBase("localhost")).toBe("http://localhost:8080");
  });

  it("returns localhost base for 127.0.0.1", () => {
    delete process.env.NEXT_PUBLIC_TWIN_API;
    expect(apiBase("127.0.0.1")).toBe("http://localhost:8080");
  });

  it("returns the production base for adambuilds.ai", () => {
    delete process.env.NEXT_PUBLIC_TWIN_API;
    expect(apiBase("adambuilds.ai")).toBe("https://api.adambuilds.ai");
  });

  it("returns the production base for www.adambuilds.ai", () => {
    delete process.env.NEXT_PUBLIC_TWIN_API;
    expect(apiBase("www.adambuilds.ai")).toBe("https://api.adambuilds.ai");
  });

  it("returns null for an unrecognized host", () => {
    delete process.env.NEXT_PUBLIC_TWIN_API;
    expect(apiBase("example.com")).toBeNull();
  });

  it("prefers the env var over the host rule", () => {
    process.env.NEXT_PUBLIC_TWIN_API = "https://override.example";
    expect(apiBase("example.com")).toBe("https://override.example");
    expect(apiBase("adambuilds.ai")).toBe("https://override.example");
  });
});

describe("fetchExamples", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the parsed JSON array", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ["Question one?", "Question two?"],
    });
    vi.stubGlobal("fetch", fetchMock);

    const examples = await fetchExamples("https://api.adambuilds.ai");
    expect(examples).toEqual(["Question one?", "Question two?"]);
    expect(fetchMock).toHaveBeenCalledWith("https://api.adambuilds.ai/v1/examples");
  });
});

describe("streamChat", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the messages and feeds frames to onFrame", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamOf([
        "event: step\ndata: {\"phase\":\"thinking\"}\n\nevent: del",
        "ta\ndata: hi\n\nevent: done\ndata: {\"reply\":\"hi\"}\n\n",
      ]),
    });
    vi.stubGlobal("fetch", fetchMock);

    const frames: { event: string; data: string }[] = [];
    await streamChat(
      "https://api.adambuilds.ai",
      [{ role: "user", text: "hello" }],
      (frame) => frames.push(frame),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.adambuilds.ai/v1/chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
        body: JSON.stringify({ messages: [{ role: "user", text: "hello" }] }),
      }),
    );
    expect(frames).toEqual([
      { event: "step", data: '{"phase":"thinking"}' },
      { event: "delta", data: "hi" },
      { event: "done", data: '{"reply":"hi"}' },
    ]);
  });

  it("passes the abort signal through to fetch", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamOf([]),
    });
    vi.stubGlobal("fetch", fetchMock);

    await streamChat("https://api.adambuilds.ai", [], () => {}, controller.signal);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("throws ChatHttpError with a parsed body on non-200", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ code: "rate_limited", message: "slow down", retry_after: 30 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      streamChat("https://api.adambuilds.ai", [], () => {}),
    ).rejects.toMatchObject({
      status: 429,
      body: { code: "rate_limited", message: "slow down", retry_after: 30 },
    });
  });

  it("throws ChatHttpError with no body when the error response isn't JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    let caught: unknown;
    try {
      await streamChat("https://api.adambuilds.ai", [], () => {});
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(ChatHttpError);
    expect((caught as ChatHttpError).status).toBe(500);
    expect((caught as ChatHttpError).body).toBeUndefined();
  });
});
