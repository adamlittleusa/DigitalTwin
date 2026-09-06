import path from "node:path";
import { describe, expect, it } from "vitest";
import { loadAbout, loadProject, loadProjects, loadWriting } from "@/content/load";

const fixture = (...parts: string[]) => path.join(__dirname, "fixtures", ...parts);

describe("loadProjects", () => {
  it("loads valid files and sorts by date then slug", () => {
    const projects = loadProjects(fixture("valid", "projects"));
    expect(projects.map((p) => p.meta.slug)).toEqual(["beta", "gamma", "alpha"]);
    expect(projects[0].meta.title).toBe("Beta");
    expect(projects[0].meta.architecture).toBe("routing");
    expect(projects[0].body).toContain("Body of beta");
  });

  it("rejects an unknown architecture key, naming the file", () => {
    const dir = fixture("invalid-architecture");
    expect(() => loadProjects(dir)).toThrow(/architecture/);
    expectStartsWith(() => loadProjects(dir), path.join(dir, "bad.mdx"));
  });

  it("rejects a slug that does not match the file name", () => {
    const dir = fixture("slug-mismatch");
    const file = path.join(dir, "wrong-name.mdx");
    expect(() => loadProjects(dir)).toThrow(/does not match/);
    expectStartsWith(() => loadProjects(dir), file);
  });

  it("rejects duplicate slugs", () => {
    const dir = fixture("duplicate-slugs");
    const file = path.join(dir, "alpha2.mdx");
    expect(() => loadProjects(dir)).toThrow(/duplicate slug "alpha"/);
    expectStartsWith(() => loadProjects(dir), file);
  });

  it("reports a missing directory by path", () => {
    const dir = fixture("nope");
    expectStartsWith(() => loadProjects(dir), dir);
  });
});

describe("loadProject", () => {
  it("finds a project by slug and returns undefined otherwise", () => {
    const dir = fixture("valid", "projects");
    expect(loadProject("alpha", dir)?.meta.title).toBe("Alpha");
    expect(loadProject("missing", dir)).toBeUndefined();
  });
});

describe("loadWriting", () => {
  it("excludes drafts by default and takes the slug from the file stem", () => {
    const posts = loadWriting(fixture("writing"));
    expect(posts.map((p) => p.meta.slug)).toEqual(["published"]);
    expect(posts[0].meta.draft).toBe(false);
  });

  it("includes drafts when asked", () => {
    const posts = loadWriting(fixture("writing"), { includeDrafts: true });
    expect(posts.map((p) => p.meta.slug)).toEqual(["published", "draft-post"]);
  });
});

describe("loadAbout", () => {
  it("returns the body", () => {
    expect(loadAbout(fixture("about.mdx")).body).toContain("About body.");
  });

  it("reports a missing file by path", () => {
    const file = fixture("missing-about.mdx");
    expectStartsWith(() => loadAbout(file), file);
  });
});

function expectStartsWith(fn: () => unknown, prefix: string): void {
  let message = "";
  try {
    fn();
  } catch (error) {
    message = error instanceof Error ? error.message : String(error);
  }
  expect(message.startsWith(prefix), `expected "${message}" to start with "${prefix}"`).toBe(true);
}
