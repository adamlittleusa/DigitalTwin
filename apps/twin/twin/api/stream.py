"""Run a synchronous agent turn in a thread and expose its events to async code.

The thread runs the turn to completion regardless of whether anyone is still listening, so a tool
call that already started (a notification to Adam) finishes even if the visitor closed the tab.

The worker is a daemon thread, so it is killed at interpreter exit: a notification in flight during
a deploy can be lost. That trade-off is accepted for now; it will be revisited with uvicorn's
graceful-shutdown timeout in the deployment work.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable, Iterator

from twin.agent import FALLBACK_REPLY
from twin.events import AgentEvent, Done, Error

log = logging.getLogger(__name__)
_END = object()


class AgentStream:
    """Bridge a synchronous event generator to the HTTP service's async iteration.

    The worker thread runs blocking model/tool work. An async queue lets the HTTP task
    wait for events without doing that blocking work on the server's event loop.
    Disconnecting the consumer does not cancel the worker or its remaining tool calls.
    """

    def __init__(self, turn: Callable[[], Iterator[AgentEvent]]) -> None:
        self._turn = turn

    async def __aiter__(self) -> AsyncIterator[AgentEvent]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[object] = asyncio.Queue()

        def put(item: object) -> None:
            try:
                # asyncio.Queue belongs to the event-loop thread. Schedule its write
                # there instead of modifying the queue directly from the worker thread.
                loop.call_soon_threadsafe(queue.put_nowait, item)
            except RuntimeError:  # the loop is gone because the response already ended; the turn still completes
                pass

        def worker() -> None:
            try:
                for event in self._turn():
                    put(event)
            except Exception:  # the agent never raises, so this is a belt-and-braces guard
                log.exception("Agent turn failed outside the loop")
                put(Error("internal", "Something went wrong on our side."))
                put(Done(FALLBACK_REPLY, (), 0, None))
            finally:
                # This private sentinel means no more events will arrive. It is not
                # a Done event and is never serialized or displayed to the visitor.
                put(_END)

        threading.Thread(target=worker, name="twin-agent-turn", daemon=True).start()
        while True:
            item = await queue.get()
            if item is _END:
                return
            yield item  # type: ignore[misc]
