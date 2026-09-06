"use client";

import { useState, type KeyboardEvent, type RefObject } from "react";

export const CAP_MESSAGE = "That's a full conversation. Start a new one?";

interface ComposerProps {
  disabled: boolean;
  atCap: boolean;
  onSend: (text: string) => void;
  onReset: () => void;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}

/** Let the textarea grow with its content; CSS caps it at four lines. */
function fitHeight(textarea: HTMLTextAreaElement) {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

export function Composer({ disabled, atCap, onSend, onReset, textareaRef }: ComposerProps) {
  const [draft, setDraft] = useState("");

  if (atCap) {
    return (
      <div className="twin-composer twin-composer--cap">
        <p className="twin-composer__cap-text">{CAP_MESSAGE}</p>
        <button type="button" className="twin-button mono" onClick={onReset}>
          Start over
        </button>
      </div>
    );
  }

  function submit() {
    const text = draft.trim();
    if (disabled || text.length === 0) return;
    onSend(text);
    setDraft("");
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.value = "";
      fitHeight(textarea);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    submit();
  }

  return (
    <form
      className="twin-composer"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor="twin-composer-input" className="visually-hidden">
        Your question
      </label>
      <textarea
        id="twin-composer-input"
        ref={textareaRef}
        className="twin-composer__input"
        rows={1}
        placeholder="Ask about Adam's work"
        value={draft}
        disabled={disabled}
        onChange={(event) => {
          setDraft(event.target.value);
          fitHeight(event.target);
        }}
        onKeyDown={handleKeyDown}
      />
      <button
        type="submit"
        className="twin-button mono"
        disabled={disabled || draft.trim().length === 0}
      >
        Send
      </button>
    </form>
  );
}
