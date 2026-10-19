"""The activity library and the template plan the Coach falls back on (PRD 3.1, 8)."""

import json
from pathlib import Path

import pytest
from aloai_guardrails import validate_parent_summary
from services.core.coach import library
from services.core.coach.template import (
    RETRY_ADVICE,
    STRENGTHS,
    default_activities,
    next_check_days,
    template_home_practice,
    template_summary,
)
from services.core.tests.support import demo_report

PROFILES = sorted(STRENGTHS)
ALL_PROFILES = [*PROFILES, "INSUFFICIENT_EVIDENCE"]


def test_activity_ids_are_unique():
    listed = json.loads(Path(library.__file__).with_name("activities.json").read_text())
    assert len(listed["activities"]) == len(library.ACTIVITIES) == 30


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("arl", range(1, 13))
def test_every_profile_has_three_activities_at_every_level(profile, arl):
    assert len(library.activities_for(profile, arl)) >= 3


def test_without_a_level_every_activity_for_the_profile_is_offered():
    tagged = [a for a in library.ACTIVITIES.values() if "ON_TRACK" in a["profiles"]]
    assert library.activities_for("ON_TRACK", None) == tagged


@pytest.mark.parametrize("activity_id", sorted(library.ACTIVITIES))
def test_no_activity_would_fail_the_guardrail(activity_id):
    activity = library.ACTIVITIES[activity_id]
    assert validate_parent_summary(f"{activity['title']}. {activity['text']}", {}) == []


@pytest.mark.parametrize("profile", ALL_PROFILES)
@pytest.mark.parametrize("wcpm", [68.0, 93.8, None])
def test_the_template_text_passes_the_guardrail(profile, wcpm):
    report = demo_report(code=profile, wcpm=wcpm)
    assert validate_parent_summary(template_summary(report, "Chidi"), report) == []
    assert validate_parent_summary(template_home_practice(report), report) == []


def test_the_template_summary_states_the_rounded_wcpm_and_the_first_activity():
    summary = template_summary(demo_report(code="ON_TRACK", wcpm=93.8), "Chidi")
    assert summary.startswith("Chidi read accurately")
    assert "Chidi read 94 words correctly in a minute." in summary
    assert "Try this at home: pictures in the mind." in summary


def test_without_a_wcpm_the_summary_states_no_number():
    summary = template_summary(demo_report(code="DECODING_LIMITED", wcpm=None), "Chidi")
    assert not any(character.isdigit() for character in summary)


def test_insufficient_evidence_suggests_another_check_and_no_activity():
    report = demo_report(code="INSUFFICIENT_EVIDENCE", reported_arl=None)
    assert default_activities(report) == []
    assert template_summary(report, "Chidi").endswith(RETRY_ADVICE)
    assert template_home_practice(report) == RETRY_ADVICE


@pytest.mark.parametrize(
    "profile, provisional, days",
    [
        ("ON_TRACK", False, 14),
        ("ON_TRACK", True, 7),
        ("INSUFFICIENT_EVIDENCE", False, 7),
    ],
)
def test_the_next_check_is_sooner_when_the_result_is_uncertain(profile, provisional, days):
    assert next_check_days(demo_report(code=profile, provisional=provisional)) == days
