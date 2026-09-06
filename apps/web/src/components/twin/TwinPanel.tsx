"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import { Composer } from "@/components/twin/Composer";
import { Transcript } from "@/components/twin/Transcript";
import type { TwinState } from "@/twin/state";

export const GREETING = "Ask me about Adam's work. I answer as him.";
export const OFF_DOMAIN_NOTICE = "The twin only answers on adambuilds.ai.";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface TwinPanelProps {
  state: TwinState;
  examples: string[];
  offDomain: boolean;
  composerDisabled: boolean;
  atCap: boolean;
  onClose: () => void;
  onSend: (text: string) => void;
  onRetry: () => void;
  onReset: () => void;
}

function ExampleChips({ examples, onPick }: { examples: string[]; onPick: (text: string) => void }) {
  if (examples.length === 0) return null;
  return (
    <div className="twin-chips" aria-label="Example questions">
      {examples.map((example) => (
        <button
          key={example}
          type="button"
          className="twin-chip"
          onClick={() => onPick(example)}
        >
          {example}
        </button>
      ))}
    </div>
  );
}

export function TwinPanel({
  state,
  examples,
  offDomain,
  composerDisabled,
  atCap,
  onClose,
  onSend,
  onRetry,
  onReset,
}: TwinPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus the composer on open; fall back to the first focusable control
  // (the close button) when the composer is disabled or replaced.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea && !textarea.disabled) {
      textarea.focus();
      return;
    }
    panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !panelRef.current) return;

    const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && (active === first || !panelRef.current.contains(active))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const hasMessages = state.messages.length > 0;

  return (
    <div
      ref={panelRef}
      className="twin-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby="twin-panel-title"
      onKeyDown={handleKeyDown}
    >
      <header className="twin-panel__header">
        <h2 id="twin-panel-title" className="twin-panel__title">
          Adam&apos;s twin
        </h2>
        <button type="button" className="twin-panel__close mono" onClick={onClose}>
          Close
        </button>
      </header>

      <div className="twin-panel__body">
        <p className="twin-greeting">{GREETING}</p>
        {offDomain ? <p className="twin-notice mono">{OFF_DOMAIN_NOTICE}</p> : null}
        {!hasMessages && !offDomain ? <ExampleChips examples={examples} onPick={onSend} /> : null}
        <Transcript
          messages={state.messages}
          pending={state.pending}
          status={state.status}
          error={state.error}
          onRetry={onRetry}
        />
      </div>

      <Composer
        disabled={composerDisabled}
        atCap={atCap}
        onSend={onSend}
        onReset={onReset}
        textareaRef={textareaRef}
      />
    </div>
  );
}
