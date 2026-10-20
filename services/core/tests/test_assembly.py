"""Report assembly (SDD 7 step 6): written once, when grading and telemetry are both in."""

import aloai_contracts
from aloai_events import MemoryPublisher
from aloai_store import MemoryStore
from services.core.grader import paths
from services.core.tests.support import (
    SESSION_ID,
    add_telemetry,
    assembler,
    contract,
    seeded_store,
)

GRADING = {
    "reading_stopped_early": False,
    "listening_module_run": True,
    "capture_mode": "LIVE",
    "session_settings": {"voice_mode": "cache_first", "session_profile": "demo"},
    "session_flags": ["DEMO_PROFILE"],
    "read": {
        "passage_id": "bank_p3_market_day",
        "total_weight": 6,
        "weighted_credit": 5.5,
        "item_points": [2, 0],
        "disagreement": False,
    },
    "listen": None,
}


def graded_store() -> MemoryStore:
    store = seeded_store()
    store.set(paths.grading(SESSION_ID), GRADING)
    return store


def test_nothing_happens_until_grading_and_telemetry_are_both_in():
    publisher = MemoryPublisher()
    only_telemetry = seeded_store()
    add_telemetry(only_telemetry)
    assert not assembler(only_telemetry, publisher).assemble(SESSION_ID)
    assert not assembler(graded_store(), publisher).assemble(SESSION_ID)
    assert publisher.events == []


def test_the_report_is_written_once_and_announced_each_time():
    store, publisher = graded_store(), MemoryPublisher()
    add_telemetry(store)
    reports = assembler(store, publisher)
    assert reports.assemble(SESSION_ID)
    first = store.get(paths.report(SESSION_ID))
    store.merge(paths.report(SESSION_ID), {"flags": ["marker"]})
    assert reports.assemble(SESSION_ID)
    assert store.get(paths.report(SESSION_ID))["flags"] == ["marker"]
    assert first["profile"]["code"] == "UNDERSTANDS_BUILDING_WORD_READING"
    assert [event["data"] for event in publisher.events] == 2 * [
        {
            "session_id": SESSION_ID,
            "report_ref": "reports/sess_demo_001",
            "profile": "UNDERSTANDS_BUILDING_WORD_READING",
            "provisional": True,
        }
    ]
    for event in publisher.events:
        aloai_contracts.EVENT_ENVELOPE.validate(event)


def test_the_childs_next_passage_level_is_saved():
    store = graded_store()
    add_telemetry(store)
    assembler(store, MemoryPublisher()).assemble(SESSION_ID)
    assert store.get(paths.child("child_demo_001"))["next_passage_arl"] == 2


def test_the_childs_previous_report_confirms_the_level():
    store = graded_store()
    add_telemetry(store)
    earlier = contract("reading_report.sess_demo_001.json") | {
        "session_id": "sess_demo_000",
        "timestamp_iso": "2025-12-01T09:00:00Z",
    }
    store.set(paths.report("sess_demo_000"), earlier)
    assembler(store, MemoryPublisher()).assemble(SESSION_ID)
    assert store.get(paths.report(SESSION_ID))["level"]["confirmed"] is True


class RacingStore(MemoryStore):
    """Another instance writes the report between this one's read and its create."""

    def create(self, path: str, data: dict) -> bool:
        if path == paths.report(SESSION_ID):
            self.docs[path] = data | {"flags": ["written elsewhere"]}
            return False
        return super().create(path, data)


def test_a_report_written_elsewhere_first_is_kept():
    store = RacingStore(graded_store().docs)
    add_telemetry(store)
    publisher = MemoryPublisher()
    assembler(store, publisher).assemble(SESSION_ID)
    assert store.get(paths.report(SESSION_ID))["flags"] == ["written elsewhere"]
    assert store.get(paths.child("child_demo_001"))["next_passage_arl"] == 2
    assert len(publisher.events) == 1


def test_a_crash_between_the_report_and_the_childs_level_is_mended_on_redelivery():
    store, publisher = graded_store(), MemoryPublisher()
    add_telemetry(store)
    reports = assembler(store, publisher)
    reports.assemble(SESSION_ID)
    store.docs[paths.child("child_demo_001")].pop("next_passage_arl")
    reports.assemble(SESSION_ID)
    assert store.get(paths.child("child_demo_001"))["next_passage_arl"] == 2
    first, again = publisher.events
    assert first["event_id"] == again["event_id"]
