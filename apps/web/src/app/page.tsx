import Link from "next/link";
import { Suspense } from "react";
import { PatternDiagram } from "@/components/PatternDiagram";
import { Tile } from "@/components/Tile";
import { StaticViewToggle, ViewToggle } from "@/components/ViewToggle";
import { loadProjects } from "@/content/load";
import { deriveUseCases } from "@/content/use-cases";
import { PATTERN_LIST } from "@/patterns";

const IDENTITY_LINE =
  "I build agents. Here is the map of what I make, by architecture or by what it solves.";

function projectCount(n: number): string {
  if (n === 0) return "No projects yet";
  return n === 1 ? "1 project" : `${n} projects`;
}

/**
 * The gallery is static. Both grids are rendered; `ViewToggle` reads
 * `?view=` on the client and sets `data-view` on `#gallery`, and CSS shows
 * the matching grid (architecture by default). The prerendered HTML carries
 * `StaticViewToggle` (architecture active) until the client toggle hydrates.
 */
export default function Home() {
  const projects = loadProjects();
  const useCases = deriveUseCases(projects);

  return (
    <div className="container">
      <section className="identity">
        <h1 className="identity__name">Adam Little.</h1>{" "}
        <p className="identity__line">
          {IDENTITY_LINE} <Link href="/about">About me</Link>
        </p>
      </section>

      <section id="gallery" className="gallery" aria-label="Gallery">
        <Suspense fallback={<StaticViewToggle />}>
          <ViewToggle />
        </Suspense>

        <div className="tile-grid gallery__grid gallery__grid--architecture">
          {PATTERN_LIST.map((pattern) => (
            <Tile
              key={pattern.key}
              href={`/architecture/${pattern.key}`}
              eyebrow={pattern.key}
              headingLevel="h2"
              title={pattern.name}
              description={pattern.oneLine}
              diagram={<PatternDiagram pattern={pattern.key} size="tile" />}
              count={projectCount(
                projects.filter((p) => p.meta.architecture === pattern.key).length,
              )}
            />
          ))}
        </div>

        <div className="tile-grid gallery__grid gallery__grid--use-cases">
          {useCases.map((useCase) => (
            <Tile
              key={useCase.slug}
              href={`/use-cases/${useCase.slug}`}
              eyebrow="Use case"
              headingLevel="h2"
              title={useCase.label}
              description={useCase.description}
              count={projectCount(useCase.projects.length)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
