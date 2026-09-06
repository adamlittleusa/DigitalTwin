import type { ReactNode } from "react";

interface EmptyStateProps {
  eyebrow?: string;
  children: ReactNode;
}

export function EmptyState({ eyebrow, children }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {eyebrow ? <p className="mono empty-state__eyebrow">{eyebrow}</p> : null}
      <p className="empty-state__body">{children}</p>
    </div>
  );
}
