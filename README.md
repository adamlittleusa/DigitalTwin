# adambuilds

Source for [adambuilds.ai](https://adambuilds.ai): a portfolio of AI agent
projects by Adam Little. The first project is a digital twin, an agent that
answers questions about Adam's career in his voice.

## Layout

| Path | What |
|---|---|
| `apps/twin/` | The twin: Python package, tests, and terminal dev scripts. |
| `apps/web/` | The site. Not started yet. |
| `knowledge/` | The twin's knowledge of Adam, as reviewed markdown. See `knowledge/README.md`. |
| `evals/` | Question sets the twin must answer correctly. |
| `docs/superpowers/` | Design specs and implementation plans. |

## Run the twin locally

Requires [uv](https://docs.astral.sh/uv/). Create `.env` at the repo root
from `.env.example` and fill in `OPENAI_API_KEY` (the Pushover pair is
optional).

    cd apps/twin
    uv sync
    uv run python scripts/chat.py      # multi-turn chat in the terminal
    uv run python scripts/smoke.py     # fixed questions, prints replies and tool calls

## Test

    cd apps/twin
    uv run pytest -m "not integration" --cov=twin --cov-report=term-missing
    uv run pytest -m integration        # runs the evals against the real model
    uv run pytest -m integration -k "boundary or unknown"   # a subset; case ids work with -k
