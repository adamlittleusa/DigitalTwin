/**
 * Pure state/reducer module for the twin chat panel. No DOM, no fetch, no
 * storage access here — see `storage.ts` for persistence and the dock
 * component for wiring this reducer to the network and to `window` events.
 */

export type Role = "user" | "assistant";

export interface Card {
  slug: string;
  title: string;
  summary: string;
}

export interface Message {
  role: Role;
  text: string;
  cards?: Card[];
}

export type Status = string | null;

export interface PendingReply {
  text: string;
  cards: Card[];
}

export interface ChatError {
  text: string;
  retryable: boolean;
  retryAfter?: number;
  cap?: boolean;
}

export interface TwinState {
  messages: Message[];
  pending: PendingReply | null;
  status: Status;
  error: ChatError | null;
  open: boolean;
  capReached: boolean;
}

export const MAX_USER_TURNS = 8;

export const initialState: TwinState = {
  messages: [],
  pending: null,
  status: null,
  error: null,
  open: false,
  capReached: false,
};

/** Frame data shapes per the spec's "Events to UI" table. */
export interface StepFrameData {
  phase: string;
  round?: number;
}
export interface ToolFrameData {
  label: string;
}
export interface ToolResultFrameData {
  ok: boolean;
}
export interface DeltaFrameData {
  text: string;
}
export interface ProjectFrameData {
  slug: string;
  title: string;
  summary: string;
  url?: string;
}
export interface DoneFrameData {
  reply: string;
  rounds?: number;
}
export interface AgentErrorFrameData {
  code: string;
  message: string;
}

export type FrameData =
  | StepFrameData
  | ToolFrameData
  | ToolResultFrameData
  | DeltaFrameData
  | ProjectFrameData
  | DoneFrameData
  | AgentErrorFrameData
  | Record<string, unknown>;

export type TwinAction =
  | { type: "open" }
  | { type: "close" }
  | { type: "send"; text: string }
  | { type: "frame"; event: string; data: FrameData }
  | { type: "fail"; text: string; retryable: boolean; retryAfter?: number; cap?: boolean }
  | { type: "timeout" }
  | { type: "reset" }
  | { type: "capReached" };

/** Number of user turns currently in the transcript. */
export function userTurns(state: TwinState): number {
  return state.messages.filter((message) => message.role === "user").length;
}

/**
 * Whether a new message can be sent right now: under the turn cap, no send
 * already in flight, no unresolved cap/error state blocking input.
 */
export function canSend(state: TwinState): boolean {
  if (state.capReached) return false;
  if (state.pending !== null) return false;
  if (userTurns(state) >= MAX_USER_TURNS) return false;
  return true;
}

/**
 * Maps a `step`/`tool` SSE event to the single status line shown under the
 * pending reply.
 */
export function statusFor(event: string, data: FrameData): string {
  if (event === "step") {
    const { phase, round } = data as StepFrameData;
    const base = phase === "composing" ? "composing" : "thinking";
    return round !== undefined && round > 1 ? `${base} · round ${round}` : base;
  }
  if (event === "tool") {
    const { label } = data as ToolFrameData;
    return label.toLowerCase();
  }
  return "";
}

export interface HttpErrorResult {
  text: string;
  retryable: boolean;
  retryAfter?: number;
  cap?: boolean;
}

/**
 * Maps an HTTP status (and, where relevant, the error body) to the plain
 * sentence shown to the user, per the spec's "Limits and errors" table.
 */
export function httpErrorText(
  status: number | undefined,
  body?: { code?: string; message?: string; retry_after?: number },
  retryAfterHeader?: number,
): HttpErrorResult {
  if (status === 429) {
    const retryAfter = body?.retry_after ?? retryAfterHeader ?? 60;
    return {
      text: `Too many questions for the moment. Try again in ${retryAfter} seconds.`,
      retryable: true,
      retryAfter,
    };
  }

  if (status === 503) {
    return {
      text: body?.message ?? "The twin is not available right now.",
      retryable: true,
      retryAfter: retryAfterHeader,
    };
  }

  if (status === 413 && body?.code === "conversation_too_long") {
    return {
      text: body.message ?? "That's a full conversation. Start a new one?",
      retryable: false,
      cap: true,
    };
  }

  if (status === 400 || status === 413) {
    return { text: "That message didn't go through", retryable: false };
  }

  return { text: "Couldn't reach the twin.", retryable: true };
}

function finalizeAssistantMessage(state: TwinState, text: string, cards: Card[]): Message[] {
  return [...state.messages, { role: "assistant", text, cards }];
}

export function reducer(state: TwinState, action: TwinAction): TwinState {
  switch (action.type) {
    case "open":
      return { ...state, open: true };

    case "close":
      return { ...state, open: false };

    case "send": {
      const userMessage: Message = { role: "user", text: action.text };
      return {
        ...state,
        messages: [...state.messages, userMessage],
        pending: { text: "", cards: [] },
        status: null,
        error: null,
      };
    }

    case "frame": {
      const { event, data } = action;

      if (event === "delta") {
        const { text } = data as DeltaFrameData;
        const pending = state.pending ?? { text: "", cards: [] };
        return { ...state, pending: { ...pending, text: pending.text + text } };
      }

      if (event === "project") {
        const { slug, title, summary } = data as ProjectFrameData;
        const pending = state.pending ?? { text: "", cards: [] };
        return {
          ...state,
          pending: { ...pending, cards: [...pending.cards, { slug, title, summary }] },
        };
      }

      if (event === "step" || event === "tool") {
        return { ...state, status: statusFor(event, data) };
      }

      if (event === "done") {
        const { reply } = data as DoneFrameData;
        const pending = state.pending ?? { text: "", cards: [] };
        return {
          ...state,
          messages: finalizeAssistantMessage(state, reply, pending.cards),
          pending: null,
          status: null,
        };
      }

      if (event === "agent_error") {
        const { message } = data as AgentErrorFrameData;
        const pending = state.pending ?? { text: "", cards: [] };
        return {
          ...state,
          messages: finalizeAssistantMessage(state, message, pending.cards),
          pending: null,
          status: null,
        };
      }

      // tool_result and unknown events have no visible effect.
      return state;
    }

    case "fail":
      return {
        ...state,
        pending: null,
        status: null,
        error: {
          text: action.text,
          retryable: action.retryable,
          retryAfter: action.retryAfter,
          cap: action.cap,
        },
      };

    case "timeout":
      return {
        ...state,
        pending: null,
        status: null,
        error: { text: "The twin lost the thread. Try again.", retryable: true },
      };

    case "reset":
      return { ...state, messages: [], pending: null, status: null, error: null, capReached: false };

    case "capReached":
      return { ...state, capReached: true };

    default:
      return state;
  }
}
