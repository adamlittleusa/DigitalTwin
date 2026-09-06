import { evaluate } from "next-mdx-remote-client/rsc";
import type { MDXComponents } from "next-mdx-remote-client/rsc";
import { PatternDiagram } from "@/components/PatternDiagram";
import { OpenTwinButton } from "@/components/twin/OpenTwinButton";

/** Components MDX bodies may use by name. */
const MDX_COMPONENTS: MDXComponents = { PatternDiagram, OpenTwinButton };

/**
 * Renders an MDX body to a React element at build time. A syntax error in
 * the content is an authoring error, so it fails the build rather than
 * rendering a broken page.
 */
export async function renderMdx(source: string, label: string) {
  const { content, error } = await evaluate({ source, components: MDX_COMPONENTS });
  if (error) {
    throw new Error(`${label}: MDX failed to compile (${error.message})`);
  }
  return content;
}
