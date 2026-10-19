"""Background: an event is published only after the writes queued before it."""

import asyncio
import logging
import threading

from services.session_agent.background import Background


def test_a_publish_waits_for_the_writes_queued_before_it():
    order = []
    release = threading.Event()

    def upload():
        release.wait(5)
        order.append("upload")

    async def main():
        background = Background()
        background.run(upload)
        background.run_after_pending(order.append, "publish")
        await asyncio.sleep(0.05)
        assert order == []  # the publish has not run ahead of the upload
        release.set()
        await background.drain()

    asyncio.run(main())
    assert order == ["upload", "publish"]


def test_events_keep_their_order():
    order = []
    release = threading.Event()

    def upload():
        release.wait(5)
        order.append("upload")

    def slow_first_event():
        threading.Event().wait(0.05)
        order.append("phase1.recorded")

    async def main():
        background = Background()
        background.run(upload)
        background.run_after_pending(slow_first_event)
        background.run_after_pending(order.append, "session.done")
        release.set()
        await background.drain()

    asyncio.run(main())
    assert order == ["upload", "phase1.recorded", "session.done"]


def test_later_work_does_not_wait_for_a_publish():
    order = []
    release = threading.Event()

    def upload():
        release.wait(5)
        order.append("upload")

    async def main():
        background = Background()
        background.run(upload)
        background.run_after_pending(order.append, "publish")
        background.run(order.append, "turn record")
        await asyncio.sleep(0.05)
        assert order == ["turn record"]
        release.set()
        await background.drain()

    asyncio.run(main())
    assert order == ["turn record", "upload", "publish"]


def test_a_failed_write_is_logged_and_the_event_still_goes(caplog):
    order = []

    def broken_upload():
        raise RuntimeError("bucket unreachable")

    async def main():
        background = Background()
        background.run(broken_upload)
        background.run_after_pending(order.append, "publish")
        await background.drain()

    with caplog.at_level(logging.ERROR, logger="aloai.session_agent"):
        asyncio.run(main())
    assert order == ["publish"]
    assert "background call failed" in caplog.text


def test_a_failed_publish_is_logged(caplog):
    def broken_publish():
        raise RuntimeError("topic unreachable")

    async def main():
        background = Background()
        background.run_after_pending(broken_publish)
        await background.drain()

    with caplog.at_level(logging.ERROR, logger="aloai.session_agent"):
        asyncio.run(main())
    assert "background call failed" in caplog.text


def test_with_nothing_pending_a_publish_runs_at_once_and_drain_returns():
    order = []

    async def main():
        background = Background()
        await background.drain()
        background.run_after_pending(order.append, "publish")
        await background.drain()

    asyncio.run(main())
    assert order == ["publish"]


def test_drain_also_waits_for_work_queued_while_it_waits():
    order = []

    def slow_write():
        threading.Event().wait(0.05)
        order.append("write")

    async def main():
        background = Background()
        background.run(slow_write)

        async def late_event():
            await asyncio.sleep(0.01)
            background.run_after_pending(order.append, "publish")

        late = asyncio.ensure_future(late_event())
        await background.drain()
        await late

    asyncio.run(main())
    assert order == ["write", "publish"]


def test_a_cancelled_call_does_not_stop_the_drain(caplog):
    async def main():
        background = Background()
        background.run_after_pending(threading.Event().wait, 0.05)
        next(iter(background._pending)).cancel()
        await background.drain()

    with caplog.at_level(logging.ERROR, logger="aloai.session_agent"):
        asyncio.run(main())
    assert "background call failed" not in caplog.text
