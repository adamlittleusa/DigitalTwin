# adambuilds

Source for [adambuilds.ai](https://adambuilds.ai): a portfolio of AI agent
projects by Adam Little. The first project is a digital twin, an agent that
answers questions about Adam's career in his voice.

## Layout

| Path | What |
|---|---|
| `apps/twin/` | The twin: Python package and tests. `twin/cli/` holds the console commands; `twin/api/` the HTTP service (added in the next task). |
| `apps/web/` | The site. Not started yet. |
| `knowledge/` | The twin's knowledge of Adam, as reviewed markdown. See `knowledge/README.md`. |
| `evals/` | Question sets the twin must answer correctly. |
| `docs/superpowers/` | Design specs and implementation plans. |

## Run the twin locally

Requires [uv](https://docs.astral.sh/uv/). Create `.env` at the repo root
from `.env.example` and fill in `OPENAI_API_KEY` (everything else is
optional).

    cd apps/twin
    uv sync
    uv run twin-chat      # multi-turn chat in the terminal, showing the agent's steps
    uv run twin-smoke     # fixed questions, prints replies and tool calls
    uv run twin-api       # the HTTP API on http://localhost:8080

## The API

`POST /v1/chat` takes `{"messages": [{"role": "user", "content": "..."}]}`
and streams Server-Sent Events: `step`, `tool`, `tool_result`, `delta`,
`project`, `done`, `agent_error`. `GET /v1/health`, `/v1/examples`, and
`/v1/projects` are plain JSON. Limits and origins are configured through
the `TWIN_*` variables in `.env.example`. See
`docs/superpowers/specs/2026-09-05-twin-api-design.md`.

## Test

    cd apps/twin
    uv run pytest                        # unit tests, never calls the model
    uv run pytest --cov=twin             # with the 80 percent coverage gate
    uv run pytest -m integration         # the evals and one API turn against the real model
    uv run pytest -m integration -k "boundary or unknown"   # a subset; case ids work with -k
