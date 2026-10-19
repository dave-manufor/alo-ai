"""Blocking cloud calls, run off the event loop; the session waits for them before ending.

Uploads and record writes start at once (run). An event starts only after every call
queued before it has finished (run_after_pending), so it never reaches the Reading
Scorer or the Grader ahead of the audio and records it names. Events keep their order
too, because each one waits for the earlier events as well.
"""

import asyncio
import functools
import logging

log = logging.getLogger("aloai.session_agent")


class Background:
    def __init__(self) -> None:
        self._pending: set[asyncio.Future] = set()

    def run(self, fn, *args) -> None:
        loop = asyncio.get_running_loop()
        self._track(loop.run_in_executor(None, functools.partial(fn, *args)))

    def run_after_pending(self, fn, *args) -> None:
        """Run fn once everything queued so far has finished, whether it worked or not:
        a failed write is already logged, and a lost event would lose the session."""
        loop = asyncio.get_running_loop()
        before = set(self._pending)

        async def later() -> None:
            if before:
                await asyncio.gather(*before, return_exceptions=True)
            await loop.run_in_executor(None, functools.partial(fn, *args))

        self._track(asyncio.ensure_future(later()))

    def _track(self, future: asyncio.Future) -> None:
        self._pending.add(future)
        future.add_done_callback(self._done)

    def _done(self, future: asyncio.Future) -> None:
        self._pending.discard(future)
        if not future.cancelled() and future.exception() is not None:
            log.error("background call failed", exc_info=future.exception())

    async def drain(self) -> None:
        """Wait until nothing is pending, including work queued while waiting."""
        while self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
