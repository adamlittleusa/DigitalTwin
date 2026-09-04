# Digital Twin: Foundation and Knowledge Base

**Date:** 2026-09-04
**Status:** Approved 2026-09-04
**Owner:** Adam Little

## 1. Goal

Make the digital twin know Adam the way a close colleague does, and give the
project a foundation the rest of the portfolio can build on. After this work:

- The twin's knowledge comes from curated markdown files written from Adam's
  own narration and reviewed by him, not from a scraped LinkedIn page.
- The code lives in a public monorepo laid out to receive the FastAPI service
  and the Next.js site in later specs.
- A test suite and an eval set exist so every change to the knowledge or the
  prompt can be checked in minutes.

## 2. Context

The starting point is the Ed Donner course app in
`C:\Users\adaml\OneDrive\Desktop\PortfolioProjects\twin`: a Gradio
`ChatInterface`, an OpenAI chat-completions tool loop, two Pushover tools
(`record_user_details`, `record_unknown_question`), and a system prompt that
embeds `summary.txt` plus the raw text of `linkedin.pdf`.

Problems this spec fixes:

- The LinkedIn text is a browser print of the profile page. It contains ads,
  "people you may know" blocks, and every role description is truncated at
  "...more". The twin knows less than the resume.
- Nothing runs: no git repo, no virtual environment, no `.env`, `gradio` not
  installed.
- Tool failures and missing environment variables crash the chat with raw
  tracebacks.

## 3. Decisions already made

These were settled in the brainstorming session and are inputs, not open
questions:

| Decision | Choice |
|---|---|
| Overall architecture | Custom Next.js site on Vercel at adambuilds.ai, plus a Python API holding the twin. Later specs. |
| Repo visibility | One public monorepo. Knowledge files are committed and are public-safe by rule. The remote is Adam's existing `adamlittleusa/DigitalTwin` repo; nothing is pushed until Adam says the project is ready to deploy. |
| Repo location | `C:\Users\adaml\code\adambuilds`, outside OneDrive. |
| Knowledge representation | Curated markdown loaded whole into the system prompt. RAG rejected as overkill at this size. |
| Narration method | Adam's practiced interview monologue first, then a structured role-by-role interview in chat to fill gaps. |
| Model and provider | Unchanged: OpenAI chat completions, `gpt-5.4-mini`, read from config. |
| Local dev harness | No Gradio anywhere. A terminal chat REPL and a smoke script until the FastAPI service and the site exist. Decided 2026-09-04. |

## 4. Scope

**In scope**

1. Monorepo skeleton, Python project managed with `uv`, `.env.example`,
   `.gitignore`, README.
2. Knowledge base: file conventions, loader, the first set of files drafted
   from the resume and monologue, and the interview workflow.
3. Refactor of the twin into a small package with injectable dependencies,
   config validation, and error handling. A terminal REPL and a smoke
   script replace Gradio as the local dev harness.
4. Unit tests and an eval runner.
5. Local git history only. `origin` points at Adam's existing
   `adamlittleusa/DigitalTwin` repo, and the first push happens when Adam
   decides the project is ready to deploy. Knowledge files are pushed only
   after Adam has reviewed them.

**Out of scope, each gets its own spec**

- FastAPI service, streaming, rate limiting, the portfolio guide tool.
- Next.js site, design system, custom chat UI.
- Hosting and DNS.
- Voice transcription tooling.
- LLM-as-judge evals.

## 5. Repository layout

```
adambuilds/
  README.md
  .gitignore                 ignores .env, knowledge/raw/, private/, .venv/
  .env.example
  apps/
    twin/
      pyproject.toml         uv-managed; Python 3.13 pinned via .python-version
      scripts/
        chat.py              terminal chat REPL for local development
        smoke.py             fixed questions through the agent; prints replies and tool calls
        extract_docx.py      one-off: resume docx to raw text
      twin/
        __init__.py
        config.py            Settings from environment, validated at startup
        knowledge.py         loads and validates knowledge/*.md
        prompt.py            assembles the system prompt
        tools.py             tool schemas, handlers, dispatch
        agent.py             the completion loop
        examples.py          the four example questions
      tests/
        test_config.py
        test_knowledge.py
        test_prompt.py
        test_tools.py
        test_agent.py
        test_evals.py        integration, skipped without OPENAI_API_KEY
    web/
      .gitkeep               Next.js arrives in a later spec
  knowledge/                 the twin's memory of Adam (see section 6)
    README.md                conventions and the coverage table
    raw/                     gitignored: monologue transcript, resume text, interview notes
  evals/
    twin_qa.yaml
  private/                   gitignored: notes for Claude that never reach the twin
  docs/
    superpowers/specs/
```

Nothing from the course folder in OneDrive is copied into the repo. The
agent loop and tool schemas are rewritten inside the package, and the
Gradio UI and its CSS are left behind. The text of `linkedin.pdf` and
`summary.txt` is saved under gitignored `knowledge/raw/` as sources only:
the PDF is scraped page text that must not land in a public repository, and
the summary is superseded by `identity.md`. Adam can delete the OneDrive
folder once the new repo runs.

## 6. Knowledge base

### 6.1 File conventions

Every file under `knowledge/` except `README.md` and `raw/` is a markdown
document with YAML frontmatter, parsed with the `python-frontmatter` package.

```yaml
---
title: Recorded Future
kind: role            # identity | voice | boundaries | arc | role | topic | project | faq
period: 2018-07 to 2022-08   # required for role and project, absent otherwise
tags: [cti, product-architecture, data-science]
public: true          # required, must be exactly true
reviewed: 2026-09-10  # date Adam last reviewed the file; absent until he has
---
```

Rules enforced by the loader:

- `public: true` is required. The loader raises `KnowledgeError` naming every
  file that fails, and the app does not start. This is how "public-safe by
  rule" is enforced rather than remembered.
- `title` is required and non-empty; the prompt builder uses it as the
  heading for the file.
- `kind` must be one of the eight values above.
- `period` is required for `role` and `project`. It has the form
  `<start> to <end>` where each end is `YYYY` or `YYYY-MM`, and the end may
  be `present`. Sorting uses the start; a bare year sorts as its January.
- `reviewed`, when present, may arrive from the YAML parser as a date object
  or a string; the loader normalises it to an ISO date string.
- Body must be non-empty.
- The loader recurses into subdirectories under `knowledge/`, skipping
  `raw/` and `README.md`.

### 6.2 File inventory

| Path | Kind | Contents |
|---|---|---|
| `identity.md` | identity | One paragraph on who Adam is today, where he lives, what he is building, how to get in touch (the contact flow, not raw details). |
| `voice.md` | voice | How Adam talks: tone, phrases he uses, things he would never say, three sample answers in his voice. Drafted from the monologue. |
| `boundaries.md` | boundaries | What the twin declines to discuss and the deflection it uses. Draft defaults for Adam to edit: compensation, negative comments on employers or colleagues, operational military detail beyond the resume, client names not already public, personal contact details, politics and religion, and why the Corelight role ended (deflect neutrally and notify Adam through the `record_sensitive_question` tool). |
| `career-arc.md` | arc | The through-line of the career as the monologue tells it. |
| `roles/YYYY-slug.md` | role | One per role, the nine files listed below. Sections: Context, What I did, Outcomes, Stories, Skills used, Why I moved on. |
| `topics/slug.md` | topic | Adam's positions on AI security, CTI, product management, and whatever the interviews surface. |
| `projects/slug.md` | project | One per portfolio project, starting with `digital-twin.md`: what, why, stack, status, link. The future guide tool reads these. |
| `faq.md` | faq | Common visitor questions with approved answers. |

The nine role files, with the `period` each carries, taken from the 2026
resume:

| File | Title | Period |
|---|---|---|
| `roles/2026-corelight.md` | Principal Product Manager, AI-Driven Security Response, Corelight | `2026-03 to present` |
| `roles/2023-accenture.md` | Deputy Director of Strategy and Services, Accenture Cyber Intelligence | `2023-07 to 2026-03` |
| `roles/2023-revelstoke.md` | Solutions Architect and CTI, Revelstoke SOAR | `2023-02 to 2023-07` |
| `roles/2022-pondurance.md` | Cyber Threat Intelligence Program Manager, Pondurance | `2022-08 to 2023-02` |
| `roles/2018-recorded-future.md` | Intelligence Services Consultant to Product Architect, Recorded Future | `2018-07 to 2022-08` |
| `roles/2017-mit-lincoln-lab.md` | Information System Security Officer, MIT Lincoln Laboratory | `2017-10 to 2018-07` |
| `roles/2017-mission-essential.md` | Counterintelligence Analyst, Insider Threat Team, Mission Essential Personnel | `2017-03 to 2017-09` |
| `roles/2013-mang-training-manager.md` | Training Manager (AGR), Massachusetts Army National Guard | `2013-07 to 2017-03` |
| `roles/2001-army-intel-ops.md` | Intelligence operations roles, U.S. Army, Massachusetts Army National Guard, and contractors | `2001 to 2013` |

Sections inside a role file are headings, not frontmatter, so Adam can write
freely. A role file may leave a section empty while it is still being
interviewed; the coverage table in `knowledge/README.md` tracks that.

### 6.3 Loading order

The loader returns files in this order, and the prompt builder preserves it:
identity, voice, boundaries, arc, roles newest first by `period` start,
topics by filename, projects by filename, faq. Files of the same kind that are
not roles sort by filename.

### 6.4 Size budget and upgrade path

The loader logs an estimated token count (characters divided by four) and
emits a warning above 60,000. That warning is the trigger to move to the
"core profile plus lookup tool" design. Because every file is self-contained
with metadata, that upgrade is a new tool plus a change to the prompt builder,
not a rewrite of the knowledge.

## 7. Narration and interview workflow

1. **Monologue.** Adam delivers his practiced resume monologue in chat. It is
   saved verbatim to `knowledge/raw/2026-09-04-monologue.md`.
2. **Seed drafts, in two passes.** The resume source is
   `C:\Users\adaml\OneDrive\Desktop\resumes\workday resume 2026.docx`; its
   text is extracted once and saved to `knowledge/raw/resume-2026.md`.
   - *Pass one, from the resume and this spec, needs nothing from Adam:*
     the nine role files, `projects/digital-twin.md`, a first
     `identity.md`, and default `boundaries.md` and `faq.md`. This pass
     is enough to make the loader, the prompt, the dev scripts, and the
     fact evals runnable.
   - *Pass two, gated on the monologue:* `voice.md` and `career-arc.md`
     are written from it, and `identity.md`, `boundaries.md`, `faq.md`, and
     the role files are revised with what it adds.

   Anything not stated in a source is left as an empty section, never
   invented.
3. **Coverage table.** `knowledge/README.md` gets a table with one row per
   file and columns Seeded, Interviewed, Reviewed. Claude fills Seeded.
4. **Interview.** Role by role, newest first, in chat. Each role gets the
   same six prompts: why you joined and what the company does, the work,
   outcomes and numbers, two or three stories, what you learned, why you
   moved on. Answers are appended verbatim to
   `knowledge/raw/interviews/<role-slug>.md` and folded into the role file.
   Topic and FAQ material that surfaces goes to its own file.
5. **Review gate.** Drafts and partially interviewed files may be committed
   locally so nothing is lost. Adam reads each file when he is satisfied
   with it and sets the `reviewed` date. The gate is on pushing: no knowledge
   file leaves this machine without a `reviewed` date.

**Done state for this spec.** The monologue is captured in `raw/`, the resume
text is in `raw/`, all seed drafts exist and load, the coverage table is
filled in, and this workflow is written into `knowledge/README.md`. The
`topics/` directory is empty at the done state apart from a `.gitkeep`,
because topic files come from the interviews; the README says so. The
role-by-role interviews are a rolling activity that continues after this
spec is complete; they are not tasks in its implementation plan.

## 8. Twin application changes

### 8.1 Modules

| Module | Responsibility | Public interface |
|---|---|---|
| `config.py` | Read environment, validate, expose an immutable `Settings`. | `Settings.from_env() -> Settings`; raises `ConfigError` listing every missing required variable. |
| `knowledge.py` | Find, parse, validate, order knowledge files. | `load_knowledge(root: Path) -> Knowledge`; `Knowledge` is a frozen dataclass holding a tuple of `KnowledgeFile` (path, meta, body). |
| `prompt.py` | Build the system prompt from `Knowledge`. | `build_system_prompt(knowledge: Knowledge) -> str`. Pure function. |
| `tools.py` | Tool schemas, handlers, dispatch. | `ToolRegistry` protocol with `schemas` and `call(name, args) -> str`; `PushoverTools` implementation; `dispatch(registry, tool_calls) -> list[dict]`. Three tools: the course's `record_user_details` and `record_unknown_question`, plus `record_sensitive_question`, which pushes a notification when the twin deflects a question on a topic a boundary says Adam handles himself. |
| `agent.py` | The chat-completions loop. | `TwinAgent(client, settings, system_prompt, tools)`; `reply(history, message) -> str`. `history` is a list of `{role, content}` dicts in the OpenAI messages format and is passed to the model unchanged. |
| `examples.py` | The example questions. | `EXAMPLE_QUESTIONS: tuple[str, ...]`. |
| `scripts/chat.py` | Wire the above into a terminal REPL. | `main() -> int`; exits 1 with one message when config or knowledge is invalid. |
| `scripts/smoke.py` | Run fixed questions through the agent with a recording tool registry. | `main() -> int`. |

Every dependency that touches the network (OpenAI client, Pushover) is passed
in, never constructed inside the module that uses it, so tests and evals can
substitute fakes.

### 8.2 Configuration

| Variable | Required | Default | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | | |
| `TWIN_MODEL` | no | `gpt-5.4-mini` | |
| `PUSHOVER_USER`, `PUSHOVER_TOKEN` | no | | If either is absent, tools log to stderr instead of pushing, and startup logs a warning. |
| `KNOWLEDGE_DIR` | no | `<repo>/knowledge` | |

Missing required variables produce one `ConfigError` naming all of them, not
a `KeyError` on the first.

### 8.3 System prompt

Built from three parts in order: the role instructions (who the twin is,
that it is an AI, that it represents Adam), the knowledge files each under a
heading of its title and kind, and the rules (stay on professional topics,
never invent, use the unknown-question tool, deflect the topics in
boundaries and call the sensitive-question tool where a boundary says so,
ask for email when a visitor wants to get in touch, markdown without code
blocks). The rules text moves
from the course prompt largely unchanged. No file body is altered on the way
in.

### 8.4 Tool handling and errors

- A tool that raises returns a tool message containing a short error string
  to the model, and the error is logged with the tool name and arguments. The
  chat continues.
- An unknown tool name returns "unknown tool" to the model, as today.
- Pushover HTTP failures are caught in `PushoverTools`, logged, and reported
  to the model as "notification failed"; the conversation is not affected.
- The completion loop allows at most 5 consecutive tool rounds. If the cap
  is hit, the agent makes one final completion with `tool_choice="none"`
  and returns its text, so the visitor always gets a reply rather than an
  empty tool-call message.

### 8.5 Local dev harness

There is no Gradio. `scripts/chat.py` is a terminal REPL that holds a
multi-turn conversation, and `scripts/smoke.py` runs a fixed question set
and prints replies and tool calls. Both are development tools only. The
browser chat arrives with the site spec, and none of the course app's UI or
CSS is carried into this repo.

## 9. Tests and evals

### 9.1 Unit tests

Written before the implementation, run with `uv run pytest`, no network, no
API key. Target 80 percent line coverage of the `twin` package, measured with
`pytest-cov`.

- `config.py`: all required present; one missing; several missing lists all;
  defaults applied.
- `knowledge.py`: valid tree loads in the documented order; missing `public`
  fails naming the file; bad `kind`; missing `period` on a role; empty body;
  `raw/` and `README.md` are skipped; token warning fires above threshold.
- `prompt.py`: contains every file title; order preserved; rules present;
  bodies unmodified.
- `tools.py`: dispatch routes to the right handler; handler exception becomes
  an error tool message; unknown tool; Pushover HTTP failure handled;
  logging fallback when Pushover is unconfigured.
- `agent.py`: with a fake client, a plain reply returns text; a tool-call
  reply dispatches then returns the follow-up text; the 5-round cap.
- The real `knowledge/` tree: one test calls `load_knowledge` on the
  repository's actual knowledge directory and asserts it loads. This makes
  "all seed drafts exist and load" checkable by `uv run pytest` and catches
  a bad frontmatter edit before it reaches the app.

### 9.2 Eval set

`evals/twin_qa.yaml` is a list of cases:

```yaml
- id: rf-tenure
  category: fact          # fact | boundary | unknown | voice
  question: How long were you at Recorded Future?
  must_include: ["2018", "2022"]     # case-insensitive substrings, all required
  must_not_include: []
  expect_tool: null                  # or a tool name that must be called
  max_words: null
```

The runner applies every non-null field the same way for every case:
`must_include` substrings must all appear, `must_not_include` substrings must
all be absent, `expect_tool` must have been called, and the reply must not
exceed `max_words`. `category` is a label for reporting and signals which
fields a case typically uses:

- **fact**: `must_include` carries the facts, `must_not_include` catches
  known confusions.
- **boundary**: `must_not_include` catches the leak, and `expect_tool` is
  `record_sensitive_question` for topics that must notify Adam. Whether the
  deflection reads well is judged by Adam reading the transcript, not by the
  runner.
- **unknown**: `expect_tool` is `record_unknown_question`; `must_not_include`
  carries the plausible inventions.
- **voice**: `must_not_include` catches phrases Adam would never use
  ("As an AI language model", "I'm just an AI"); `max_words` catches
  rambling.

The first eval set has at least one fact case per role, five boundary cases
from `boundaries.md`, five unknown cases, and five voice cases. It grows as
the interviews add facts.

### 9.3 Eval runner

`tests/test_evals.py` is marked `integration` and skipped when
`OPENAI_API_KEY` is unset. Each case runs as a fresh single-turn
conversation through `TwinAgent` with a `RecordingTools` registry that
captures calls and never contacts Pushover, so evals do not page Adam. Each
case is a separate parametrized test, so a failure names the case id. Model
output is not deterministic, so the runner retries a failing case once
before reporting it; two failures in a row is a real failure.

## 10. Success criteria

1. `uv run pytest -m "not integration"` passes with at least 80 percent
   coverage of `twin/`.
2. `uv run pytest -m integration` passes every case in `evals/twin_qa.yaml`
   with a real API key.
3. `uv run python scripts/smoke.py` answers the four example questions from
   the knowledge files with no reference to LinkedIn text, and
   `uv run python scripts/chat.py` holds a multi-turn conversation.
4. Starting with no `.env` prints one message naming `OPENAI_API_KEY` and
   exits non-zero.
5. Every committed knowledge file has `public: true`. Every knowledge file
   that is ever pushed also has a `reviewed` date; the Deployment spec owns
   the check that enforces this before the first push.
6. Everything is committed locally with `origin` set to
   `adamlittleusa/DigitalTwin`, so the eventual push is a single command.
   No push is part of this spec.

## 11. Risks

- **Everything the twin knows is extractable.** Accepted by design. The
  defence is that sensitive material is never in the knowledge files, not
  that it is hidden. `boundaries.md` and the review gate are the controls.
- **Tool abuse.** A visitor can make the twin call the notification tools
  repeatedly. Acceptable while the app runs only locally; rate limiting is
  part of the API spec and must land before public deployment.
- **Invention.** The model may fill gaps in thin role files. The unknown
  category evals and the "leave sections empty, never invent" drafting rule
  are the controls.
- **Stale knowledge.** `reviewed` dates and the coverage table make staleness
  visible.
- **Raw transcripts have no backup.** `knowledge/raw/` is gitignored and the
  repo sits outside OneDrive, yet those transcripts are the source of truth.
  Mitigation: after each narration or interview session, Adam copies
  `knowledge/raw/` to a OneDrive folder; `knowledge/README.md` says so in
  its workflow section.
- **Removed content survives in git history.** A draft may contain something
  Adam strikes on review, such as a client name from the monologue, and the
  first push sends the whole history. Mitigation, owned by the Deployment
  spec: scan history for removed knowledge content before the first push
  and squash the knowledge commits if anything is found. Adam may instead
  choose to commit knowledge files only after review; either is fine, and
  the plan assumes the scan-and-squash route.
- **Eval flakiness.** A live model can fail a case on phrasing rather than
  knowledge. The single retry in 9.3 is the control; if a case flakes
  repeatedly, its assertions are too tight and get loosened, not the
  knowledge.

## 12. Follow-on specs, in order

1. Twin API: FastAPI, streaming, rate limiting, the portfolio guide tool.
2. Site and design system: Next.js, custom chat UI, the aesthetic work.
3. Deployment: Vercel, API host, DNS for adambuilds.ai.
