import Link from "next/link";
import { NavLink } from "./NavLink";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="container site-header__row">
        <Link href="/" className="site-header__name">
          Adam Little
        </Link>
        <nav className="site-header__nav" aria-label="Primary">
          <NavLink href="/">Architecture</NavLink>
          <Link href="/?view=use-cases">Use cases</Link>
          <NavLink href="/about">About</NavLink>
          <NavLink href="/writing">Writing</NavLink>
        </nav>
      </div>
    </header>
  );
}
