"""The Reading Coach set: its cases, its three metrics and its replay, on recorded turns."""

import copy
import dataclasses
import json
from pathlib import Path

import pytest
from eval import coach_set, models
from eval.coach_set import CaseResult, cases, score, tool_sequence_ok, totals
from eval.harness import case_report, run_case
from services.core.coach.agent import RecordedModel

ROOT = Path(__file__).resolve().parents[2]
DEMO_TURNS = json.loads((ROOT / "fixtures/ai/coach/sess_demo_001.json").read_text())["turns"]
DEMO = next(c for c in cases() if c["case_id"] == "c02_building_word_reading_provisional")
SAVE_PLAN = 3
IN_ORDER = [
    "get_report",
    "get_history",
    "get_activity_library",
    "search_books",
    "queue_story",
    "schedule_session",
    "save_plan",
    "send_parent_email",
]


def recorded(turns=DEMO_TURNS) -> RecordedModel:
    return RecordedModel(model="recorded/test", turns=turns)


def test_the_set_has_ten_cases_with_valid_reports():
    ids = [case["case_id"] for case in cases()]
    assert len(ids) == len(set(ids)) == 10
    profiles = {case_report(case)["profile"]["code"] for case in cases()}
    assert len(profiles) == 7
    assert any("LC_MISSED" in case_report(case)["flags"] for case in cases())


@pytest.mark.parametrize(
    "tools, ok",
    [
        (IN_ORDER, True),
        (["get_history", "get_report", *IN_ORDER[2:]], True),
        ([*IN_ORDER[:7], "save_plan", "send_parent_email"], True),
        (IN_ORDER[:7], False),
        ([*IN_ORDER[:5], "save_plan", "schedule_session", "send_parent_email"], False),
        (["write_score", *IN_ORDER], False),
        (["get_report", *IN_ORDER], False),
    ],
    ids=[
        "in order",
        "any order in a step",
        "one rewrite",
        "no email",
        "out of order",
        "other tool",
        "repeat",
    ],
)
def test_the_tool_sequence_follows_the_coachs_steps(tools, ok):
    assert tool_sequence_ok(tools) is ok


def test_the_recorded_demo_run_meets_every_metric():
    result = score(DEMO["case_id"], run_case(DEMO, recorded()))
    assert (result.tool_sequence, result.library_only, result.validator_first_try) == (
        True,
        True,
        True,
    )


def test_a_rewritten_summary_misses_only_the_first_try():
    turns = copy.deepcopy(DEMO_TURNS)
    refused = copy.deepcopy(turns[SAVE_PLAN])
    refused["parts"][0]["args"]["summary"] = "Chidi scored 95 today."
    turns.insert(SAVE_PLAN, refused)
    result = score(DEMO["case_id"], run_case(DEMO, recorded(turns)))
    assert (result.tool_sequence, result.library_only, result.validator_first_try) == (
        True,
        True,
        False,
    )


def test_a_run_that_stops_early_falls_back_to_library_activities():
    result = score(DEMO["case_id"], run_case(DEMO, recorded(DEMO_TURNS[:2])))
    assert (result.tool_sequence, result.library_only, result.validator_first_try) == (
        False,
        True,
        False,
    )


def results(**misses) -> list[CaseResult]:
    """Ten results, the first n of each metric failing."""
    return [
        CaseResult(
            f"c{n}",
            tool_sequence=n >= misses.get("tool_sequence", 0),
            library_only=n >= misses.get("library_only", 0),
            validator_first_try=n >= misses.get("validator_first_try", 0),
            tools=["get_report"],
        )
        for n in range(10)
    ]


@pytest.mark.parametrize(
    "misses, passed",
    [
        ({}, True),
        ({"tool_sequence": 1, "validator_first_try": 1}, True),
        ({"tool_sequence": 2}, False),
        ({"library_only": 1}, False),
    ],
)
def test_the_set_passes_only_at_every_threshold(misses, passed):
    assert coach_set.passed(results(**misses)) is passed


def test_the_summary_for_the_pr_names_each_metric_and_failure():
    text = coach_set.markdown(results(library_only=1), "recorded")
    assert text.startswith("Reading Coach set, recorded, gemini-2.5-flash, prompt coach_v1: FAIL")
    assert "| library_only | 9 of 10 | 10 |" in text
    assert "- c0: get_report" in text
    assert totals(results())["tool_sequence"] == 10


def test_a_replay_without_recordings_says_how_to_make_them(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(models, "RECORDED", tmp_path)
    assert coach_set.main([]) == 2
    assert "run with --live --record first" in capsys.readouterr().out


def test_a_replay_runs_every_recorded_case(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(models, "RECORDED", tmp_path)
    for case in cases():
        path = models.recording_path("coach", case["case_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"turns": DEMO_TURNS}))
    assert coach_set.main([]) in (0, 1)
    assert "Reading Coach set, recorded" in capsys.readouterr().out


def test_a_live_run_records_what_the_replay_then_repeats(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(models, "RECORDED", tmp_path)
    monkeypatch.setattr(coach_set, "RESULTS", tmp_path / "results" / "coach.json")
    monkeypatch.setattr(coach_set, "live_coach_model", lambda project, location: recorded())
    live = coach_set.main(["--live", "--record"])
    saved = json.loads((tmp_path / "results" / "coach.json").read_text())
    assert [result["case_id"] for result in saved] == [case["case_id"] for case in cases()]
    assert coach_set.main([]) == live
    assert "Reading Coach set, recorded" in capsys.readouterr().out


def test_a_run_without_a_plan_has_no_library_activities():
    run = run_case(DEMO, recorded())
    assert not coach_set.library_only(dataclasses.replace(run, plan=None))
