import asyncio
from pathlib import Path

import pytest
from aloai_store import MemoryStore
from services.session_agent.livekit_worker import _bank_by_level
from services.session_agent.machine.profiles import STANDARD
from services.session_agent.passages import (
    DEFAULT_BANK,
    STANDARD_BANK,
    folder_bank,
    passage_id_for_level,
)

CONTRACTS = Path(__file__).resolve().parents[3] / "fixtures" / "contracts"
LISTEN_WORDS_MAX = 120  # PRD 4.1: a standard listening story is 80 to 120 words


# ---- the level to the passage


@pytest.mark.parametrize(
    ("level", "passage_id"),
    [
        (1, "bank_p1_ada_and_the_dog"),
        (2, "bank_p1_ada_and_the_dog"),  # between two: the easier
        (3, "bank_p2_lost_ball"),
        (4, "bank_p2_lost_ball"),
        (5, "bank_p3_school_garden"),
        (6, "bank_p3_school_garden"),
        (7, "bank_p4_night_bus"),
        (8, "bank_p4_night_bus"),
        (9, "bank_p5_music_contest"),
        (10, "bank_p5_music_contest"),
        (11, "bank_p6_river_crossing"),
        (12, "bank_p6_river_crossing"),
    ],
)
def test_the_standard_profile_gets_the_passage_nearest_the_level(level, passage_id):
    assert passage_id_for_level("standard", level) == passage_id


def test_an_unknown_level_gets_the_profiles_default():
    assert passage_id_for_level("standard", None) == DEFAULT_BANK["standard"]


def test_the_demo_profile_has_one_passage_whatever_the_level():
    assert passage_id_for_level("demo", 9) == DEFAULT_BANK["demo"]
    assert passage_id_for_level("demo", None) == DEFAULT_BANK["demo"]


# ---- the bank itself


@pytest.mark.parametrize(("arl", "passage_id"), sorted(STANDARD_BANK.items()))
def test_each_standard_passage_loads_as_a_fitting_pair_at_its_level(arl, passage_id):
    pair = folder_bank(CONTRACTS).pair(passage_id, STANDARD)
    assert pair.read["arl_level"] == arl
    assert len(pair.read["items"]) == STANDARD.n_questions
    assert len(pair.listening["items"]) == STANDARD.n_listening_items
    assert pair.listening["word_count"] <= LISTEN_WORDS_MAX
    assert abs(pair.listening["arl_level"] - arl) <= 4  # never a story far from the reading


def test_the_easiest_readers_hear_an_easier_story_than_the_oldest():
    bank = folder_bank(CONTRACTS)
    easy = bank.pair(STANDARD_BANK[1], STANDARD).listening["arl_level"]
    hard = bank.pair(STANDARD_BANK[9], STANDARD).listening["arl_level"]
    assert easy < hard


# ---- the child's record


def pick(docs: dict, profile: str = "standard", child_id: str = "child_a") -> str:
    return asyncio.run(_bank_by_level(MemoryStore(docs), child_id, profile))


@pytest.mark.parametrize(
    ("primary_class", "passage_id"),
    [
        (1, "bank_p1_ada_and_the_dog"),
        (2, "bank_p2_lost_ball"),
        (3, "bank_p3_school_garden"),
        (4, "bank_p4_night_bus"),
        (5, "bank_p5_music_contest"),
        (6, "bank_p6_river_crossing"),
    ],
)
def test_a_first_session_gets_the_passage_for_the_childs_class(primary_class, passage_id):
    # Term 1 starts at 2 x class - 1 and terms 2 and 3 at 2 x class; either way the same
    # passage is nearest, so this holds in any month.
    assert pick({"children/child_a": {"primary_class": primary_class}}) == passage_id


def test_a_returning_child_gets_the_level_the_last_report_set():
    child = {"primary_class": 1, "next_passage_arl": 7}
    assert pick({"children/child_a": child}) == "bank_p4_night_bus"


def test_a_missing_or_broken_record_gets_the_default():
    assert pick({}) == DEFAULT_BANK["standard"]
    assert pick({"children/child_a": {"primary_class": 9}}) == DEFAULT_BANK["standard"]


def test_a_record_that_cannot_be_read_does_not_end_the_session():
    class Broken(MemoryStore):
        def get(self, path):
            raise ConnectionError("store unreachable")

    picked = asyncio.run(_bank_by_level(Broken(), "child_a", "standard"))
    assert picked == DEFAULT_BANK["standard"]
