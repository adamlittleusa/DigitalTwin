"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

const VIEW_PARAM = "view";
const USE_CASES_VIEW = "use-cases";

export type GalleryView = "architecture" | "use-cases";

const TABS: { view: GalleryView; href: string; label: string }[] = [
  { view: "architecture", href: "/", label: "Architecture" },
  { view: "use-cases", href: "/?view=use-cases", label: "Use cases" },
];

const DEFAULT_VIEW: GalleryView = "architecture";

/** Roving-tabindex keyboard navigation: arrows wrap, Home/End jump. */
function nextTabIndex(key: string, index: number): number | undefined {
  switch (key) {
    case "ArrowRight":
      return (index + 1) % TABS.length;
    case "ArrowLeft":
      return (index - 1 + TABS.length) % TABS.length;
    case "Home":
      return 0;
    case "End":
      return TABS.length - 1;
    default:
      return undefined;
  }
}

/**
 * Server-rendered fallback for the Suspense boundary around `ViewToggle`.
 * Same pill markup with plain links, architecture marked active, so the
 * prerendered HTML has a working toggle before the client hydrates.
 */
export function StaticViewToggle() {
  return (
    <div className="view-toggle" role="tablist" aria-label="Gallery view">
      {TABS.map((tab) => {
        const selected = tab.view === DEFAULT_VIEW;
        return (
          <Link
            key={tab.view}
            href={tab.href}
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className={`view-toggle__tab${selected ? " view-toggle__tab--active" : ""}`}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}

export function useGalleryView(): GalleryView {
  const view = useSearchParams().get(VIEW_PARAM);
  return view === USE_CASES_VIEW ? "use-cases" : DEFAULT_VIEW;
}

export function ViewToggle() {
  const view = useGalleryView();
  const tabRefs = useRef<(HTMLAnchorElement | null)[]>([]);

  useEffect(() => {
    const gallery = document.getElementById("gallery");
    if (gallery) gallery.dataset.view = view;
  }, [view]);

  function handleKeyDown(event: React.KeyboardEvent, index: number) {
    const next = nextTabIndex(event.key, index);
    if (next === undefined) return;
    event.preventDefault();
    tabRefs.current[next]?.focus();
  }

  return (
    <div className="view-toggle" role="tablist" aria-label="Gallery view">
      {TABS.map((tab, index) => {
        const selected = tab.view === view;
        return (
          <Link
            key={tab.view}
            href={tab.href}
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            className={`view-toggle__tab${selected ? " view-toggle__tab--active" : ""}`}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
