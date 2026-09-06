import { describe, expect, it } from "vitest";
import type { Project } from "@/content/load";
import { deriveUseCases } from "@/content/use-cases";

const project = (
  slug: string,
  useCase: { slug: string; label: string; description: string },
): Project => ({
  meta: {
    title: slug,
    slug,
    summary: "s",
    architecture: "routing",
    useCase,
    status: "live",
    date: "2026-01-01",
  },
  body: "",
});

const frontDoor = { slug: "front-door", label: "Zeta front door", description: "Answers." };
const review = { slug: "review", label: "Alpha review", description: "Reviews." };

describe("deriveUseCases", () => {
  it("groups by slug in loader order and sorts groups by label", () => {
    const cases = deriveUseCases([
      project("one", frontDoor),
      project("two", review),
      project("three", frontDoor),
    ]);
    expect(cases.map((c) => c.slug)).toEqual(["review", "front-door"]);
    expect(cases[1].projects.map((p) => p.meta.slug)).toEqual(["one", "three"]);
    expect(cases[1]).toMatchObject({ label: "Zeta front door", description: "Answers." });
  });

  it("returns nothing for no projects", () => {
    expect(deriveUseCases([])).toEqual([]);
  });

  it("throws on a conflicting description", () => {
    expect(() =>
      deriveUseCases([
        project("one", frontDoor),
        project("two", { ...frontDoor, description: "Different." }),
      ]),
    ).toThrow(/front-door.*"two".*different description/);
  });

  it("throws on a conflicting label", () => {
    expect(() =>
      deriveUseCases([project("one", frontDoor), project("two", { ...frontDoor, label: "Other" })]),
    ).toThrow(/front-door.*"two".*label "Other"/);
  });
});
