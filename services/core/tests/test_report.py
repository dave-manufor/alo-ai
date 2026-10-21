"""Building the ReadingReport (PRD 10.4) from telemetry and reconciled grading."""

import aloai_contracts
import pytest
from services.core.grader.report import ReportInputs, build_report
from services.core.tests.support import NOW, PASSAGE_ID, SESSION_ID, contract

READ = {
    "passage_id": PASSAGE_ID,
    "total_weight": 6,
    "weighted_credit": 5.5,
    "item_points": [2, 0],
    "disagreement": False,
}
LISTEN = {
    "passage_id": "bank_l3_rain",
    "total_weight": 6,
    "weighted_credit": 6,
    "item_points": [2, 2],
    "disagreement": False,
}
LOW_READ = READ | {"weighted_credit": 1.0, "item_points": [0, 0]}
QUICK = {"quick_rc": 70.0, "item_points": [2, 0], "run_listening_module": True}


def report(quick=QUICK, previous=None, **grading) -> dict:
    built = build_report(
        ReportInputs(
            session_id=SESSION_ID,
            session=contract("session_record.session.json"),
            child={"guardian_id": "guardian_demo_001", "primary_class": 2},
            passage=contract("passage.bank_p3_market_day.json"),
            telemetry=contract("phase1_telemetry.sess_demo_001.json"),
            grading={
                "reading_stopped_early": False,
                "listening_module_run": True,
                "capture_mode": "LIVE",
                "session_settings": {"voice_mode": "cache_first", "session_profile": "demo"},
                "session_flags": ["DEMO_PROFILE"],
                "read": READ,
                "listen": None,
            }
            | grading,
            quick=quick,
            previous_reported_arl=previous,
            now=NOW,
        )
    )
    aloai_contracts.READING_REPORT.validate(built)
    return built


def test_the_demo_session_report():
    built = report()
    assert built["comprehension"] == {
        "reading_comprehension": 70.0,
        "retell_coverage": 1.0,
        "item_score": 0.5,
        "quick_reading_comprehension": 70.0,
        "listening_module_run": True,
        "listening_comprehension": None,
        "listening_used": False,
        "quick_vs_final_item_agreement": 1.0,
    }
    assert built["fluency"]["word_reading_ok"] is False
    assert built["profile"]["code"] == "UNDERSTANDS_BUILDING_WORD_READING"
    assert built["profile"]["provisional"] is True
    assert built["level"] == {
        "passage_arl": 3,
        "band": "SUPPORTED",
        "reported_arl": 2,
        "at_least": False,
        "confirmed": False,
        "next_passage_arl": 2,
        "approx_primary_class": "Primary 1 (approximate, not normed)",
    }
    assert built["recommendations"] == {"arl_min": 1, "arl_max": 2, "book_ids": []}
    assert built["flags"] == ["DEMO_PROFILE", "SHORT_READING"]
    assert (built["guardian_id"], built["timestamp_iso"]) == (
        "guardian_demo_001",
        "2026-01-15T09:09:05Z",
    )
    assert built["parent_reporting"] is None


def test_listening_is_used_when_reading_comprehension_is_low():
    built = report(read=LOW_READ, listen=LISTEN)
    assert built["comprehension"]["reading_comprehension"] == 11.1
    assert built["comprehension"]["listening_comprehension"] == 100.0
    assert built["comprehension"]["listening_used"] is True
    assert built["profile"]["code"] == "DECODING_LIMITED"


def test_listening_is_stored_but_not_used_when_final_rc_is_78_or_more():
    built = report(read=READ | {"item_points": [2, 2]}, listen=LISTEN)
    assert built["comprehension"]["listening_comprehension"] == 100.0
    assert built["comprehension"]["listening_used"] is False
    assert "LC_NOT_USED" in built["flags"]
    assert built["profile"]["code"] == "UNDERSTANDS_BUILDING_WORD_READING"


def test_a_missed_listening_module_gives_insufficient_evidence():
    built = report(read=LOW_READ, listening_module_run=False)
    assert "LC_MISSED" in built["flags"]
    assert built["profile"]["code"] == "INSUFFICIENT_EVIDENCE"
    assert built["recommendations"] == {"arl_min": None, "arl_max": None, "book_ids": []}


def test_a_reading_stopped_early_has_no_reading_comprehension():
    built = report(quick=None, reading_stopped_early=True, read=None, listen=LISTEN)
    assert built["comprehension"]["reading_comprehension"] is None
    assert built["comprehension"]["quick_vs_final_item_agreement"] is None
    assert built["profile"]["code"] == "DECODING_LIMITED"
    assert (built["level"]["band"], built["level"]["reported_arl"]) == ("FRUSTRATION", 1)
    assert built["level"]["next_passage_arl"] == 1


def test_grader_disagreement_is_flagged():
    built = report(read=READ | {"disagreement": True})
    assert "GRADER_DISAGREEMENT" in built["flags"]


@pytest.mark.parametrize("previous, confirmed", [(None, False), (2, True), (3, True), (4, False)])
def test_a_level_is_confirmed_by_the_previous_session(previous, confirmed):
    assert report(previous=previous)["level"]["confirmed"] is confirmed


def test_flags_are_not_repeated():
    built = report(session_flags=["DEMO_PROFILE", "SHORT_READING"])
    assert built["flags"] == ["DEMO_PROFILE", "SHORT_READING"]
