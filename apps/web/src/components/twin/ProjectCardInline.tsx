import Link from "next/link";
import type { Card } from "@/twin/state";

/** A compact project card shown under a twin reply, linking into the site. */
export function ProjectCardInline({ card }: { card: Card }) {
  return (
    <Link href={`/projects/${card.slug}`} className="twin-card">
      <span className="twin-card__title">{card.title}</span>
      <span className="twin-card__summary">{card.summary}</span>
    </Link>
  );
}
