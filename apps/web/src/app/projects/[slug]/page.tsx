import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Prose } from "@/components/Prose";
import { loadProject, loadProjects } from "@/content/load";
import { renderMdx } from "@/content/mdx";
import { PATTERNS } from "@/patterns";

type Params = Promise<{ slug: string }>;

export function generateStaticParams() {
  return loadProjects().map((project) => ({ slug: project.meta.slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const project = loadProject((await params).slug);
  if (!project) return {};
  return { title: project.meta.title, description: project.meta.summary };
}

export default async function ProjectPage({ params }: { params: Params }) {
  const project = loadProject((await params).slug);
  if (!project) notFound();
  const { meta } = project;
  const pattern = PATTERNS[meta.architecture];
  const body = await renderMdx(project.body, `projects/${meta.slug}`);

  return (
    <div className="container">
      <PageHeader
        eyebrow={pattern.name}
        eyebrowHref={`/architecture/${pattern.key}`}
        title={meta.title}
        lede={meta.summary}
      />
      <div className="meta-row">
        <span className={`mono project-card__status project-card__status--${meta.status}`}>
          {meta.status}
        </span>
        <span className="mono">{meta.date}</span>
        {meta.tryUrl ? (
          <a className="mono" href={meta.tryUrl} target="_blank" rel="noreferrer">
            Try it
          </a>
        ) : null}
        {meta.repoUrl ? (
          <a className="mono" href={meta.repoUrl} target="_blank" rel="noreferrer">
            Source
          </a>
        ) : null}
      </div>
      <Prose>{body}</Prose>
    </div>
  );
}
