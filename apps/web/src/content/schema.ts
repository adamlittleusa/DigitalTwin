import { z } from "zod";
import { PATTERN_KEYS } from "@/patterns";

const slug = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

export const useCaseSchema = z.object({
  slug,
  label: z.string().min(1),
  description: z.string().min(1),
});

export const projectSchema = z
  .object({
    title: z.string().min(1),
    slug,
    summary: z.string().min(1),
    architecture: z.enum(PATTERN_KEYS),
    useCase: useCaseSchema,
    status: z.enum(["live", "building", "retired"]),
    date: isoDate,
    tryUrl: z.url().optional(),
    repoUrl: z.url().optional(),
  })
  .strict();

export const writingSchema = z
  .object({
    title: z.string().min(1),
    date: isoDate,
    summary: z.string().min(1),
    draft: z.boolean().default(false),
  })
  .strict();

export type ProjectMeta = z.infer<typeof projectSchema>;
export type WritingMeta = z.infer<typeof writingSchema> & { slug: string };
