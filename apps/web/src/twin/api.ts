import { createSseParser, type SseFrame } from "@/twin/sse";

export type ChatHttpErrorBody = {
  code: string;
  message: string;
  retry_after?: number;
};

export class ChatHttpError extends Error {
  status: number;
  body?: ChatHttpErrorBody;
  /** Seconds from the `Retry-After` header, when the server sent one. */
  retryAfterHeader?: number;

  constructor(status: number, body?: ChatHttpErrorBody, retryAfterHeader?: number) {
    super(body?.message ?? `twin API responded with ${status}`);
    this.name = "ChatHttpError";
    this.status = status;
    this.body = body;
    this.retryAfterHeader = retryAfterHeader;
  }
}

/**
 * Determine the base URL for the twin API. `NEXT_PUBLIC_TWIN_API`, when set,
 * always wins. Otherwise the base is derived from the host: localhost
 * targets a local dev server, adambuilds.ai (and www) targets production,
 * anything else is off-domain (`null`).
 */
export function apiBase(host: string = window.location.hostname): string | null {
  const envBase = process.env.NEXT_PUBLIC_TWIN_API;
  if (envBase) return envBase;

  if (host === "localhost" || host === "127.0.0.1") {
    return "http://localhost:8080";
  }
  if (host === "adambuilds.ai" || host === "www.adambuilds.ai") {
    return "https://api.adambuilds.ai";
  }
  return null;
}

/**
 * `GET /v1/examples` returns `{ "questions": [...] }`. Anything else (a
 * failed response, a different shape) yields no chips rather than a throw.
 */
export async function fetchExamples(base: string): Promise<string[]> {
  const response = await fetch(`${base}/v1/examples`);
  if (!response.ok) return [];
  const body: unknown = await response.json();
  if (body === null || typeof body !== "object") return [];
  const { questions } = body as { questions?: unknown };
  if (!Array.isArray(questions)) return [];
  return questions.every((q) => typeof q === "string") ? (questions as string[]) : [];
}

function retryAfterSeconds(response: Response): number | undefined {
  const header = response.headers?.get("Retry-After");
  if (!header) return undefined;
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

export type ChatMessage = { role: "user" | "assistant"; text: string };

/** The API's wire shape: `content`, not `text`, and nothing else (unknown fields are rejected). */
type WireMessage = { role: ChatMessage["role"]; content: string };

function toWire(messages: ChatMessage[]): WireMessage[] {
  return messages.map(({ role, text }) => ({ role, content: text }));
}

export async function streamChat(
  base: string,
  messages: ChatMessage[],
  onFrame: (frame: SseFrame) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${base}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: toWire(messages) }),
    signal,
  });

  if (!response.ok) {
    let body: ChatHttpErrorBody | undefined;
    try {
      body = (await response.json()) as ChatHttpErrorBody;
    } catch {
      body = undefined;
    }
    throw new ChatHttpError(response.status, body, retryAfterSeconds(response));
  }

  const parser = createSseParser();
  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder("utf-8");
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    for (const frame of parser.push(chunk)) {
      onFrame(frame);
    }
  }
  for (const frame of parser.flush()) {
    onFrame(frame);
  }
}

export type ParsedFrame = { event: string; data: Record<string, unknown> };

/**
 * The boundary between the wire and the reducer: turns a raw SSE frame into
 * one with its `data` parsed as a JSON object. Returns `null` (and logs) when
 * the payload is not valid JSON or is not an object, so a malformed frame is
 * skipped rather than crashing the turn.
 */
export function parseFrame(frame: SseFrame): ParsedFrame | null {
  try {
    const parsed: unknown = JSON.parse(frame.data);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      console.warn(`twin: ${frame.event} frame payload is not an object`, frame.data);
      return null;
    }
    return { event: frame.event, data: parsed as Record<string, unknown> };
  } catch (error) {
    console.warn(`twin: could not parse ${frame.event} frame`, frame.data, error);
    return null;
  }
}
