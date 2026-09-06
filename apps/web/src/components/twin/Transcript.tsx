"use client";

import { useEffect, useRef } from "react";
import { ProjectCardInline } from "@/components/twin/ProjectCardInline";
import type { Card, ChatError, Message, PendingReply, Status } from "@/twin/state";

interface TranscriptProps {
  messages: Message[];
  pending: PendingReply | null;
  status: Status;
  error: ChatError | null;
  /** Hide Retry while a cooldown runs; the composer is disabled for the same window. */
  retryDisabled: boolean;
  onRetry: () => void;
}

function paragraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function Cards({ cards }: { cards: Card[] }) {
  if (cards.length === 0) return null;
  return (
    <div className="twin-cards">
      {cards.map((card) => (
        <ProjectCardInline key={card.slug} card={card} />
      ))}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  return (
    <div className={`twin-message twin-message--${message.role}`}>
      {paragraphs(message.text).map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
      {message.cards ? <Cards cards={message.cards} /> : null}
    </div>
  );
}

function PendingBubble({ pending }: { pending: PendingReply }) {
  const parts = paragraphs(pending.text);
  return (
    <div className="twin-message twin-message--assistant twin-message--pending">
      {parts.length === 0 ? (
        <p>
          <span className="twin-caret" aria-hidden="true">
            ▍
          </span>
        </p>
      ) : (
        parts.map((paragraph, index) => (
          <p key={index}>
            {paragraph}
            {index === parts.length - 1 ? (
              <span className="twin-caret" aria-hidden="true">
                ▍
              </span>
            ) : null}
          </p>
        ))
      )}
      <Cards cards={pending.cards} />
    </div>
  );
}

interface ErrorLineProps {
  error: ChatError;
  retryDisabled: boolean;
  onRetry: () => void;
}

function ErrorLine({ error, retryDisabled, onRetry }: ErrorLineProps) {
  return (
    <div className="twin-error" role="status">
      <span>{error.text}</span>
      {error.retryable && !retryDisabled ? (
        <button type="button" className="twin-error__retry mono" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Transcript({
  messages,
  pending,
  status,
  error,
  retryDisabled,
  onRetry,
}: TranscriptProps) {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, pending, status, error]);

  // Status and error lines are live regions of their own, so they sit beside
  // the log rather than inside it (nested live regions announce twice).
  return (
    <>
      <div className="twin-transcript" role="log" aria-live="polite" ref={logRef}>
        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}
        {pending ? <PendingBubble pending={pending} /> : null}
      </div>
      {pending ? (
        <p className="twin-status mono" aria-live="polite" aria-atomic="true">
          {status ?? ""}
        </p>
      ) : null}
      {error ? <ErrorLine error={error} retryDisabled={retryDisabled} onRetry={onRetry} /> : null}
    </>
  );
}
