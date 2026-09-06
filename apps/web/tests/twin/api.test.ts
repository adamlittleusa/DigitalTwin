import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatHttpError, apiBase, fetchExamples, parseFrame, streamChat } from "@/twin/api";

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

  it("returns the questions array from the { questions } envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ questions: ["Question one?", "Question two?"] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const examples = await fetchExamples("https://api.adambuilds.ai");
    expect(examples).toEqual(["Question one?", "Question two?"]);
    expect(fetchMock).toHaveBeenCalledWith("https://api.adambuilds.ai/v1/examples");
  });

  it("returns [] when the response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ questions: ["x"] }) }),
    );
    expect(await fetchExamples("https://api.adambuilds.ai")).toEqual([]);
  });

  it("returns [] when questions is missing or not an array of strings", async () => {
    for (const body of [["bare"], { questions: "nope" }, { questions: ["ok", 3] }, null]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }));
      expect(await fetchExamples("https://api.adambuilds.ai")).toEqual([]);
    }
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
        body: JSON.stringify({ messages: [{ role: "user", content: "hello" }] }),
      }),
    );
    expect(frames).toEqual([
      { event: "step", data: '{"phase":"thinking"}' },
      { event: "delta", data: "hi" },
      { event: "done", data: '{"reply":"hi"}' },
    ]);
  });

  it("serialises messages as { role, content } with no extra fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, body: streamOf([]) });
    vi.stubGlobal("fetch", fetchMock);

    await streamChat(
      "https://api.adambuilds.ai",
      [
        { role: "user", text: "first" },
        { role: "assistant", text: "reply" },
        { role: "user", text: "second" },
      ],
      () => {},
    );

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string) as {
      messages: Record<string, unknown>[];
    };
    expect(body).toEqual({
      messages: [
        { role: "user", content: "first" },
        { role: "assistant", content: "reply" },
        { role: "user", content: "second" },
      ],
    });
    for (const message of body.messages) {
      expect(Object.keys(message).sort()).toEqual(["content", "role"]);
    }
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

describe("parseFrame", () => {
  it("parses JSON object data and keeps the event name", () => {
    expect(parseFrame({ event: "delta", data: '{"text":"hi"}' })).toEqual({
      event: "delta",
      data: { text: "hi" },
    });
  });

  it("returns null and logs on invalid JSON", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(parseFrame({ event: "delta", data: "{not json" })).toBeNull();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("returns null when the payload is not an object", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(parseFrame({ event: "done", data: '"just a string"' })).toBeNull();
    expect(parseFrame({ event: "done", data: "[1,2]" })).toBeNull();
    warn.mockRestore();
  });
});

describe("streamChat: Retry-After header", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exposes the Retry-After header on the ChatHttpError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        headers: new Headers({ "Retry-After": "5" }),
        json: async () => ({ code: "busy", message: "Give me a moment." }),
      }),
    );
    await expect(streamChat("https://api.adambuilds.ai", [], () => {})).rejects.toMatchObject({
      status: 503,
      retryAfterHeader: 5,
    });
  });
});
