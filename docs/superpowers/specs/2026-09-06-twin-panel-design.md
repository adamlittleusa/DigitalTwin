# Twin Panel Design (sub-project 4b)

Approved in conversation on 2026-09-06. Builds on the site spec
(`2026-09-06-site-design.md`, section 12) and the API spec
(`2026-09-05-twin-api-design.md`, sections 6, 10, 11).

## 1. Goal

A docked chat panel on every page of `adambuilds.ai` that talks to the twin
API, streams the answer as it arrives, shows one quiet status line while the
twin works, renders project cards the twin sends, and handles every limit
and error in a plain sentence. Shipping it flips the twin's project card to
live.

## 2. Decisions

| Question | Decision |
|---|---|
| Greeting | Quiet. One line in the twin's voice plus the four example questions from `/v1/examples` as chips. Never auto-opens. |
| Loop visibility | Inline status only: a single mono line under the pending reply that changes with the events and disappears when the answer lands. No timeline. |
| Transcript | Held in `sessionStorage` (survives navigation within a tab, not across tabs); at most eight user turns, then "start a new one". |
| Rendering | Plain paragraphs; no markdown library. |
| Off-domain | On any host other than `adambuilds.ai` (previews, other domains) the panel says the twin only answers on adambuilds.ai. `localhost` targets `http://localhost:8080`. |
| Launch flips | Project status `live` with a "Try it" that opens the panel; footer and About "ask the twin" become buttons. |

## 3. Behaviour

**Dock.** A fixed button, bottom right, mono label "Ask the twin", on every
page. Click, or the keyboard, opens the panel; Escape or the close button
closes it. Open state is remembered in `sessionStorage`.

**Panel.** A `dialog` element, 420 px wide on desktop docked to the right
edge, full screen under 700 px. Header: "Adam's twin" and a close button.
Body: greeting line, example chips (until the first message is sent), the
transcript, the pending reply with its status line, then the input row
(textarea that grows to four lines, Enter sends, Shift+Enter newlines, a send
button). Focus is trapped while open and returns to the dock button on
close.

**Sending.** `POST {API}/v1/chat` with `{ messages }` being the full
transcript plus the new user message (the API is stateless). The response
is `text/event-stream`; the client reads it with `fetch` and a small SSE
parser (event and data lines, blank-line delimited, comments ignored).

**Events to UI.**

| Event | Effect |
|---|---|
| `step` `{phase, round}` | Status line: "thinking" or "composing" (round shown as "round 2" only when above 1). |
| `tool` `{label}` | Status line: the label, lower-cased ("passing this along to Adam"). |
| `tool_result` `{ok}` | No change; a failed tool shows nothing (the twin's text explains). |
| `delta` `{text}` | Append to the pending reply. |
| `project` `{slug, title, summary, url}` | A card under the pending reply: title, summary, a link to `/projects/<slug>` (the `url` is absolute; use its path). |
| `done` `{reply, rounds}` | Pending reply becomes final (use `reply` as the canonical text); status line cleared. |
| `agent_error` `{code, message}` | Show `message` as the reply text in the twin's voice; the turn still ends with `done`. |

**Limits and errors.**

| Situation | The panel shows |
|---|---|
| Ninth user turn | Input replaced by "That's a full conversation. Start a new one?" with a button that clears the transcript. |
| HTTP 429 | "Too many questions for the moment. Try again in N seconds." using the body's `retry_after`; the input re-enables after N seconds. |
| HTTP 503 `resting` or `busy` | The body's `message` verbatim. |
| HTTP 400 or 413 | "That message didn't go through" (a client bug; log it to the console). |
| HTTP 500 or network failure | "Couldn't reach the twin." with a Retry button that resends the same message. |
| No `done` within 90 s | The turn ends with "The twin lost the thread. Try again." |
| Off-domain host | Input disabled; "The twin only answers on adambuilds.ai." |

The user's message stays in the transcript on failure so Retry can resend
it; the failed pending reply is removed.

**Cards.** A `project` card renders once per slug per turn (the API already
deduplicates). Clicking navigates with the Next router; the panel stays
open.

## 4. Structure (all under `apps/web/src/`)

| File | Responsibility |
|---|---|
| `twin/api.ts` | `apiBase()` (host check), `fetchExamples()`, `streamChat(messages, onEvent, signal)` with the SSE parser. Pure with respect to the DOM. |
| `twin/sse.ts` | `parseSseChunk` state machine: bytes in, `{event, data}` frames out. Unit tested. |
| `twin/state.ts` | The reducer: transcript, pending reply, status, error, turn count, `start`, `event`, `finish`, `fail`, `reset`. Pure. Unit tested. |
| `twin/storage.ts` | `sessionStorage` read/write with try/catch and a version key. |
| `components/twin/TwinDock.tsx` | Client component: the button plus the panel; wires state, storage, and the stream; installed once in `layout.tsx`. |
| `components/twin/TwinPanel.tsx`, `Transcript.tsx`, `ProjectCardInline.tsx`, `Composer.tsx` | Presentation. |
| `components/twin/OpenTwinButton.tsx` | A small client button that dispatches a `twin:open` window event, used by the project page "Try it", the footer, and About. |

CSS in `globals.css` under `/* twin */`, tokens only. Motion: the panel
slides in over `--t-fast`; disabled under reduced motion.

## 5. Accessibility

`dialog` with `aria-labelledby`; focus trap; Escape closes; the transcript
is `role="log"` with `aria-live="polite"`; the status line is
`aria-live="polite"` and `aria-atomic`; the dock button has `aria-expanded`;
chips are buttons; contrast per the site tokens. The 4a Lighthouse
accessibility findings (whatever the audit lists on the home and project
pages) are fixed in the same branch.

## 6. Configuration

`NEXT_PUBLIC_TWIN_API` optional; when unset the client derives the base:
`localhost` → `http://localhost:8080`, `adambuilds.ai` or `www` →
`https://api.adambuilds.ai`, anything else → off-domain mode. No secrets in
the site.

## 7. Verification

- Vitest: the SSE parser (split frames across chunks, comments, multi-line
  data); the reducer for every event and error path, the eight-turn cap, and
  reset; the error mapping from status codes and bodies; `apiBase()` per
  host.
- `npm run build` static; the link check still passes (the panel adds no
  routes).
- Manual on the live site: open, ask the four examples, see a project card
  and follow it, hit the Corelight question and see the deflection with the
  status "passing this along to Adam", close and reopen with the transcript
  intact, a new tab starts fresh, phone layout, keyboard only.

## 8. Risks

- **Two copies of the conversation cap.** The API enforces eight user
  messages; the client mirrors it. If the server number changes the client
  shows the server's 413 sentence, so drift is visible, not silent.
- **Long idle streams.** The API pings every 15 s; the client's 90 s
  timeout resets on every frame, so a slow but live turn is not cut.
- **Cost.** Every visitor question is a model call; the API's limits are
  the guard. The panel never sends without a click.
