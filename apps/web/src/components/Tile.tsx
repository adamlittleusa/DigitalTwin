import Link from "next/link";
import type { ReactNode } from "react";

export type HeadingLevel = "h2" | "h3";

interface TileProps {
  href: string;
  headingLevel?: HeadingLevel;
  eyebrow: string;
  title: string;
  description: string;
  diagram?: ReactNode;
  count?: string;
}

export function Tile({
  href,
  headingLevel = "h3",
  eyebrow,
  title,
  description,
  diagram,
  count,
}: TileProps) {
  const Heading = headingLevel;
  return (
    <Link href={href} className="tile">
      {diagram ? <div className="tile__diagram">{diagram}</div> : null}
      <span className="mono tile__eyebrow">{eyebrow}</span>
      <Heading className="tile__title">{title}</Heading>
      <p className="tile__description">{description}</p>
      {count ? <span className="mono tile__count">{count}</span> : null}
    </Link>
  );
}
