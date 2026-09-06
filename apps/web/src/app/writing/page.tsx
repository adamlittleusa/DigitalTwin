import type { Metadata } from "next";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { loadWriting } from "@/content/load";
import { INCLUDE_DRAFTS } from "./drafts";

export const metadata: Metadata = {
  title: "Writing",
  description: "Notes on building agents and securing them.",
};

const EMPTY_COPY = "The first piece is on its way. Until then, the twin knows the stories.";

export default function WritingPage() {
  const posts = loadWriting(undefined, { includeDrafts: INCLUDE_DRAFTS });

  return (
    <div className="container">
      <PageHeader title="Writing" />
      {posts.length === 0 ? (
        <EmptyState eyebrow="Writing">{EMPTY_COPY}</EmptyState>
      ) : (
        <ul className="writing-list">
          {posts.map(({ meta }) => (
            <li key={meta.slug} className="writing-list__item">
              <span className="mono">{meta.date}</span>
              <h2 className="writing-list__title">
                <Link href={`/writing/${meta.slug}`}>{meta.title}</Link>
              </h2>
              <p className="writing-list__summary">{meta.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
