"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useReducer,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { TWIN_OPEN_EVENT } from "@/components/twin/OpenTwinButton";
import { TWIN_PANEL_ID, TwinPanel } from "@/components/twin/TwinPanel";
import {
  ChatHttpError,
  apiBase,
  fetchExamples,
  parseFrame,
  streamChat,
  type ChatMessage,
} from "@/twin/api";
import {
  MAX_USER_TURNS,
  canSend,
  httpErrorText,
  initialState,
  reducer,
  userTurns,
  type TwinState,
} from "@/twin/state";
import { loadState, saveState } from "@/twin/storage";
import { sawDoneAfter, streamEndedEarly } from "@/twin/turn";

/** The turn ends if no frame arrives for this long. */
const INACTIVITY_MS = 90_000;
const NETWORK_ERROR_TEXT = "Couldn't reach the twin.";
const STREAM_ENDED_EARLY_TEXT = "The twin lost the thread. Try again.";

const subscribeNever = () => () => {};
const getClientBase = (): string | null => apiBase();
const getServerBase = (): string | null | undefined => undefined;

function toChatMessages(state: TwinState): ChatMessage[] {
  return state.messages.map(({ role, text }) => ({ role, text }));
}

export function TwinDock() {
  const [state, dispatch] = useReducer(reducer, initialState);
  // Mirrored in a layout effect, which commits synchronously before any
  // handler can run, so the double-send guard never sees a stale state.
  // (Writing the ref during render is what the React Compiler lint forbids.)
  const stateRef = useRef(state);
  useLayoutEffect(() => {
    stateRef.current = state;
  });

  // `undefined` during server render and hydration; `null` is off-domain.
  const base = useSyncExternalStore(subscribeNever, getClientBase, getServerBase);
  const [examples, setExamples] = useState<string[]>([]);
  const [coolingDown, setCoolingDown] = useState(false);

  const hydrated = useRef(false);
  const examplesRequested = useRef(false);
  const wasOpen = useRef(false);
  const dockButtonRef = useRef<HTMLButtonElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const cooldownTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Hydrate after mount so server and first client render agree.
  useEffect(() => {
    const persisted = loadState();
    if (persisted) dispatch({ type: "hydrate", ...persisted });
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    saveState({ messages: state.messages, open: state.open });
  }, [state.messages, state.open]);

  useEffect(() => {
    const onOpen = () => dispatch({ type: "open" });
    window.addEventListener(TWIN_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(TWIN_OPEN_EVENT, onOpen);
  }, []);

  // Examples load once, the first time the panel opens with a known base.
  useEffect(() => {
    if (!state.open || !base || examplesRequested.current) return;
    examplesRequested.current = true;
    fetchExamples(base)
      .then(setExamples)
      .catch((error: unknown) => console.warn("twin: examples unavailable", error));
  }, [state.open, base]);

  // Return focus to the dock button when the panel closes.
  useEffect(() => {
    if (wasOpen.current && !state.open) dockButtonRef.current?.focus();
    wasOpen.current = state.open;
  }, [state.open]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      if (cooldownTimer.current) clearTimeout(cooldownTimer.current);
    },
    [],
  );

  const startCooldown = useCallback((seconds: number) => {
    if (cooldownTimer.current) clearTimeout(cooldownTimer.current);
    setCoolingDown(true);
    cooldownTimer.current = setTimeout(() => setCoolingDown(false), seconds * 1000);
  }, []);

  const runTurn = useCallback(
    async (messages: ChatMessage[]) => {
      if (!base) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      let inactivity: ReturnType<typeof setTimeout> | null = null;
      const armInactivity = () => {
        if (inactivity) clearTimeout(inactivity);
        inactivity = setTimeout(() => {
          dispatch({ type: "timeout" });
          controller.abort();
        }, INACTIVITY_MS);
      };
      armInactivity();

      // Tracked here rather than read back from state after the await: the
      // reducer's `done` may not have committed yet when the stream closes.
      let sawDone = false;
      try {
        await streamChat(
          base,
          messages,
          (frame) => {
            armInactivity();
            const parsed = parseFrame(frame);
            sawDone = sawDoneAfter(sawDone, parsed);
            if (parsed) dispatch({ type: "frame", event: parsed.event, data: parsed.data });
          },
          controller.signal,
        );
        if (streamEndedEarly(sawDone)) {
          dispatch({ type: "fail", text: STREAM_ENDED_EARLY_TEXT, retryable: true });
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof ChatHttpError) {
          const mapped = httpErrorText(error.status, error.body, error.retryAfterHeader);
          if (error.status === 400 || error.status === 413) {
            console.error("twin: request rejected", error.status, error.body);
          }
          dispatch({ type: "fail", ...mapped });
          if (mapped.cap) dispatch({ type: "capReached" });
          if (mapped.retryAfter) startCooldown(mapped.retryAfter);
        } else {
          console.error("twin: request failed", error);
          dispatch({ type: "fail", text: NETWORK_ERROR_TEXT, retryable: true });
        }
      } finally {
        if (inactivity) clearTimeout(inactivity);
        if (abortRef.current === controller) abortRef.current = null;
      }
    },
    [base, startCooldown],
  );

  const handleSend = useCallback(
    (text: string) => {
      const current = stateRef.current;
      if (!base || coolingDown || !canSend(current)) return;
      dispatch({ type: "send", text });
      void runTurn([...toChatMessages(current), { role: "user", text }]);
    },
    [base, coolingDown, runTurn],
  );

  const handleRetry = useCallback(() => {
    const current = stateRef.current;
    const last = current.messages[current.messages.length - 1];
    if (!base || coolingDown || current.pending || !last || last.role !== "user") return;
    dispatch({ type: "retry" });
    void runTurn(toChatMessages(current));
  }, [base, coolingDown, runTurn]);

  const handleClose = useCallback(() => dispatch({ type: "close" }), []);
  const handleReset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  const offDomain = base === null;
  const atCap = state.capReached || userTurns(state) >= MAX_USER_TURNS;
  const composerDisabled =
    offDomain || base === undefined || coolingDown || state.pending !== null || !canSend(state);

  return (
    <>
      <button
        ref={dockButtonRef}
        type="button"
        className="twin-dock mono"
        aria-expanded={state.open}
        aria-controls={TWIN_PANEL_ID}
        onClick={() => dispatch({ type: state.open ? "close" : "open" })}
      >
        Ask the twin
      </button>
      {state.open ? (
        <TwinPanel
          state={state}
          examples={examples}
          offDomain={offDomain}
          composerDisabled={composerDisabled}
          coolingDown={coolingDown}
          atCap={atCap}
          onClose={handleClose}
          onSend={handleSend}
          onRetry={handleRetry}
          onReset={handleReset}
        />
      ) : null}
    </>
  );
}
