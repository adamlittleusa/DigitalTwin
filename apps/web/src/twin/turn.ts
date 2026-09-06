/**
 * Pure helpers for the turn runner in `TwinDock`. The runner tracks whether a
 * `done` frame arrived while the stream was open, so that a stream closing
 * after a completed reply is never mistaken for one that ended early.
 */
import type { ParsedFrame } from "@/twin/api";

/** Fold one parsed frame into the "seen done" flag; unparseable frames don't count. */
export function sawDoneAfter(sawDone: boolean, parsed: ParsedFrame | null): boolean {
  return sawDone || parsed?.event === "done";
}

/** A stream that closed without `done` left the turn hanging. */
export function streamEndedEarly(sawDone: boolean): boolean {
  return !sawDone;
}
