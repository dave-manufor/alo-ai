"""The Session Agent's copies of values the after-session services also hold (libs/aloai).

The agent keeps its own event versions and told-word wait, so its image needs neither
libs/aloai nor schemas/ at run time. These tests make the two sides change together.
"""

from datetime import date

import aloai_events
import aloai_scoring
import pytest
from aloai_scoring import constants as scoring
from services.session_agent import generation
from services.session_agent.events import SCHEMA_VERSIONS
from services.session_agent.machine import profiles as cfg


def test_event_versions_match_the_shared_map():
    # The Scorer and Grader validate what the agent publishes against these versions.
    assert SCHEMA_VERSIONS == {t: aloai_events.SCHEMA_VERSIONS[t] for t in SCHEMA_VERSIONS}


def test_the_told_word_wait_matches_the_scorers():
    # WCPM takes the wait for "That word is X." out of the reading time (PRD 6.1).
    assert cfg.TOLD_WORD_MS == scoring.TOLD_WAIT_S * 1000


@pytest.mark.parametrize("next_arl", [None, *range(1, 13)])
@pytest.mark.parametrize("primary_class", range(1, 7))
def test_the_starting_level_matches_the_scorers(primary_class, next_arl):
    # The agent's copy of PRD 6.7 must give the level aloai_scoring gives, in every month.
    for month in range(1, 13):
        today = date(2026, month, 1)
        child = {"primary_class": primary_class, "next_passage_arl": next_arl}
        expected = aloai_scoring.start_arl(primary_class, today, next_arl)
        assert generation.start_arl(child, today) == expected


@pytest.mark.parametrize(
    "child",
    [{"primary_class": 0}, {"primary_class": 7}, {"next_passage_arl": 0}, {"next_passage_arl": 13}],
)
def test_the_scorer_refuses_what_the_agent_answers_with_no_level(child):
    with pytest.raises(ValueError):
        aloai_scoring.start_arl(
            child.get("primary_class", 3), date(2026, 10, 1), child.get("next_passage_arl")
        )
    assert generation.start_arl(child, date(2026, 10, 1)) is None
