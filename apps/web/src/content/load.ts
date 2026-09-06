import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import type { ZodType } from "zod";
import { projectSchema, writingSchema, type ProjectMeta, type WritingMeta } from "./schema";

const MDX_EXT = ".mdx";

export type Project = { meta: ProjectMeta; body: string };
export type Writing = { meta: WritingMeta; body: string };
export type About = { body: string };

export type LoadWritingOptions = { includeDrafts?: boolean };

export function contentDir(kind: "projects" | "writing"): string {
  return path.join(process.cwd(), "content", kind);
}

function listMdx(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    throw new Error(`${dir}: content directory does not exist`);
  }
  return fs
    .readdirSync(dir)
    .filter((name) => name.endsWith(MDX_EXT))
    .sort()
    .map((name) => path.join(dir, name));
}

function stemOf(file: string): string {
  return path.basename(file, MDX_EXT);
}

/**
 * YAML reads a bare `2026-01-02` as a Date. The schema wants the string the
 * author typed, so Dates are turned back into `YYYY-MM-DD` (UTC) before
 * validation. Nested objects are walked; nothing else is touched.
 */
function normalizeDates(value: unknown): unknown {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (Array.isArray(value)) return value.map(normalizeDates);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, inner]) => [key, normalizeDates(inner)]),
    );
  }
  return value;
}

function parseFile<T>(file: string, schema: ZodType<T>): { meta: T; body: string } {
  const raw = fs.readFileSync(file, "utf8");
  const { data, content } = matter(raw);
  const result = schema.safeParse(normalizeDates(data));
  if (!result.success) {
    const issues = result.error.issues
      .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
      .join("; ");
    throw new Error(`${file}: invalid frontmatter (${issues})`);
  }
  return { meta: result.data, body: content };
}

function compareByDateThenSlug(
  a: { date: string; slug: string },
  b: { date: string; slug: string },
): number {
  return a.date.localeCompare(b.date) || a.slug.localeCompare(b.slug);
}

export function loadProjects(dir: string = contentDir("projects")): Project[] {
  const seen = new Map<string, string>();
  const projects = listMdx(dir).map((file) => {
    const project = parseFile(file, projectSchema);
    const stem = stemOf(file);
    const previous = seen.get(project.meta.slug);
    if (previous !== undefined) {
      throw new Error(`${file}: duplicate slug "${project.meta.slug}" (also in ${previous})`);
    }
    seen.set(project.meta.slug, file);
    if (project.meta.slug !== stem) {
      throw new Error(
        `${file}: frontmatter slug "${project.meta.slug}" does not match file name "${stem}"`,
      );
    }
    return project;
  });
  return [...projects].sort((a, b) => compareByDateThenSlug(a.meta, b.meta));
}

export function loadProject(slug: string, dir?: string): Project | undefined {
  return loadProjects(dir).find((project) => project.meta.slug === slug);
}

export function loadWriting(
  dir: string = contentDir("writing"),
  { includeDrafts = false }: LoadWritingOptions = {},
): Writing[] {
  const posts = listMdx(dir).map((file) => {
    const { meta, body } = parseFile(file, writingSchema);
    return { meta: { ...meta, slug: stemOf(file) }, body };
  });
  return posts
    .filter((post) => includeDrafts || !post.meta.draft)
    .sort((a, b) => compareByDateThenSlug(a.meta, b.meta));
}

export function loadAbout(file: string = path.join(process.cwd(), "content", "about.mdx")): About {
  if (!fs.existsSync(file)) {
    throw new Error(`${file}: about page does not exist`);
  }
  const { content } = matter(fs.readFileSync(file, "utf8"));
  return { body: content };
}
