import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { ProjectCard } from "@/components/ProjectCard";
import { loadProjects } from "@/content/load";
import { deriveUseCases, type UseCase } from "@/content/use-cases";

type Params = Promise<{ slug: string }>;

function findUseCase(slug: string): UseCase | undefined {
  return deriveUseCases(loadProjects()).find((useCase) => useCase.slug === slug);
}

/** Unknown params 404 at build time instead of rendering on demand. */
export const dynamicParams = false;

export function generateStaticParams() {
  return deriveUseCases(loadProjects()).map(({ slug }) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const useCase = findUseCase((await params).slug);
  if (!useCase) return {};
  return { title: useCase.label, description: useCase.description };
}

export default async function UseCasePage({ params }: { params: Params }) {
  const useCase = findUseCase((await params).slug);
  if (!useCase) notFound();

  return (
    <div className="container">
      <PageHeader eyebrow="Use case" title={useCase.label} lede={useCase.description} />
      <div className="tile-grid page-section">
        {useCase.projects.map((project) => (
          <ProjectCard key={project.meta.slug} project={project.meta} headingLevel="h2" />
        ))}
      </div>
    </div>
  );
}
