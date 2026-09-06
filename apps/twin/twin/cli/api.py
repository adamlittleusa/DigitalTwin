"""Run the twin API with uvicorn.

Usage, from apps/twin: uv run twin-api
"""

from __future__ import annotations

import logging

import uvicorn

from twin.config import ConfigError, Settings, load_env_file

log = logging.getLogger("twin.api")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    load_env_file()
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        log.error("Cannot start: %s", exc)
        return 1
    uvicorn.run("twin.api.asgi:app", host=settings.host, port=settings.port, log_level="info")
    return 0
