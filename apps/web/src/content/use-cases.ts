import type { Project } from "./load";

export type UseCase = {
  slug: string;
  label: string;
  description: string;
  projects: Project[];
};

/**
 * Groups projects by `useCase.slug`, keeping the loader's order inside each
 * group. The first project's label and description define the use case;
 * any later project that disagrees is an authoring error.
 */
export function deriveUseCases(projects: readonly Project[]): UseCase[] {
  const groups = projects.reduce<Map<string, UseCase>>((acc, project) => {
    const { slug, label, description } = project.meta.useCase;
    const existing = acc.get(slug);
    if (existing === undefined) {
      return new Map(acc).set(slug, { slug, label, description, projects: [project] });
    }
    if (existing.label !== label) {
      throw new Error(
        `use case "${slug}": project "${project.meta.slug}" has label "${label}" but "${existing.projects[0].meta.slug}" has "${existing.label}"`,
      );
    }
    if (existing.description !== description) {
      throw new Error(
        `use case "${slug}": project "${project.meta.slug}" has a different description than "${existing.projects[0].meta.slug}"`,
      );
    }
    return new Map(acc).set(slug, { ...existing, projects: [...existing.projects, project] });
  }, new Map());
  return [...groups.values()].sort((a, b) => a.label.localeCompare(b.label));
}
