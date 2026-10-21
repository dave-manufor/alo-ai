import json
from types import SimpleNamespace

from aloai_store import MemoryStore
from services.session_agent.tools import cloud_smoke
from services.session_agent.tools.cloud_smoke import Check, report_done, run_smoke, wait_for


class Clock:
    """Time that only moves when the test sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class Admin:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts

    def get_queue_runtime_properties(self, queue: str):
        return SimpleNamespace(dead_letter_message_count=self.counts[queue])


QUEUES = ["core-events", "scorer-events"]


def finished(store: MemoryStore, session_id: str) -> None:
    store.set(f"reports/{session_id}", {"parent_reporting": {"summary_script": "A good session."}})
    store.set(f"plans/plan_{session_id}", {"session_id": session_id})


# ---- the queues


def test_the_queues_are_the_two_in_events_json():
    assert cloud_smoke.queue_names() == QUEUES


def test_queue_names_read_the_given_file(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"queues": {"b": [], "a": []}}))
    assert cloud_smoke.queue_names(path) == ["a", "b"]


def test_dead_letter_counts_asks_each_queue():
    assert cloud_smoke.dead_letter_counts(
        Admin({"core-events": 0, "scorer-events": 3}), QUEUES
    ) == {
        "core-events": 0,
        "scorer-events": 3,
    }


# ---- a finished report


def test_session_ids_are_new_each_time_and_marked_as_smoke():
    first, second = cloud_smoke.new_session_id(), cloud_smoke.new_session_id()
    assert first != second
    assert first.startswith("sess_smoke_")


def test_a_report_is_done_with_the_plan_and_the_parents_summary():
    store = MemoryStore()
    assert not report_done(store, "s1")
    store.set("reports/s1", {"parent_reporting": {"summary_script": "x"}})
    assert not report_done(store, "s1")  # no plan yet
    store.set("plans/plan_s1", {})
    assert report_done(store, "s1")


def test_a_report_without_the_summary_is_not_done():
    for report in ({}, {"parent_reporting": None}, {"parent_reporting": {"summary_script": ""}}):
        store = MemoryStore()
        store.set("reports/s1", report)
        store.set("plans/plan_s1", {})
        assert not report_done(store, "s1")


# ---- waiting


def test_wait_for_returns_as_soon_as_the_condition_holds():
    clock = Clock()
    calls = []

    def condition() -> bool:
        calls.append(clock.now)
        return len(calls) == 3

    assert wait_for(condition, timeout_s=60, interval_s=5, clock=clock, sleep=clock.sleep)
    assert calls == [0.0, 5.0, 10.0]


def test_wait_for_gives_up_at_the_timeout():
    clock = Clock()
    assert not wait_for(lambda: False, timeout_s=12, interval_s=5, clock=clock, sleep=clock.sleep)
    assert clock.now == 15.0


# ---- the whole smoke


def smoke(store, admin, drive, timeout_s=30) -> list[Check]:
    clock = Clock()
    return run_smoke(
        store=store,
        admin=admin,
        queues=QUEUES,
        drive=drive,
        timeout_s=timeout_s,
        interval_s=5,
        clock=clock,
        sleep=clock.sleep,
    )


def test_a_good_run_passes_every_check_and_makes_the_fictional_child():
    store = MemoryStore()

    def drive(session_id: str, child_id: str) -> dict:
        assert child_id == cloud_smoke.CHILD_ID
        store.set(f"sessions/{session_id}", {"status": "COMPLETE"})
        finished(store, session_id)
        return {"ended": True, "messages": 40}

    checks = smoke(store, Admin({"core-events": 0, "scorer-events": 0}), drive)
    assert [c.ok for c in checks] == [True] * 5
    assert store.get("children/child_smoke") == cloud_smoke.CHILD
    assert "status COMPLETE" in checks[2].detail
    assert "40 agent messages" in checks[0].detail


def test_the_child_document_has_what_the_grader_reads():
    assert cloud_smoke.CHILD["guardian_id"]
    assert 1 <= cloud_smoke.CHILD["primary_class"] <= 6


def test_no_report_in_time_fails_that_check_only():
    store = MemoryStore()
    checks = smoke(
        store, Admin({"core-events": 0, "scorer-events": 0}), lambda s, c: {"ended": True}
    )
    failed = [c.name for c in checks if not c.ok]
    assert failed == ["report and plan written", "session record"]
    assert "not within 30 s" in checks[1].detail


def test_a_dead_letter_message_fails_that_queue():
    store = MemoryStore()

    def drive(session_id: str, child_id: str) -> dict:
        finished(store, session_id)
        return {"ended": True}

    checks = smoke(store, Admin({"core-events": 0, "scorer-events": 2}), drive)
    failed = [c for c in checks if not c.ok]
    assert [c.name for c in failed if "dead-letter" in c.name] == [
        "dead-letter queue scorer-events is empty"
    ]
    assert failed[-1].detail == "2 messages"


def test_a_session_that_did_not_end_fails_even_if_a_report_appears():
    store = MemoryStore()

    def drive(session_id: str, child_id: str) -> dict:
        finished(store, session_id)
        return {"ended": False, "messages": 3}

    checks = smoke(store, Admin({"core-events": 0, "scorer-events": 0}), drive)
    assert not checks[0].ok
    assert checks[1].ok


def test_a_crash_in_the_session_is_reported_and_the_other_checks_still_run():
    def drive(session_id: str, child_id: str) -> dict:
        raise ConnectionError("no route to LiveKit")

    checks = smoke(MemoryStore(), Admin({"core-events": 0, "scorer-events": 0}), drive, timeout_s=5)
    assert checks[0] == Check("session ran", False, "ConnectionError: no route to LiveKit")
    assert len(checks) == 5


def test_a_check_prints_as_one_line():
    assert Check("a", True).line() == "PASS  a"
    assert Check("b", False, "why").line() == "FAIL  b: why"
