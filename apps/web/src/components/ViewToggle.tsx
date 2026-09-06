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

export function useGalleryView(): GalleryView {
  const view = useSearchParams().get(VIEW_PARAM);
  return view === USE_CASES_VIEW ? "use-cases" : "architecture";
}

export function ViewToggle() {
  const view = useGalleryView();
  const tabRefs = useRef<(HTMLAnchorElement | null)[]>([]);

  useEffect(() => {
    const gallery = document.getElementById("gallery");
    if (gallery) gallery.dataset.view = view;
  }, [view]);

  function handleKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = (index + delta + TABS.length) % TABS.length;
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
