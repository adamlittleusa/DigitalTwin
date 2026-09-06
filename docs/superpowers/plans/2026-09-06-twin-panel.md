# Twin Panel Implementation Plan (sub-project 4b)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A docked chat panel on every page of adambuilds.ai that streams answers from the twin API with one inline status line, project cards, and plain-sentence limits and errors; then flip the twin's project card to live.

**Architecture:** Pure modules first (`sse.ts`, `state.ts`, `api.ts`, `storage.ts`) with Vitest coverage, then client components wired into `layout.tsx`, then the launch flips. No new dependencies.

**Tech Stack:** The existing `apps/web` Next.js 16 app; `fetch` with `ReadableStream`; `sessionStorage`; Vitest.

**Spec:** `docs/superpowers/specs/2026-09-06-twin-panel-design.md`. API contract: `docs/superpowers/specs/2026-09-05-twin-api-design.md` sections 10 and 11 (request shape, error bodies `{code, message, retry_after?}`, SSE event payloads).

---

## Conventions

- Work in `apps/web`; branch `feat/twin-panel`; commits with the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Tokens only for styling; no new packages; every page stays static.
- Never touch `apps/twin`, `knowledge/`, `.env`. The API is live at `https://api.adambuilds.ai`; manual checks against it are allowed only in Task 5 and cost real model calls; automated tests never call it.

### Task 1: SSE parser and API client (pure)

- [ ] `src/twin/sse.ts`: `export function createSseParser(): { push(chunk: string): SseFrame[]; flush(): SseFrame[] }` where `SseFrame = { event: string; data: string }`. Rules: frames end at a blank line; `event:` and `data:` lines (a space after the colon is optional); multiple `data:` lines join with `\n`; lines starting with `:` are comments; unknown fields ignored; a frame without `event` is emitted as `message`; partial lines are kept until the next push; `\r\n` accepted.
- [ ] `src/twin/api.ts`: `apiBase(host = window.location.hostname)` returning `"http://localhost:8080"` for `localhost`/`127.0.0.1`, `"https://api.adambuilds.ai"` for `adambuilds.ai`/`www.adambuilds.ai`, `process.env.NEXT_PUBLIC_TWIN_API` when set (wins over the host rule), else `null` (off-domain). `fetchExamples(base)` → `string[]`. `streamChat(base, messages, onFrame, signal)`: POST JSON, on non-200 throw `ChatHttpError(status, body?: {code, message, retry_after?})` (parse JSON if possible), else read the body with `TextDecoder` through the parser, calling `onFrame` for each frame, resolve when the stream ends.
- [ ] Tests in `tests/twin/sse.test.ts` (frames split mid-line and mid-frame across pushes; comments; multi-line data; CRLF; a frame without event) and `tests/twin/api.test.ts` (`apiBase` per host and env; `streamChat` against a stubbed `fetch` returning a `ReadableStream` of two chunks; a 429 body becomes `ChatHttpError` with `retry_after`).
- [ ] Commit `feat(web): SSE parser and twin API client`.

### Task 2: State reducer and storage (pure)

- [ ] `src/twin/state.ts`: types `Message = { role: "user" | "assistant"; text: string; cards?: Card[] }`, `Card = { slug; title; summary }`, `Status = string | null`, `TwinState = { messages: Message[]; pending: { text: string; cards: Card[] } | null; status: Status; error: { text: string; retryable: boolean; retryAfter?: number } | null; open: boolean }`. Actions: `open`, `close`, `send(text)` (appends the user message, creates `pending`, clears error), `frame(event, data)` (per the spec's events-to-UI table; `done` moves `pending` to a final assistant message using `reply`; `agent_error` sets the pending text to `message`), `fail(text, retryable, retryAfter?)` (drops `pending`, sets `error`), `timeout`, `reset` (empties messages, keeps `open`). Helpers: `userTurns(state)`, `MAX_USER_TURNS = 8`, `canSend(state)`, `httpErrorText(status, body)` mapping per the spec table.
- [ ] `src/twin/storage.ts`: `loadState(): Partial<TwinState> | null` and `saveState(state)` under key `twin:v1`, storing only `messages` and `open`; try/catch around every `sessionStorage` access; `null` when unavailable.
- [ ] Tests in `tests/twin/state.test.ts` covering every action, the status text per event (including the "round 2" suffix), the eight-turn cap, `httpErrorText` for 429 with and without `retry_after`, 503 bodies, 400/413, 500; and `tests/twin/storage.test.ts` with a fake `sessionStorage`.
- [ ] Commit `feat(web): twin panel state and storage`.

### Task 3: Components and dock

- [ ] `src/components/twin/TwinDock.tsx` (client, `"use client"`): owns `useReducer` with the state module, hydrates from storage on mount (not during render, to avoid hydration mismatch), saves on change, listens for `window` `twin:open` events, fetches examples once when first opened, runs `streamChat` on send with an `AbortController` and a 90 s inactivity timer reset on every frame, dispatches `frame`/`fail`/`timeout`, and re-enables the composer after `retryAfter` seconds. Renders the dock button and, when open, `TwinPanel`.
- [ ] `TwinPanel.tsx`: the `dialog` (rendered as a `div role="dialog" aria-modal="true"` positioned by CSS, with a focus trap implemented by hand: on open focus the composer, keep Tab within the panel, Escape closes, on close return focus to the dock button). Header, greeting ("Ask me about Adam's work. I answer as him."), chips (`ExampleChips`, hidden once a message exists), `Transcript`, `Composer`, off-domain notice when `apiBase()` is null.
- [ ] `Transcript.tsx`: messages as paragraphs (split on blank lines), user messages right-aligned on `--surface-raised`, assistant messages plain; the pending reply with a blinking-free caret (a static `▍` in `--text-3`); the status line under it (`aria-live="polite"`, mono, `--text-3`); `ProjectCardInline` for cards (title, summary, link to `/projects/<slug>` via `next/link`); the error line with Retry when `retryable`; `role="log"`, `aria-live="polite"`, auto-scroll to bottom on change.
- [ ] `Composer.tsx`: textarea (auto-grow to 4 lines), Enter sends, Shift+Enter newline, send button; disabled while pending, when `!canSend`, and off-domain; the "full conversation" replacement with a Start-over button at the cap.
- [ ] `OpenTwinButton.tsx` (client): renders a button with the given children that dispatches `new CustomEvent("twin:open")`.
- [ ] CSS under `/* twin */` in `globals.css`: dock button (fixed, bottom `--space-3`, right `--space-3`, pill, mono, raised surface, hairline), panel (fixed right, width 420 px, full height, `--surface`, hairline left border, slide-in over `--t-fast`, full screen under 700 px), transcript bubbles, chips, composer, status, cards. Reduced motion disables the slide.
- [ ] Mount `<TwinDock />` in `layout.tsx` after the footer. Verify `npm run build` keeps every route static (the dock is a client component inside a static layout, fine).
- [ ] Commit `feat(web): the twin panel`.

### Task 4: Launch flips and accessibility pass

- [ ] `content/projects/digital-twin.mdx`: `status: live`; add a "Try it" that opens the panel: since MDX renders `OpenTwinButton`, register it in `src/content/mdx.tsx` components and place `<OpenTwinButton>Ask the twin</OpenTwinButton>` at the end of "What it does". Keep `tryUrl` absent (the project page's meta row shows "Try it" only when `tryUrl` exists; instead show the button in the body).
- [ ] `SiteFooter.tsx`: replace the "Email: ask the twin" text with `<OpenTwinButton>Ask the twin</OpenTwinButton>` styled as a mono link.
- [ ] `content/about.mdx`: end with a line "Anything else, ask the twin." using the button.
- [ ] Run Lighthouse locally (`npx lighthouse http://localhost:3000/ --only-categories=accessibility` against `npm run start` after a build) on `/` and `/projects/digital-twin`; fix every failing audit it lists in this branch (4a scored 96 and 95). Record what was fixed in the plan's deviations.
- [ ] `npm run lint`, `typecheck`, `test`, `build`. Commit `feat(web): the twin is live on the site; accessibility fixes`.

### Task 5: Verify, PR, merge

- [ ] `npm run dev` with the site pointed at production (`NEXT_PUBLIC_TWIN_API=https://api.adambuilds.ai`): open the panel, send "Where are you based?", confirm the status line changes and the answer streams; ask "Tell me about the digital twin project" and confirm a card appears and links to the project page; ask "Why did you leave Corelight?" and confirm the status shows "passing this along to Adam" and the reply deflects (one real push). Close, navigate, reopen: transcript intact. Keyboard only: open with Enter on the dock, Tab stays inside, Escape closes and focus returns.
- [ ] Push, open a PR "The twin panel", wait for the `web` job, merge. Verify on `https://adambuilds.ai` (the CORS origin is the production host, so the panel works only there), including on a phone.
- [ ] Record deviations in this plan; update the roadmap memory.
