import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { PatternDiagram } from "@/components/PatternDiagram";
import { ProjectCard } from "@/components/ProjectCard";
import { Prose } from "@/components/Prose";
import { loadProjects } from "@/content/load";
import { PATTERN_KEYS, PATTERNS, type PatternKey } from "@/patterns";

type Params = Promise<{ pattern: string }>;

function asPatternKey(value: string): PatternKey | undefined {
  return PATTERN_KEYS.find((key) => key === value);
}

export function generateStaticParams() {
  return PATTERN_KEYS.map((pattern) => ({ pattern }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const key = asPatternKey((await params).pattern);
  if (!key) return {};
  const pattern = PATTERNS[key];
  return { title: pattern.name, description: pattern.oneLine };
}

export default async function ArchitecturePage({ params }: { params: Params }) {
  const key = asPatternKey((await params).pattern);
  if (!key) notFound();
  const pattern = PATTERNS[key];
  const projects = loadProjects().filter((p) => p.meta.architecture === key);

  return (
    <div className="container">
      <PageHeader eyebrow="Architecture" title={pattern.name} lede={pattern.oneLine} />
      <PatternDiagram pattern={key} size="page" />
      <Prose>
        {pattern.long.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </Prose>
      <section className="page-section" aria-label="Projects">
        <h2 className="page-section__title">Projects</h2>
        {projects.length === 0 ? (
          <EmptyState eyebrow="Projects">No projects here yet.</EmptyState>
        ) : (
          <div className="tile-grid">
            {projects.map((project) => (
              <ProjectCard key={project.meta.slug} project={project.meta} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
