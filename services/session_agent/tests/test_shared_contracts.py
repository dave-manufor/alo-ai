"""The Session Agent's copies of values the after-session services also hold (libs/aloai).

The agent keeps its own event versions and told-word wait, so its image needs neither
libs/aloai nor schemas/ at run time. These tests make the two sides change together.
"""

import aloai_events
from aloai_scoring import constants as scoring
from services.session_agent.events import SCHEMA_VERSIONS
from services.session_agent.machine import profiles as cfg


def test_event_versions_match_the_shared_map():
    # The Scorer and Grader validate what the agent publishes against these versions.
    assert SCHEMA_VERSIONS == {t: aloai_events.SCHEMA_VERSIONS[t] for t in SCHEMA_VERSIONS}


def test_the_told_word_wait_matches_the_scorers():
    # WCPM takes the wait for "That word is X." out of the reading time (PRD 6.1).
    assert cfg.TOLD_WORD_MS == scoring.TOLD_WAIT_S * 1000
