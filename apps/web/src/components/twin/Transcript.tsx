"use client";

import { useEffect, useRef } from "react";
import { ProjectCardInline } from "@/components/twin/ProjectCardInline";
import type { Card, ChatError, Message, PendingReply, Status } from "@/twin/state";

interface TranscriptProps {
  messages: Message[];
  pending: PendingReply | null;
  status: Status;
  error: ChatError | null;
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

function PendingBubble({ pending, status }: { pending: PendingReply; status: Status }) {
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
      <p className="twin-status mono" aria-live="polite" aria-atomic="true">
        {status ?? ""}
      </p>
    </div>
  );
}

function ErrorLine({ error, onRetry }: { error: ChatError; onRetry: () => void }) {
  return (
    <div className="twin-error" role="status">
      <span>{error.text}</span>
      {error.retryable ? (
        <button type="button" className="twin-error__retry mono" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Transcript({ messages, pending, status, error, onRetry }: TranscriptProps) {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, pending, status, error]);

  return (
    <div className="twin-transcript" role="log" aria-live="polite" ref={logRef}>
      {messages.map((message, index) => (
        <MessageBubble key={index} message={message} />
      ))}
      {pending ? <PendingBubble pending={pending} status={status} /> : null}
      {error ? <ErrorLine error={error} onRetry={onRetry} /> : null}
    </div>
  );
}
