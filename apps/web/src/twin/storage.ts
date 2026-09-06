import type { Message } from "@/twin/state";

const STORAGE_KEY = "twin:v1";

export interface PersistedTwinState {
  messages: Message[];
  open: boolean;
}

/**
 * Reads the persisted subset of twin state (`messages` and `open` only —
 * every transient field like `status`/`pending`/`error` is left out). Returns
 * `null` whenever storage is unavailable (SSR, privacy mode) or the stored
 * value can't be parsed.
 */
export function loadState(): PersistedTwinState | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const parsed = JSON.parse(raw) as Partial<PersistedTwinState>;
    if (!parsed || !Array.isArray(parsed.messages)) return null;
    return { messages: parsed.messages, open: parsed.open ?? false };
  } catch {
    return null;
  }
}

/**
 * Persists only `messages` and `open` from the given state, ignoring any
 * other fields it may carry.
 */
export function saveState(state: PersistedTwinState): void {
  try {
    const toStore: PersistedTwinState = { messages: state.messages, open: state.open };
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
  } catch {
    // sessionStorage unavailable (SSR, privacy mode, quota exceeded) — no-op.
  }
}
