import asyncio

from services.session_agent.livekit_worker import _wait_for_child


class FakeCtx:
    def __init__(self, arrives_after: float | None) -> None:
        self.arrives_after = arrives_after
        self.shutdowns: list[str] = []

    async def wait_for_participant(self):
        if self.arrives_after is None:
            await asyncio.Event().wait()  # nobody ever comes
        await asyncio.sleep(self.arrives_after)
        return "child"

    def shutdown(self, reason: str) -> None:
        self.shutdowns.append(reason)


def test_the_child_who_joins_in_time_is_returned():
    ctx = FakeCtx(arrives_after=0)
    assert asyncio.run(_wait_for_child(ctx, 1)) == "child"
    assert ctx.shutdowns == []


def test_nobody_joining_ends_the_job_instead_of_waiting_for_ever():
    ctx = FakeCtx(arrives_after=None)
    assert asyncio.run(_wait_for_child(ctx, 0.05)) is None
    assert ctx.shutdowns == ["nobody joined"]
