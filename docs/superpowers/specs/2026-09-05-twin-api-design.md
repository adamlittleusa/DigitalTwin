# Digital Twin: API Service

**Date:** 2026-09-05
**Status:** Approved by Adam, pending spec review
**Owner:** Adam Little
**Builds on:** `2026-09-04-twin-knowledge-base-design.md` (merged as PR #1)

## 1. Goal

Put the twin behind an HTTP API the portfolio site can call, so that a
visitor sees the answer being written and sees the agent working: each
model call, each tool it uses, and each result, as a visible chain of
steps. After this work:

- `POST /v1/chat` streams a reply over Server-Sent Events with named
  events for loop steps, tool use, text, project cards, and completion.
- The API is stateless, publicly reachable, and protected by tight
  in-memory limits on visitors, on the daily model spend, and on
  notifications to Adam's phone.
- The `twin` package is installable, assembled in one place, and runs the
  same way from the REPL, the smoke command, the API, and a Docker image.

## 2. Context

Sub-project one delivered the `twin` package (`config`, `errors`,
`knowledge`, `prompt`, `tools`, `agent`, `evals`, `examples`), 17 reviewed
knowledge files, 47 live eval cases, and two dev scripts. Its final review
named three things that make an API harder than necessary, all fixed here:

- Assembly lives in `scripts/chat.py` and is duplicated in `scripts/smoke.py`;
  nothing in the package builds an agent.
- The package is not installable (`[tool.uv] package = false`), so scripts
  insert their own path and `uvicorn twin.api...` would need the same hack.
- `TwinAgent.reply` returns a finished string; nothing can observe the loop
  while it runs.

The agent calls the OpenAI Chat Completions API. Its streaming mode
delivers answer text as deltas and tool calls as fragments keyed by index,
with `finish_reason` on the last chunk of a choice and, when requested,
a final usage chunk. The SDK also accepts `safety_identifier` (a hashed
per-visitor id for abuse detection on OpenAI's side) and `prompt_cache_key`
(a stable key that improves prefix caching of the large system prompt).

## 3. Decisions already made

| Decision | Choice |
|---|---|
| Streaming | Server-Sent Events. Real token streaming from the model's streaming mode. |
| Visible chain of thought | The agent loop's own steps only: model calls, tool calls, tool results, composing. No model reasoning summaries; that would need the Responses API and would risk showing boundary logic. |
| Conversation state | Stateless. The browser holds the transcript and sends it every turn. |
| Abuse controls | Tight: 20 messages per visitor per hour, 8 user messages per conversation, 500 model calls per UTC day, 10 pushes per hour. |
| Hosting target | Fly.io, one small always-on machine. So in-memory limits are sufficient. Deployment itself is a later spec. |
| Portfolio guide | One `show_project` tool that emits a project card event. Navigation and richer actions wait for the site spec. |
| Streaming architecture | Event-emitting agent: `TwinAgent.run` yields typed events; `reply` wraps it. |
| Model and provider | Unchanged: OpenAI Chat Completions, `gpt-5.4-mini` from config. |
| Visitor-facing tool labels | `record_unknown_question` and `record_sensitive_question` share one label, so a deflection is indistinguishable from a gap. |

## 4. Scope

**In scope**

1. Make the package installable and move assembly into it; turn the two
   scripts into console commands.
2. Typed agent events and a streaming `TwinAgent.run`; `reply` preserved.
3. The `show_project` tool and the project catalog behind it.
4. Limits: per-visitor rate, per-conversation length, daily model ceiling,
   notification cap.
5. The FastAPI app: chat, examples, projects, health; SSE; CORS; errors;
   logging.
6. A Dockerfile and a local container check.
7. Tests for all of it, and one live integration test through the API.

**Out of scope, each its own spec or a later decision**

- Deploying to Fly.io, `fly.toml`, DNS for `api.adambuilds.ai`.
- The site and its chat UI.
- Server-side sessions, authentication, model reasoning summaries, a
  Responses API migration.
- The history scan-and-squash before first push, which the deployment
  spec inherited; note that the knowledge files were already pushed under
  PR #1 by Adam's decision.

## 5. Repository layout

Changes and additions under `apps/twin/`:

```
apps/twin/
  Dockerfile
  .dockerignore
  pyproject.toml            hatchling build; installable; console scripts
  twin/
    agent.py                run() generator + reply() wrapper
    events.py               frozen event dataclasses
    projects.py             ProjectCatalog and ProjectCard
    tools.py                + show_project handler and schema
    prompt.py               + one rule about show_project
    limits.py               RateLimiter, DailyBudget, RateLimitedNotifier, Clock
    wiring.py               Runtime, load_runtime, build_agent, choose_notifier
    cli/
      __init__.py
      chat.py               twin-chat (moved from scripts/chat.py)
      smoke.py              twin-smoke (moved from scripts/smoke.py)
    api/
      __init__.py
      app.py                create_app(runtime) and the module-level app
      routes.py             the four routes
      schemas.py            ChatRequest, ChatMessage, error bodies
      sse.py                event to SSE frame
      security.py           client key, CORS origins
  scripts/
    extract_docx.py         unchanged
  tests/
    test_events.py, test_agent_stream.py, test_projects.py,
    test_limits.py, test_wiring.py, test_api_routes.py,
    test_api_sse.py, test_api_live.py (integration)
```

`scripts/chat.py` and `scripts/smoke.py` are deleted; `twin-chat` and
`twin-smoke` replace them. Nothing else in the repo moves.

## 6. Agent events

`twin/events.py` defines frozen dataclasses, one per event, sharing a
`kind` string literal:

| Event | Fields | Meaning |
|---|---|---|
| `Step` | `phase: "thinking" \| "composing"`, `round: int` | `thinking` before each model call; `composing` when the first text delta of the final answer arrives. |
| `ToolCall` | `name`, `label` | The model asked for a tool. `label` is the visitor-facing text. |
| `ToolResult` | `name`, `ok: bool` | The tool ran; `ok` is false when the handler reported an error or "notification failed". |
| `Delta` | `text` | A piece of the answer. |
| `Project` | `slug`, `title`, `summary`, `url` | `show_project` produced a card. |
| `Done` | `reply`, `tools: tuple[str, ...]`, `rounds: int` | The turn is complete. `reply` is the full text, never empty. |
| `Error` | `code`, `message` | Something failed mid-turn; always followed by `Done`. |

Ordering guarantees: exactly one `Done`, always last. `Step(thinking)`
precedes every model call. `Delta` events appear only after the last tool
round. `Error` appears at most once. The labels for tools:

| Tool | Label |
|---|---|
| `record_user_details` | Saving your email for Adam |
| `record_unknown_question` | Passing this along to Adam |
| `record_sensitive_question` | Passing this along to Adam |
| `show_project` | Pulling up a project |

## 7. The streaming loop

`TwinAgent.run(history, message) -> Iterator[AgentEvent]`:

1. Build `[system, *history, user]` exactly as today.
2. For each round up to `MAX_TOOL_ROUNDS`:
   - Yield `Step(thinking, round)`.
   - Call `chat.completions.create(..., stream=True, tools=..., tool_choice="auto", stream_options={"include_usage": True}, safety_identifier=<hashed key>, prompt_cache_key=<prompt version key>, timeout=<settings>)`.
   - Consume chunks. Text deltas: on the first one yield `Step(composing)`,
     then yield `Delta` per chunk and append to a buffer. Tool-call
     fragments: accumulate `id`, `name`, and `arguments` per `index`. Stop
     on the chunk whose choice has a `finish_reason`, then read the usage
     chunk if present.
   - If tool calls were accumulated: for each, yield `ToolCall`, run it
     through `dispatch` (unchanged), yield `ToolResult`, and for
     `show_project` also yield `Project` from the catalog. Append the
     assistant message (reconstructed with the accumulated tool calls) and
     the tool messages, and continue to the next round. Text that arrived
     in the same round as tool calls is discarded, matching today's
     behaviour where a tool-call turn's content is not shown.
   - If no tool calls: the buffer is the reply; yield `Done` and stop.
3. If the cap is reached, yield `Step(thinking)`, make one streamed call
   with `tool_choice="none"`, stream its text, yield `Done`.
4. `Done.reply` is the buffer, or `FALLBACK_REPLY` when the buffer is empty
   (no text, empty choices, or a final-turn tool call that was ignored).
5. Any exception from the model client, mid-stream or before the first
   chunk, is caught inside `run`: log it, yield `Error(code="model_error",
   message=<short, no internals>)`, then `Done` with whatever text was
   buffered or `FALLBACK_REPLY`. `run` never raises to its caller.

`reply(history, message) -> str` iterates `run` and returns `Done.reply`.
`RecordingTools` and the evals are unaffected. Logging inside the agent
stays as it is (round and tool names), plus one line per turn with rounds,
tool names, time to first delta, and total time; no message text.

The hashed key and the cache key are optional constructor arguments to
`TwinAgent` (`safety_identifier: str | None`, `prompt_cache_key: str |
None`) so the REPL and evals can omit them.

## 8. `show_project` and the project catalog

`twin/projects.py`:

- `ProjectCard(slug, title, summary, url)`, frozen.
- `ProjectCatalog.from_knowledge(knowledge, site_url) -> ProjectCatalog`:
  one card per file of kind `project`. `slug` is the file's stem
  (`digital-twin`). `title` is the frontmatter title. `summary` is the
  first paragraph under a `## What it is` heading, or the first paragraph
  of the body when that heading is absent, cut to 280 characters at a word
  boundary. `url` is `f"{site_url}/projects/{slug}"`.
- `catalog.get(slug) -> ProjectCard | None`, `catalog.cards -> tuple`.

`tools.py` gains `SHOW_PROJECT`, a schema whose `slug` property carries an
`enum` of the catalog's slugs, built at wiring time by
`TwinTools(notifier, catalog=catalog)`. The handler returns
`"Shown: <title>"` for a known slug and `"Unknown project: <slug>. Known:
<comma-separated slugs>"` otherwise. `TwinTools` records the last shown
card so `run` can emit the `Project` event; `RecordingTools` accepts the
call and records it like any other. Because the schema is built from the
catalog, the sync test that compares schemas to handler signatures keeps
passing.

`prompt.py` gains one rule: "When one of the projects in the sections
above is what the visitor is asking about, or the natural next thing to
show them, call the show_project tool with its slug so they see a card.
Do it at most once per reply."

## 9. Wiring and runtime

`twin/wiring.py`:

```python
@dataclass(frozen=True)
class Runtime:
    settings: Settings
    knowledge: Knowledge
    catalog: ProjectCatalog
    system_prompt: str
    notifier: Notifier            # already wrapped by RateLimitedNotifier
    client: Any                   # OpenAI client
    clock: Clock

def load_runtime(env=None, *, client=None, clock=None) -> Runtime
def build_agent(runtime, *, tools=None, safety_identifier=None) -> TwinAgent
def choose_notifier(settings, clock) -> Notifier
```

`load_runtime` is the single startup path: settings from the environment,
knowledge loaded and validated, catalog built, prompt built once, notifier
chosen (Pushover when configured, logging otherwise) and wrapped with the
hourly cap, client constructed unless one is injected. It raises the
existing `TwinError` subclasses; callers print one line and exit 1, as the
REPL does today. `build_agent` produces a `TwinAgent` with `TwinTools` over
the runtime's notifier and catalog, or with an injected registry (evals,
tests, smoke).

`pyproject.toml` switches to a hatchling build with the package installable
(`[tool.uv] package = false` removed), adds `fastapi`, `sse-starlette`,
`uvicorn[standard]`, and for tests `httpx` (the test client's dependency,
distinct from the `httpx2` package the OpenAI SDK uses), and declares
console scripts `twin-chat`, `twin-smoke`, and `twin-api` (runs uvicorn on
`twin.api.app:app`). `pythonpath = ["."]` and the `sys.path` inserts go
away. The prompt version key is `f"twin-prompt-{sha256(system_prompt)[:12]}"`
computed in `load_runtime`.

## 10. The HTTP API

Routes, all under `/v1`:

| Route | Purpose |
|---|---|
| `GET /v1/health` | `{"status": "ok", "knowledge_files": n, "model": "...", "version": "..."}`. |
| `GET /v1/examples` | `{"questions": [...]}` from `twin.examples`. |
| `GET /v1/projects` | `{"projects": [ProjectCard...]}`. |
| `POST /v1/chat` | The streamed turn. |

### 10.1 Request

```json
{
  "conversation_id": "c3f1…",
  "messages": [
    {"role": "user", "content": "Tell me about your background."},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "And before that?"}
  ]
}
```

Validation, in `schemas.py` with pydantic, all before any model call:

- `conversation_id`: optional string, 8 to 64 characters of `[A-Za-z0-9_-]`;
  used only for logging correlation.
- `messages`: 1 to 16 items; roles alternate starting and ending with
  `user`; each `content` is a non-empty string of at most 2,000 characters
  after stripping; total content at most 24,000 characters.
- Request body at most 32 KB (middleware rejects larger with 413 before
  parsing).

The last message is the new question; everything before it is the history
passed unchanged to the agent.

### 10.2 Responses

| Situation | Response |
|---|---|
| Valid | `200 text/event-stream` |
| Malformed JSON or failed validation | `400 {"code": "invalid_request", "message": "...", "detail": [...]}` |
| More than 8 user messages | `413 {"code": "conversation_too_long", "message": "..."}` |
| Body over 32 KB | `413 {"code": "body_too_large", "message": "..."}` |
| Visitor over the hourly limit | `429 {"code": "rate_limited", "message": "...", "retry_after": n}` with a `Retry-After` header |
| Daily ceiling reached | `503 {"code": "resting", "message": "The twin has used its budget for today and will be back tomorrow."}` |
| Startup problem surfaced at request time (should not happen) | `500 {"code": "internal", "message": "..."}` |

Error bodies never contain stack traces, file paths, or model error text.

### 10.3 The stream

`sse.py` maps each agent event to one SSE frame: `event:` is the kind
(`step`, `tool`, `tool_result`, `delta`, `project`, `done`, `error`) and
`data:` is the event's fields as JSON. Frames are produced by
`sse-starlette`'s `EventSourceResponse` from an async generator that runs
the synchronous `agent.run` in a worker thread and forwards its events, with
a heartbeat comment every 15 seconds. When the client disconnects, the
generator stops forwarding; the in-flight model call is allowed to finish
in the background so a tool call that already started still completes and
notifies. Response headers include `Cache-Control: no-store` and
`X-Request-Id`.

### 10.4 CORS and headers

`security.py` reads `TWIN_ALLOWED_ORIGINS` (comma-separated) and installs
FastAPI's CORS middleware for exactly those origins, methods `GET` and
`POST`, no credentials. Every response carries `X-Request-Id` (a UUID
generated per request) so a visitor can quote it. The client key is the
first address in `X-Forwarded-For` when `TWIN_TRUST_PROXY` is true,
otherwise the peer address; it is hashed with `TWIN_LOG_SALT` before it is
logged or sent to OpenAI as `safety_identifier`.

## 11. Limits

`twin/limits.py`, all pure and driven by an injected `Clock` protocol with
`now() -> float`:

- `RateLimiter(rate_per_hour=20, burst=5)`: a token bucket per client key.
  `allow(key) -> Decision(allowed: bool, retry_after: int)`. Buckets for
  keys idle over two hours are dropped on access to bound memory.
- `DailyBudget(limit=500)`: counts model calls per UTC day; `take() -> bool`
  returns false once the limit is reached and resets when the date changes.
  Counted at each model call inside the loop, so a turn with two rounds
  costs two; a turn that starts with budget left is allowed to finish its
  rounds even if it crosses the line.
- `RateLimitedNotifier(inner, per_hour=10)`: implements `Notifier`; forwards
  the first ten pushes in any rolling hour and logs the rest at warning
  with the text, so nothing is silently lost.

Where each is enforced: the request handler checks the per-conversation
count (validation), then `RateLimiter.allow`, then `DailyBudget` has
capacity for at least one call; the agent takes from the budget per call.
All limits are configurable through the environment (section 12). With one
Fly machine these in-memory limits are exact; a second instance would
double them, which the deployment spec must not do without adding a store.

## 12. Configuration

New variables, all with defaults, read by `Settings.from_env`:

| Variable | Default | Meaning |
|---|---|---|
| `TWIN_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS origins. Production sets the site's origins. |
| `TWIN_SITE_URL` | `https://adambuilds.ai` | Base for project card links. |
| `TWIN_TRUST_PROXY` | `false` | Take the client address from `X-Forwarded-For`. True on Fly. |
| `TWIN_LOG_SALT` | required in production, random per process otherwise | Salt for hashing client keys. |
| `TWIN_PER_CLIENT_HOURLY` | `20` | Messages per visitor per hour. |
| `TWIN_PER_CLIENT_BURST` | `5` | Bucket size. |
| `TWIN_MAX_USER_MESSAGES` | `8` | Per conversation. |
| `TWIN_DAILY_CALL_LIMIT` | `500` | Model calls per UTC day. |
| `TWIN_PUSHOVER_HOURLY` | `10` | Pushes per rolling hour. |
| `TWIN_MODEL_TIMEOUT_SECONDS` | `60` | Per model call. |
| `PORT` | `8080` | Listening port for `twin-api` and the container. |

"Required in production" means: when `TWIN_TRUST_PROXY` is true and
`TWIN_LOG_SALT` is unset, startup fails with a one-line error, since a
trusted proxy implies a real deployment.

## 13. Logging and health

One JSON line per chat request, emitted when the stream ends:
`request_id`, `conversation_id`, `client` (hash), `messages`, `rounds`,
`tools`, `first_delta_ms`, `total_ms`, `outcome` (`ok`, `error`,
`disconnected`), `usage` (prompt, completion, cached tokens when the usage
chunk arrived). Never the message text. Limit rejections log one line with
the code and the hashed key. `/v1/health` is unauthenticated and cheap; it
does not call the model.

## 14. Docker image

`python:3.13-slim` base; install `uv`; `uv sync --frozen --no-dev`; copy
`twin/` and the repo's `knowledge/` directory (the image bundles the
reviewed knowledge; `raw/` is excluded by `.dockerignore`); non-root user;
`EXPOSE 8080`; `CMD ["twin-api"]`. `KNOWLEDGE_DIR` is set explicitly in the
image so `REPO_ROOT` walk-up is not relied on. The build context is the
repo root so `knowledge/` is reachable. Local check: build, run with the
repo `.env` passed as `--env-file`, hit `/v1/health` and one `/v1/chat`
with `curl -N`.

## 15. Testing

Unit, no network, written first:

- `test_events.py`: dataclasses frozen; `kind` literals.
- `test_agent_stream.py`: a fake streaming client yielding scripted chunks.
  Cases: text-only turn (`thinking`, `composing`, deltas, `done`); a tool
  round then text (`ToolCall`, `ToolResult`, then text; discarded interim
  text); `show_project` emitting `Project`; the round cap and final
  `tool_choice="none"`; empty content and empty choices giving
  `FALLBACK_REPLY`; an exception before the first chunk and one
  mid-stream, both yielding `Error` then `Done` and never raising;
  `reply()` returns `Done.reply`; the safety and cache keys are passed
  through; `history` not mutated.
- `test_projects.py`: catalog from a temp knowledge tree; summary
  extraction with and without the heading; the 280-character cut; unknown
  slug; url shape.
- `test_tools.py` (extended): `show_project` known and unknown; the schema
  enum matches the catalog; the schema-signature sync test still passes.
- `test_limits.py`: token bucket allow/deny/refill with a fake clock;
  idle-bucket eviction; daily budget rollover at UTC midnight; notifier
  cap forwarding ten then logging.
- `test_wiring.py`: `load_runtime` with an injected client and a temp
  knowledge tree; error on missing key; the prompt cache key is stable.
- `test_api_routes.py`: with `create_app(runtime)` and a fake client:
  health, examples, projects; every 4xx and the 503; CORS headers for an
  allowed and a disallowed origin; `X-Request-Id` present; body size
  limit.
- `test_api_sse.py`: parse the stream from the test client and assert the
  event sequence for a text turn, a tool turn, and an error turn; heartbeat
  presence is not asserted (timing).
- `test_api_live.py` (integration, skipped without the key): start the app
  with the real client, stream one real turn, assert a `done` event with
  non-empty reply and at least one `delta`.

The existing evals and unit tests keep passing. Coverage gate unchanged at
80 percent with branch coverage; the package should stay near 100.

## 16. Success criteria

1. `uv run pytest` passes with coverage at or above the gate; the 47 evals
   pass with `-m integration`.
2. `uv run twin-api` starts, `/v1/health` answers, and a `curl -N` chat
   shows `step`, `delta`, and `done` events for a plain question, and a
   `tool` event for "What's your shoe size?".
3. The Corelight question over the API shows the same "Passing this along
   to Adam" label as an unknown question, and the reply text matches the
   boundary.
4. Sending 26 messages from one client inside an hour yields a 429 with
   `Retry-After` on the 26th (20 per hour plus a burst of 5).
5. With `TWIN_DAILY_CALL_LIMIT=2`, the third model call of the day yields
   the `resting` 503 on the next request.
6. `docker build` succeeds and the container answers `/v1/health` and one
   chat turn locally.
7. `twin-chat` and `twin-smoke` behave exactly as the old scripts did.

## 17. Risks

- **Cost from abuse.** The daily ceiling bounds the worst day to about 500
  calls. Per-visitor limits are by IP, which shared networks and VPNs blur
  in both directions; acceptable for a portfolio.
- **Phone spam.** Ten pushes an hour, the rest logged; a determined
  visitor can still fill an hour. The label choice keeps them from knowing
  which questions page Adam.
- **Streaming and proxies.** Buffering proxies can hold SSE; the heartbeat
  and `Cache-Control: no-store` are the mitigations. Fly's proxy passes SSE
  through.
- **In-memory limits and restarts.** A restart resets all counters. Fine
  for one machine; the deployment spec must keep it to one.
- **Prompt growth.** The prompt is about 10,000 tokens now; the loader
  warns at 60,000. `prompt_cache_key` keeps repeated turns cheap.
- **Client disconnects mid-tool.** Allowing the in-flight call to finish
  means a notification can fire after the visitor left; that is the
  desired behaviour for a lead or a flagged question.

## 18. Follow-on specs

1. Deployment: Fly.io app, secrets, `fly.toml`, `api.adambuilds.ai` DNS,
   the history scan before any further push, and a single-instance rule.
2. Site and design system: Next.js, the chat UI that renders these events,
   the project pages the cards link to.
