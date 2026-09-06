import Link from "next/link";
import { Suspense } from "react";
import { NavLink } from "./NavLink";

const NAV_ITEMS = [
  { href: "/", label: "Architecture" },
  { href: "/?view=use-cases", label: "Use cases" },
  { href: "/about", label: "About" },
  { href: "/writing", label: "Writing" },
] as const;

function NavItems() {
  return (
    <>
      {NAV_ITEMS.map((item) => (
        <NavLink key={item.href} href={item.href}>
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

function StaticNavItems() {
  return (
    <>
      {NAV_ITEMS.map((item) => (
        <Link key={item.href} href={item.href}>
          {item.label}
        </Link>
      ))}
    </>
  );
}

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container site-header__row">
        <Link href="/" className="site-header__name">
          Adam Little
        </Link>
        <nav className="site-header__nav" aria-label="Primary">
          {/* useSearchParams in NavLink needs a Suspense boundary on static pages. */}
          <Suspense fallback={<StaticNavItems />}>
            <NavItems />
          </Suspense>
        </nav>
      </div>
    </header>
  );
}
