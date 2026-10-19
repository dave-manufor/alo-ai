"""Tests for aloai_guardrails (PRD 3.1). The library must stay at 100% line coverage.

The banned terms appear here on purpose: these tests prove the guardrail refuses them.
"""

import json
from pathlib import Path

import pytest
from aloai_guardrails import traceable_numbers, validate_parent_summary

REPORT = json.loads(
    (
        Path(__file__).resolve().parents[1] / "fixtures/contracts/reading_report.sess_demo_001.json"
    ).read_text()
)
CHIDI = {
    "fluency": {"wcpm": 93.8, "accuracy_pct": 97.7},
    "comprehension": {"retell_coverage": 0.72},
}
CHIDI_SUMMARY = (
    "Chidi read 94 words correctly in a minute and got almost every word right. Reading the "
    "words is a real strength. He remembered parts of the story but found it hard to explain "
    "why things happened, even when I read a story to him. This was a short check, so think "
    "of it as a first look."
)


def test_chidis_summary_from_the_worked_session_passes():
    assert validate_parent_summary(CHIDI_SUMMARY, CHIDI) == []


def test_a_made_up_score_is_refused():
    problems = validate_parent_summary("Chidi scored 95 today.", CHIDI)
    assert problems == ["95 is in neither the report nor the plan"]


@pytest.mark.parametrize(
    "said", ["93.8 words a minute", "about 94 words a minute", "98% of words right", "72%"]
)
def test_numbers_from_the_report_may_be_rounded(said):
    assert validate_parent_summary(f"Chidi read {said}.", CHIDI) == []


def test_numbers_from_the_plan_are_allowed():
    text = "Read together every day, and check again in 14 days."
    assert validate_parent_summary(text, CHIDI) == ["14 is in neither the report nor the plan"]
    assert validate_parent_summary(text, CHIDI, plan_numbers=[14]) == []


@pytest.mark.parametrize(
    "term",
    [
        "diagnosis",
        "Diagnosed",
        "dyslexia",
        "dyslexic",
        "a disorder",
        "behind",
        "failing",
        "a slow learner",
        "hyperlexic",
        "a word caller",
    ],
)
def test_terms_that_sound_like_a_diagnosis_are_refused(term):
    problems = validate_parent_summary(f"This is not {term}.", CHIDI)
    assert len(problems) == 1
    assert "sounds like a diagnosis" in problems[0]


def test_each_problem_is_reported_once():
    text = "Behind, behind: 95 and 95."
    assert validate_parent_summary(text, CHIDI) == [
        "uses 'behind', which sounds like a diagnosis",
        "95 is in neither the report nor the plan",
    ]


def test_a_summary_over_90_words_is_refused():
    assert validate_parent_summary("word " * 90, CHIDI) == []
    assert validate_parent_summary("word " * 91, CHIDI) == ["91 words; the limit is 90"]


def test_true_and_false_are_not_numbers():
    assert traceable_numbers({"word_reading_ok": True, "at_least": False}) == set()


def test_numbers_are_found_anywhere_in_a_full_report():
    numbers = traceable_numbers(REPORT)
    assert {90.9, 68.0, 70.0, 2.0, 50.0} <= numbers
