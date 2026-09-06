import Link from "next/link";
import type { HeadingLevel } from "@/components/Tile";
import type { ProjectMeta } from "@/content/schema";

interface ProjectCardProps {
  project: ProjectMeta;
  headingLevel?: HeadingLevel;
}

const STATUS_LABEL: Record<ProjectMeta["status"], string> = {
  live: "live",
  building: "building",
  retired: "retired",
};

export function ProjectCard({ project, headingLevel = "h3" }: ProjectCardProps) {
  const Heading = headingLevel;
  return (
    <Link href={`/projects/${project.slug}`} className="project-card">
      <div className="project-card__row">
        <Heading className="project-card__title">{project.title}</Heading>
        <span
          className={`mono project-card__status project-card__status--${project.status}`}
        >
          {STATUS_LABEL[project.status]}
        </span>
      </div>
      <p className="project-card__summary">{project.summary}</p>
      <span className="mono project-card__date">{project.date}</span>
    </Link>
  );
}
