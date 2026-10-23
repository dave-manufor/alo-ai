"""Run a background task so that if it stops, someone hears about it.

The speech pipeline (audio frames, voice detection, speech to text) runs as three tasks the
session never awaits. A task that raises vanished without a log line, and the session carried
on as if the child said nothing. `supervised` keeps a reference, and reports how the task
ended: by name, with the exception class only (an error's message can quote what was heard,
and a child's words stay out of logs).
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

# Strong references: a task nobody holds can be collected before it finishes.
_running: set[asyncio.Task] = set()


def supervised(
    name: str,
    work: Coroutine[Any, Any, None],
    *,
    log: logging.Logger,
    stopped: Callable[[str, str], None],
) -> asyncio.Task:
    async def run() -> None:
        try:
            await work
        except asyncio.CancelledError:
            raise
        except Exception as error:
            how = type(error).__name__
            log.error("%s stopped: %s", name, how)
            stopped(name, how)
        else:
            log.info("%s ended", name)
            stopped(name, "ended")

    task = asyncio.get_running_loop().create_task(run(), name=name)
    _running.add(task)
    task.add_done_callback(_running.discard)
    return task
