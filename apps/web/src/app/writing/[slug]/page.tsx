import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Prose } from "@/components/Prose";
import { loadWriting, type Writing } from "@/content/load";
import { renderMdx } from "@/content/mdx";
import { INCLUDE_DRAFTS } from "../drafts";

type Params = Promise<{ slug: string }>;

function findPost(slug: string): Writing | undefined {
  return loadWriting(undefined, { includeDrafts: INCLUDE_DRAFTS }).find(
    (post) => post.meta.slug === slug,
  );
}

/** Unknown params 404 at build time instead of rendering on demand. */
export const dynamicParams = false;

/** With no posts yet this returns [] and the build still passes. */
export function generateStaticParams() {
  return loadWriting(undefined, { includeDrafts: INCLUDE_DRAFTS }).map(({ meta }) => ({
    slug: meta.slug,
  }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const post = findPost((await params).slug);
  if (!post) return {};
  return { title: post.meta.title, description: post.meta.summary };
}

export default async function WritingPostPage({ params }: { params: Params }) {
  const post = findPost((await params).slug);
  if (!post) notFound();
  const body = await renderMdx(post.body, `writing/${post.meta.slug}`);

  return (
    <div className="container">
      <PageHeader eyebrow={post.meta.date} title={post.meta.title} lede={post.meta.summary} />
      <Prose>{body}</Prose>
    </div>
  );
}
