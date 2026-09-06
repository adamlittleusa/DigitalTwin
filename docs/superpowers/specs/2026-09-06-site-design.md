# adambuilds.ai Site Design (sub-project 4a)

Approved in conversation on 2026-09-06. This document is the handoff: an
agent or a person with this file, the repo, and the API spec can build the
site without the conversation that produced it.

## 1. Goal

A high-end personal portfolio for someone who builds agents, at
`https://adambuilds.ai`. The front page is a gallery of buckets, not of
projects: it toggles between the six agent architecture patterns and the use
cases the projects serve. Project pages tell each project's story. An About
page carries the career arc. A Writing section starts empty and grows by
commits. The digital twin's chat panel is sub-project 4b and docks onto this
site afterwards.

## 2. Context

- The twin API is live at `https://api.adambuilds.ai` (spec
  `2026-09-05-twin-api-design.md`, deployment `2026-09-06-twin-deployment-design.md`).
  It streams Server-Sent Events (`step`, `tool`, `tool_result`, `delta`,
  `project`, `done`, `agent_error`) and serves `/v1/projects` cards whose
  `url` is `https://adambuilds.ai/projects/<slug>`. Its allowed origins are
  `https://adambuilds.ai` and `https://www.adambuilds.ai`.
- `apps/web/` is an empty placeholder in the monorepo. Node 24 is installed.
- The domain is at GoDaddy on GoDaddy DNS; `api` is a CNAME to Fly. The apex
  and `www` are unconfigured.
- Adam's aesthetic reference is https://linear.app. Sites he was shown and
  did not pick: paco.me, leerob.com, brianlovin.com (editorial); rauno.me,
  brittanychiang.com (dark technical); joshwcomeau.com, maggieappleton.com
  (warm). He wants nothing that reads as AI-generated: no gradient blobs,
  no purple glow, no stock icon grids, no template components.
- The twin's knowledge lives in `knowledge/` and is written for the model.
  Site content is written for readers and lives separately.

## 3. Decisions

| Question | Decision |
|---|---|
| Stack | Next.js (App Router), TypeScript, hand-written CSS with design tokens, MDX content, no UI library, no Tailwind. |
| Hosting | Vercel project rooted at `apps/web`, previews per pull request, production on `adambuilds.ai`, `www` redirects to the apex. |
| Front page | A gallery of buckets with a toggle: architecture patterns (six, fixed) or use cases (derived from the projects). No project is listed on the front page. |
| Architecture buckets | The five workflow patterns from Anthropic's "Building effective agents" (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer) plus the sixth shape, the autonomous agent. The twin is an autonomous agent. |
| Use-case buckets | Not designed up front. Each project names its use case as a business capability one layer above the domain (what an SMB would buy). A use-case tile exists only because a project does. |
| Content | Markdown/MDX files in the repo, frontmatter validated at build. |
| Pages | Home, six architecture pages, N use-case pages, project pages, About (arc plus LinkedIn), Writing (list and posts). |
| Twin | A docked panel on every page, built in 4b. In 4a the dock button exists but is hidden. |
| Look | Linear-like: dark ground, faint grid, one cool accent, Geist Sans and Geist Mono, typographic tiles with line diagrams, motion only on interaction. |
| Empty states | Honest. A pattern with no project says so in one line. Writing with no posts says the first piece is coming. Nothing says "coming soon" as decoration. |

## 4. Out of scope (4a)

- The chat panel and anything that calls the API at runtime (4b).
- Light mode (tokens make it a later addition).
- Search, tags, comments, newsletter, analytics beyond Vercel's built-in.
- A CMS. Publishing is a commit.
- Blog RSS (cheap later; not needed with zero posts).

## 5. Routes and pages

| Route | Page |
|---|---|
| `/` | Gallery. Toggle "Architecture" / "Use cases"; `/?view=use-cases` selects the second so it is linkable. One line of identity above the tiles: name, what he builds, a link to About. |
| `/architecture/[pattern]` | One of six. Title, the pattern explained in three to five short paragraphs in Adam's voice, its diagram large, then the projects in it as cards, or the one-line empty state. |
| `/use-cases/[slug]` | Derived. Title and description come from the projects that declare the slug (the first project's `useCase.description` wins; the build fails if two projects describe the same slug differently). Then the projects. |
| `/projects/[slug]` | Story: what it is, why it exists, how it is built (with the pattern diagram and a link to the pattern page), what it does, status, "Try it" and "Source" links. |
| `/about` | The career arc in reader's prose (from `knowledge/career-arc.md` and the roles, rewritten, reviewed by Adam), a photo if Adam supplies one, a LinkedIn link, and "ask the twin" (hidden until 4b). |
| `/writing` | List of posts by date; empty state text when none. |
| `/writing/[slug]` | A post. |
| `/not-found` | Styled 404 that links home. |

Every page is static at build time (`generateStaticParams` for the dynamic
routes). Metadata: title, description, Open Graph image (a generated dark
card with the page title in Geist) per page.

## 6. Content model

`apps/web/content/projects/<slug>.mdx`, frontmatter:

```yaml
title: Digital twin
slug: digital-twin
summary: An agent that answers questions about my career, in my voice, and knows when to hand off to me.
architecture: autonomous-agent        # one of the six keys below
useCase:
  slug: expert-front-door
  label: An always-on expert that answers in your voice
  description: A customer-facing agent that knows one person's or one company's material deeply, answers within stated boundaries, and hands the conversation to a human when it should.
status: live                          # live | building | retired
date: 2026-09-06
tryUrl: https://adambuilds.ai         # optional; for the twin it is the site itself (the panel)
repoUrl: https://github.com/adamlittleusa/DigitalTwin
```

Body: MDX prose with the sections above as `##` headings; the diagram is a
component (`<PatternDiagram pattern="autonomous-agent" />`) placed by the
author.

Architecture keys and display names, fixed in `apps/web/src/patterns.ts`:

| Key | Name | One-line |
|---|---|---|
| `prompt-chaining` | Prompt chaining | Steps in sequence, each one's output the next one's input, with checks between. |
| `routing` | Routing | Classify the input, send it to the specialist path that fits. |
| `parallelization` | Parallelization | Run independent pieces at once, then combine or vote. |
| `orchestrator-workers` | Orchestrator-workers | One agent breaks the task down and hands parts to workers, then assembles. |
| `evaluator-optimizer` | Evaluator-optimizer | One agent produces, another judges, and the loop runs until the judge is satisfied. |
| `autonomous-agent` | Autonomous agent | A model in a loop with tools, deciding its own next step until the job is done. |

Each key also has a `long` description (three to five paragraphs, drafted by
the implementer in Adam's voice from the essay's definitions and reviewed by
Adam before merge) and a diagram component.

`apps/web/content/writing/<slug>.mdx`: `title`, `date`, `summary`,
`draft: true|false`. Drafts build locally and are excluded in production.

Validation: a Zod schema per content type; `next build` runs the loader and
fails on any invalid file, unknown architecture key, duplicate slug, or
conflicting use-case description. The loader is a plain TypeScript module
under `src/content/` with unit tests.

## 7. Design system

Tokens in `apps/web/src/styles/tokens.css`, consumed everywhere; no
hard-coded colours or sizes elsewhere.

- **Colour.** Ground `#0b0c0f`; raised surface `#111318`; hairline
  `rgba(255,255,255,0.08)`; text primary `#ececf1`, secondary `#a3a7b3`,
  muted `#6b7080`; accent `#9ec1ff` (cool blue-white), used for links,
  focus rings, the active toggle, and diagram highlights, never for large
  fills. A faint grid on the ground: 1 px lines every 48 px at 3 percent
  white, fading out toward the page edges.
- **Type.** Geist Sans for text, Geist Mono for labels, metadata, pattern
  keys, and code, both via `next/font` (self-hosted, no layout shift).
  Scale: 13, 15, 17 (body), 22, 28, 40, 56 px; line height 1.5 for body,
  1.1 for display; tracking slightly negative above 28 px. Mono labels are
  13 px uppercase with 0.08 em tracking.
- **Space and grid.** An 8 px base; page gutter 24 px on phones, 48 px
  above 900 px; content max width 1120 px; tiles on a 12-column grid, three
  across on desktop, two on tablet, one on phones.
- **Surfaces.** Tiles are a raised surface with a hairline border and 12 px
  radius; on hover the border brightens to 16 percent and the diagram
  draws in. No shadows except a 1 px inner highlight on raised surfaces.
- **Motion.** 160 ms ease-out for hover states; the diagram draw-in is a
  stroke-dashoffset animation of 600 ms, once, on hover or focus; the
  toggle cross-fades views in 200 ms. Nothing loops. `prefers-reduced-motion`
  disables the draw-in and the cross-fade.
- **Diagrams.** One inline SVG component per pattern, drawn with boxes,
  arrows, and mono labels in the token colours, with a `size` prop (tile or
  page). They are real diagrams of the pattern, not icons.
- **Components.** `Tile`, `PatternDiagram`, `ViewToggle`, `PageHeader`,
  `Prose` (MDX styles), `ProjectCard`, `EmptyState`, `SiteHeader` (name,
  Architecture, Use cases, About, Writing), `SiteFooter` (LinkedIn, GitHub,
  email hand-off text). Keyboard reachable, visible focus rings, colour
  contrast at least 4.5:1 for text.

## 8. Hosting, DNS, CI

- **Vercel.** Import the GitHub repo, root directory `apps/web`, framework
  Next.js, production branch `main`. Add the domains `adambuilds.ai` and
  `www.adambuilds.ai`; set `www` to redirect to the apex. Vercel shows the
  DNS values to use.
- **GoDaddy.** An `A` record for `@` to Vercel's address (currently
  `76.76.21.21`; use what Vercel displays) and a `CNAME` for `www` to
  `cname.vercel-dns.com`. Leave `api` untouched.
- **CI.** `.github/workflows/web.yml` on pull requests and pushes to `main`
  touching `apps/web/**`: `npm ci`, `npm run lint`, `npm run typecheck`,
  `npm run test`, `npm run build`. No deploy step; Vercel deploys.
- **Previews.** Every PR gets a preview URL. In 4a nothing calls the API.

## 9. Content at launch

- Project: the twin, under `autonomous-agent`, use case as in section 6,
  story written from `knowledge/projects/digital-twin.md` for readers,
  reviewed by Adam.
- The six pattern pages with their long descriptions and diagrams; five say
  "No projects here yet."
- About: the arc, from `knowledge/career-arc.md` and the role files, in
  reader's prose, with the LinkedIn link and the same boundaries the twin
  keeps (nothing about why any role ended; Corelight wrapped up August 2026).
- Writing: empty state.

## 10. Verification

- Unit tests (Vitest) for the content loader: valid files load; each
  invalid case fails with the file name; use-case derivation merges projects
  by slug and rejects conflicting descriptions.
- `next build` succeeds with the launch content and fails when a fixture
  breaks a rule.
- A link check over the built site (internal links resolve).
- Lighthouse on the production URL: performance, accessibility, best
  practices, SEO each 95 or above.
- Manual: every page on a phone and a desktop; the toggle is keyboard
  reachable and preserves position; reduced motion honoured.

## 11. Risks

- The pattern write-ups and the About page are Adam's voice and need his
  review like the knowledge files; the plan makes that a gate.
- A hand-built design system is slower than a template; the token file and
  component list above are the whole system, and nothing beyond it is added
  in 4a.
- One project makes a thin gallery. The tiles are about the patterns, so
  the page reads as a map of what he builds, not an empty shop.
- The site is public before the twin panel exists; the hidden dock button
  keeps 4b from changing the layout.

## 12. Sub-project 4b, the twin panel (outline, its own spec)

A docked button on every page opens a side panel. The client posts to
`https://api.adambuilds.ai/v1/chat` with the conversation so far (the API is
stateless; the panel keeps the messages in `sessionStorage`, at most eight
user turns, then offers a fresh start). It renders the stream: a quiet
timeline of `step` and `tool` labels above the growing reply, `project`
events as clickable cards routed to `/projects/<slug>`, `agent_error` as a
one-line notice, and the 429 and 503 shapes as plain sentences with the
retry time. Example questions come from `/v1/examples`. The panel remembers
open/closed state per session and is reachable by keyboard.

## 13. Follow-on

- 4b as above.
- Light mode, RSS, Open Graph refinements, analytics, once there is content.
