import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Prose } from "@/components/Prose";
import { loadAbout } from "@/content/load";
import { renderMdx } from "@/content/mdx";

export const metadata: Metadata = {
  title: "About",
  description: "How Adam Little went from intelligence operations to building agents.",
};

export default async function AboutPage() {
  const body = await renderMdx(loadAbout().body, "about");
  return (
    <div className="container">
      <PageHeader title="About" />
      <Prose>{body}</Prose>
    </div>
  );
}
