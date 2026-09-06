"use client";

import type React from "react";

export const TWIN_OPEN_EVENT = "twin:open";

interface OpenTwinButtonProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * A plain button that asks the dock to open the twin panel. Used wherever a
 * "Try it" or "ask the twin" link is needed outside the dock itself.
 */
export function OpenTwinButton({ children, className }: OpenTwinButtonProps) {
  return (
    <button
      type="button"
      className={className ?? "twin-open-button"}
      onClick={() => window.dispatchEvent(new CustomEvent(TWIN_OPEN_EVENT))}
    >
      {children}
    </button>
  );
}
