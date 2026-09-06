import Link from "next/link";
import type { ReactNode } from "react";

interface TileProps {
  href: string;
  eyebrow: string;
  title: string;
  description: string;
  diagram?: ReactNode;
  count?: string;
}

export function Tile({ href, eyebrow, title, description, diagram, count }: TileProps) {
  return (
    <Link href={href} className="tile">
      {diagram ? <div className="tile__diagram">{diagram}</div> : null}
      <span className="mono tile__eyebrow">{eyebrow}</span>
      <h3 className="tile__title">{title}</h3>
      <p className="tile__description">{description}</p>
      {count ? <span className="mono tile__count">{count}</span> : null}
    </Link>
  );
}
