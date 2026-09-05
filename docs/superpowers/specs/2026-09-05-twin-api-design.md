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
.dockerignore               at the repo root, because the build context is the repo root
apps/twin/
  Dockerfile
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
      api.py                twin-api (uvicorn entry point)
    api/
      __init__.py
      app.py                create_app(runtime); import-clean, no environment
      asgi.py               app = create_app(load_runtime()); the only eager module
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
`twin-smoke` replace them. `tests/test_agent.py` is deleted and replaced by
`tests/test_agent_stream.py`. Outside `apps/twin/`, the only additions are
the repo-root `.dockerignore` and new lines in `.env.example`.

## 6. Agent events

`twin/events.py` defines frozen dataclasses, one per event, sharing a
`kind` string literal:

| Event | Fields | Meaning |
|---|---|---|
| `Step` | `phase: "thinking" \| "composing"`, `round: int` | `thinking` before each model call; `composing` once per turn when its first text delta arrives, in whichever round that is, carrying that round's number. |
| `ToolCall` | `name`, `label` | The model asked for a tool. `label` is the visitor-facing text. |
| `ToolResult` | `name`, `ok: bool` | The tool ran. Results are paired to calls by list order; the agent decodes the tool message's JSON content and sets `ok` false when it is "notification failed" or starts with "Tool error" or "Unknown". |
| `Delta` | `text` | A piece of the answer. |
| `Project` | `slug`, `title`, `summary`, `url` | `show_project` produced a card. |
| `Done` | `reply`, `tools: tuple[str, ...]`, `rounds: int`, `usage: Usage \| None` | The turn is complete. `reply` is the full text, never empty. `rounds` is the number of model calls the turn made, including any post-cap call. `Usage` is a frozen `(prompt_tokens, completion_tokens, cached_tokens)` summed over the turn's calls, or `None` when no usage chunk arrived. |
| `Error` | `code`, `message` | Something failed mid-turn; always followed by `Done`. |

Ordering guarantees: exactly one `Done`, always last. `Step(thinking)`
precedes every model call; the post-cap call carries
`round = MAX_TOOL_ROUNDS + 1`. `Delta` events may appear in any round, and
`Done.reply` is exactly the concatenation of every `Delta` text in order,
or `FALLBACK_REPLY` when there was none. `Step(composing)` is yielded once
per turn, before its first `Delta`. `Error` appears at most once.
`Project` is yielded only for a `show_project` call whose slug the catalog
knows, at most once per slug per turn. The labels for tools:

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
   - Consume chunks. Text deltas: on the first of the turn yield
     `Step(composing)`; yield `Delta` per chunk and append to the turn's
     buffer. Tool-call fragments: accumulate `id`, `name`, and `arguments`
     per `index`. A chunk with an empty `choices` list carries no text or
     tool data and is inspected only for `usage`. Stop after the chunk
     whose choice has a `finish_reason` and, if a usage chunk follows, add
     its counts to the turn's total. A stream that ends with no choices at
     all is the empty-reply case handled in step 4.
   - If tool calls were accumulated: merge the fragments into call objects
     with the attribute shape `dispatch` reads (`id`, `function.name`,
     `function.arguments`); yield `ToolCall` for each; run them through
     `dispatch` (unchanged); yield `ToolResult` for each; and for a
     `show_project` call whose `slug` argument the catalog knows, yield
     `Project`. Append the assistant message as a plain dict (`role`,
     `content` set to the round's text or `None`, `tool_calls` in the
     API's own shape) and the tool messages, and continue. Text that
     arrived in a tool round has already been streamed and stays part of
     the reply; nothing is retracted.
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
stays as it is (round and tool names); the API writes the per-request line
(section 13).

Before every model call, `run` calls `budget.take()` when a `DailyBudget`
was given, purely for accounting: the agent never refuses a call, so a turn
that starts with budget left always finishes its rounds. Refusal happens
only at the request boundary (section 11).

`TwinAgent` gains optional constructor arguments, all defaulting to `None`
so the REPL and evals can omit them: `safety_identifier: str | None`,
`prompt_cache_key: str | None`, `budget: DailyBudget | None`, and
`catalog: ProjectCatalog | None` (needed to emit `Project`). An agent is
built per request (section 9), so no tool or agent state crosses requests.

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

`tools.py` gains `SHOW_PROJECT`, a static schema added to `TOOL_SCHEMAS`
(four tools) whose single `slug` property is a plain string described as
"one of the project slugs named in the knowledge sections", listed in
`required`, with `additionalProperties` false like the other three.
`TwinTools(notifier, catalog=None)` gains a `show_project(slug)` handler:
with a catalog it returns `"Shown: <title>"` for a known slug and
`"Unknown project: <slug>. Known: <comma-separated slugs>"` otherwise;
without a catalog it returns `"No projects available"`. `RecordingTools`
is unchanged and therefore already advertises and records the tool, so
evals and `twin-smoke` exercise it. The schema-to-signature sync test keeps
passing because the schema is static and the handler signature is
`(slug: str)`. The `Project` event is the agent's job: `run` holds the
catalog and, after dispatching a `show_project` call, looks up the call's
own `slug` argument; a known slug yields `Project`, an unknown one yields
nothing, and a slug already shown this turn is not shown again.

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
    limiter: RateLimiter          # app lifetime, shared by every request
    budget: DailyBudget           # app lifetime, shared by every request
    prompt_cache_key: str

def load_runtime(env=None, *, client=None, clock=None) -> Runtime
def build_agent(runtime, *, tools=None, safety_identifier=None) -> TwinAgent
def choose_notifier(settings, clock) -> Notifier
```

`load_runtime` is the single startup path: settings from the environment,
knowledge loaded and validated, catalog built, prompt built once, notifier
chosen (Pushover when configured, logging otherwise) and wrapped with the
hourly cap, client constructed unless one is injected. It raises the
existing `TwinError` subclasses; callers print one line and exit 1, as the
REPL does today. `build_agent` is called once per request and produces a `TwinAgent` with
`TwinTools` over the runtime's notifier and catalog (or an injected
registry for evals, tests, and smoke), plus the runtime's budget, catalog,
and prompt cache key and the caller's safety identifier.

`pyproject.toml` switches to a hatchling build with the package installable
(`[tool.uv] package = false` removed), adds `fastapi`, `sse-starlette`,
`uvicorn[standard]`, and for tests `httpx` (the test client's dependency,
distinct from the `httpx2` package the OpenAI SDK uses), and declares
console scripts `twin-chat` (`twin.cli.chat:main`), `twin-smoke`
(`twin.cli.smoke:main`), and `twin-api` (`twin.cli.api:main`, which runs
uvicorn on `twin.api.asgi:app` with the port from settings). `twin.api.app`
stays import-clean: it defines `create_app(runtime)` and nothing that reads
the environment, so unit tests import it without a key, a knowledge tree,
or a client; `twin.api.asgi` is the one module that calls `load_runtime()`
at import, and only uvicorn imports it. `pythonpath =
["."]` and the `sys.path` inserts go away. The prompt version key is
`f"twin-prompt-{sha256(system_prompt)[:12]}"` computed in `load_runtime`.
Every environment variable, including the CORS origins, is read only
through `Settings.from_env`, so `create_app(runtime)` needs no environment
at all in tests.

## 10. The HTTP API

Routes, all under `/v1`:

| Route | Purpose |
|---|---|
| `GET /v1/health` | `{"status": "ok", "knowledge_files": n, "model": "...", "version": "..."}`, where `version` is the installed package version from `importlib.metadata`. |
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
- `messages`: 1 to 64 items; roles alternate starting and ending with
  `user`; each `content` is a non-empty string of at most 2,000 characters
  after stripping; total content at most 24,000 characters. Shape and size
  failures are 400s. After shape validation the handler counts user
  messages; more than `TWIN_MAX_USER_MESSAGES` is the 413 in section 10.2,
  checked before any limit or model call, so the cap is reachable and
  configurable.
- Request body at most 32 KB; a small middleware in `security.py` rejects
  larger bodies with the 413 before parsing.

The last message is the new question; everything before it is the history
passed unchanged to the agent.

### 10.2 Responses

| Situation | Response |
|---|---|
| Valid | `200 text/event-stream` |
| Malformed JSON or failed validation | `400 {"code": "invalid_request", "message": "...", "detail": [...]}` |
| More than `TWIN_MAX_USER_MESSAGES` user messages (default 8) | `413 {"code": "conversation_too_long", "message": "..."}` |
| Body over 32 KB | `413 {"code": "body_too_large", "message": "..."}` |
| Visitor over the hourly limit | `429 {"code": "rate_limited", "message": "...", "retry_after": n}` with a `Retry-After` header |
| Daily ceiling reached | `503 {"code": "resting", "message": "The twin has used its budget for today and will be back tomorrow."}` |
| Startup problem surfaced at request time (should not happen) | `500 {"code": "internal", "message": "..."}` |

Error bodies never contain stack traces, file paths, or model error text.
FastAPI's default for a failed request model is a 422 with a bare
`detail` list, so the app registers a `RequestValidationError` handler
that returns the 400 shape above, and a plain-JSON handler for unexpected
exceptions that returns the 500 shape and logs the traceback server-side.

### 10.3 The stream

`sse.py` maps each agent event to one SSE frame and projects it onto a
visitor-safe subset, so internal tool names and token usage never reach
the browser:

| Agent event | `event:` | `data:` fields |
|---|---|---|
| `Step` | `step` | `phase`, `round` |
| `ToolCall` | `tool` | `label` only |
| `ToolResult` | `tool_result` | `ok` only |
| `Delta` | `delta` | `text` |
| `Project` | `project` | `slug`, `title`, `summary`, `url` |
| `Done` | `done` | `reply`, `rounds` |
| `Error` | `agent_error` | `code`, `message` |

The wire name `agent_error` avoids colliding with the browser
`EventSource` object's own `error` event. Frames are produced by
`sse-starlette`'s `EventSourceResponse` from an async generator that runs
the synchronous `agent.run` in a worker thread and forwards its events, with
a heartbeat comment every 15 seconds. When the client disconnects, the
generator stops forwarding; the in-flight model call is allowed to finish
in the background so a tool call that already started still completes and
notifies. Response headers include `Cache-Control: no-store` and
`X-Request-Id`.

### 10.4 CORS and headers

`security.py` takes the allowed origins from `Settings` (populated from
`TWIN_ALLOWED_ORIGINS`, comma-separated) and installs FastAPI's CORS
middleware for exactly those origins, methods `GET` and
`POST`, no credentials. Every response carries `X-Request-Id` (a UUID
generated per request) so a visitor can quote it. The client key is the
first address in `X-Forwarded-For` when `TWIN_TRUST_PROXY` is true,
otherwise the peer address; it is hashed with `TWIN_LOG_SALT` before it is
logged or sent to OpenAI as `safety_identifier`.

## 11. Limits

`twin/limits.py`, all pure and driven by an injected `Clock` protocol with
`now() -> float`:

- `RateLimiter(rate_per_hour=20, burst=5)`: a token bucket per client key
  with capacity `rate_per_hour + burst` (25) and a refill of
  `rate_per_hour` tokens per hour, so a visitor can send 25 messages back
  to back and the 26th is refused until a token refills.
  `allow(key) -> Decision(allowed: bool, retry_after: int)`. Buckets for
  keys idle over two hours are dropped on access to bound memory.
- `DailyBudget(limit=500)`: counts model calls per UTC day.
  `remaining() -> int` and `take() -> None`, which increments the day's
  count and resets it when the date changes. The request handler refuses
  with the 503 when `remaining()` is zero; the agent calls `take()` before
  every model call for accounting only, so a turn with two rounds costs
  two and a turn that starts with budget left finishes its rounds even if
  it crosses the line.
- `RateLimitedNotifier(inner, per_hour=10)`: implements `Notifier`; forwards
  the first ten pushes in any rolling hour and logs the rest at warning
  with the text, so nothing is silently lost.

Where each is enforced: the request handler checks the per-conversation
count (validation), then `RateLimiter.allow`, then
`DailyBudget.remaining()` is at least one; the agent records each call
with `take()`. The limiter and budget live on the `Runtime`, so they last
for the life of the process and are shared by every request.
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
| `TWIN_PER_CLIENT_BURST` | `5` | Extra capacity above the hourly rate; the bucket holds rate plus burst. |
| `TWIN_MAX_USER_MESSAGES` | `8` | Per conversation. |
| `TWIN_DAILY_CALL_LIMIT` | `500` | Model calls per UTC day. |
| `TWIN_PUSHOVER_HOURLY` | `10` | Pushes per rolling hour. |
| `TWIN_MODEL_TIMEOUT_SECONDS` | `60` | Per model call. |
| `PORT` | `8080` | Listening port for `twin-api` and the container. |

"Required in production" means: when `TWIN_TRUST_PROXY` is true and
`TWIN_LOG_SALT` is unset, startup fails with a one-line error, since a
trusted proxy implies a real deployment. `.env.example` gains every new
variable with its default, so a fresh checkout documents them.

## 13. Logging and health

One JSON line per chat request, emitted when the stream ends:
`request_id`, `conversation_id`, `client` (hash), `messages`, `rounds`,
`tools`, `first_delta_ms`, `total_ms`, `outcome` (`ok`, `error`,
`disconnected`), `usage` taken from `Done.usage` (prompt, completion, and
cached tokens when the usage chunk arrived). The API measures the two
timings itself around the stream. Never the message text. Limit rejections log one line with
the code and the hashed key. `/v1/health` is unauthenticated and cheap; it
does not call the model.

## 14. Docker image

`python:3.13-slim` base; install `uv`; `uv sync --frozen --no-dev`; copy
`apps/twin/` and the repo's `knowledge/` directory (the image bundles the
reviewed knowledge). The build context is the repo root, so the
`.dockerignore` lives there and excludes `knowledge/raw/`, `private/`,
`.env` and `.env.*` except the example, `.git`, every `.venv`, caches, and
`node_modules`; the Dockerfile additionally copies only `knowledge/*.md`,
`knowledge/roles`, `knowledge/topics`, and `knowledge/projects`, never
`knowledge/raw`, so the private sources are kept out twice over. The local
check lists the image's knowledge directory to prove `raw/` is absent.
Non-root user;
`EXPOSE 8080`; `CMD ["twin-api"]`. `KNOWLEDGE_DIR` is set explicitly in the
image so `REPO_ROOT` walk-up is not relied on, and the walk-up itself is
made safe: when the package sits shallower than expected (an installed
wheel, a container), `config.py` falls back to the current working
directory instead of failing at import. The build context is the
repo root so `knowledge/` is reachable. Local check: build, run with the
repo `.env` passed as `--env-file`, hit `/v1/health` and one `/v1/chat`
with `curl -N`.

## 15. Testing

Unit, no network, written first:

- `test_events.py`: dataclasses frozen; `kind` literals.
- `test_agent_stream.py`: a fake streaming client yielding scripted chunks.
  Cases: text-only turn (`thinking`, `composing`, deltas, `done`); a tool
  round then text (`ToolCall`, `ToolResult`, then text, with any text
  streamed in the tool round kept and present in `Done.reply`);
  `show_project` emitting `Project`; the round cap and final
  `tool_choice="none"`; empty content and empty choices giving
  `FALLBACK_REPLY`; an exception before the first chunk and one
  mid-stream, both yielding `Error` then `Done` and never raising;
  `reply()` returns `Done.reply`; the safety and cache keys are passed
  through; `budget.take()` called once per model call; `history` not
  mutated; and a real `TwinTools` reached through the streaming path (a
  tool call assembled from fragments arrives at the handler with parsed
  arguments and a `ToolResult(ok=True)` follows).
- `test_projects.py`: catalog from a temp knowledge tree; summary
  extraction with and without the heading; the 280-character cut; unknown
  slug; url shape.
- `test_tools.py` (extended): `show_project` known, unknown, and without a
  catalog; the static schema exposes only `slug`; the existing
  three-tool name assertion is updated to four; the schema-signature sync
  test still passes.
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
  event sequence for a text turn, a tool turn, and an error turn; that no
  frame carries a tool name, a `tools` list, or usage; and that the two
  notification tools produce identical `tool` frames. Heartbeat presence
  is not asserted (timing).
- `test_api_live.py` (integration, skipped without the key): start the app
  with the real client, stream one real turn, assert a `done` event with
  non-empty reply and at least one `delta`.

The existing evals keep passing unchanged. The existing unit tests keep
passing apart from the deliberate updates: the tool-name list grows to
four; the scripts' tests, if any, follow them into `twin/cli`; and
`tests/test_agent.py` is deleted and replaced by `test_agent_stream.py`,
which restates every scenario it covered against the streaming fake (its
object-identity assertions on appended messages do not carry over, since
the loop now appends plain dicts). The two warnings the old loop logged, a
`length` finish reason and a stream with no choices, carry over into `run`
and keep their tests. Coverage gate unchanged at 80 percent with branch
coverage; `twin/cli/*` and `twin/api/asgi.py` are omitted from measurement
because they only wire and run, so the measured package should stay near
100.

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
5. With `TWIN_DAILY_CALL_LIMIT=2`, once two model calls have been
   recorded the next request is refused with the `resting` 503 before any
   model call is made.
6. `docker build` succeeds and the container answers `/v1/health` and one
   chat turn locally.
7. `twin-chat` and `twin-smoke` behave as the old scripts did, with two
   deliberate differences: a model failure is reported inside the turn as
   an error event and a fallback reply rather than raised, and the REPL's
   notifier is rate-limited like the API's.

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
