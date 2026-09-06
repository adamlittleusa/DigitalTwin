"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

const USE_CASES_VIEW = "use-cases";
const VIEW_PARAM = "view";

type NavLinkProps = {
  href: string;
  children: ReactNode;
};

/**
 * Current-page detection. The gallery at "/" has two views selected by
 * `?view=`: "Architecture" is current on "/" without the use-cases view,
 * "Use cases" only with it. Every other link is current on its own path and
 * on any path beneath it, so "/writing/foo" lights "Writing".
 */
function isCurrent(href: string, pathname: string, view: string | null): boolean {
  const [hrefPath, hrefQuery] = href.split("?");
  if (hrefPath !== "/") {
    return pathname === hrefPath || pathname.startsWith(`${hrefPath}/`);
  }
  if (pathname !== "/") return false;
  const hrefView = new URLSearchParams(hrefQuery ?? "").get(VIEW_PARAM);
  const wantsUseCases = hrefView === USE_CASES_VIEW;
  const hasUseCases = view === USE_CASES_VIEW;
  return wantsUseCases === hasUseCases;
}

export function NavLink({ href, children }: NavLinkProps) {
  const pathname = usePathname();
  const view = useSearchParams().get(VIEW_PARAM);
  const current = isCurrent(href, pathname, view);

  return (
    <Link href={href} aria-current={current ? "page" : undefined}>
      {children}
    </Link>
  );
}
