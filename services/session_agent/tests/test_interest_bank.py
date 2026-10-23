"""A session reads a story about what the child likes: the interest matched to the bank."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aloai_store import MemoryStore
from services.session_agent import generation
from services.session_agent.livekit_worker import _interest_picker, _Passages
from services.session_agent.machine.profiles import DEMO, STANDARD
from services.session_agent.passages import (
    INTEREST_BANK,
    MAX_LEVEL_GAP,
    folder_bank,
    passage_id_for_interest,
)

CONTRACTS = Path(__file__).resolve().parents[3] / "fixtures" / "contracts"
DEFAULT = "bank_p3_school_garden"


def test_the_interest_index_is_the_standard_read_passages_in_the_bank():
    found = {}
    for path in sorted(CONTRACTS.glob("passage.*.json")):
        passage = json.loads(path.read_text())
        if passage["mode"] == "READ" and passage["length_profile"] == "STANDARD":
            found[passage["passage_id"]] = (passage["arl_level"], tuple(passage["topic_tags"]))
    assert INTEREST_BANK == found


def test_every_indexed_passage_loads_as_a_fitting_pair():
    bank = folder_bank(CONTRACTS)
    for passage_id in INTEREST_BANK:
        pair = bank.pair(passage_id, STANDARD)
        assert len(pair.read["items"]) == STANDARD.n_questions
        assert len(pair.listening["items"]) == STANDARD.n_listening_items


@pytest.mark.parametrize(
    ("level", "tags", "expected"),
    [
        (5, ["football"], "bank_p3_cup_day"),  # at their own level, not the one two down
        (9, ["music"], "bank_p5_music_contest"),
        (3, ["food"], "bank_p2_cooking_rice"),
        (6, ["animals"], "bank_p3_hen_and_chicks"),
        (7, ["space"], "bank_p4_night_sky"),
        (11, ["space", "adventure"], "bank_p6_science_fair_rocket"),
    ],
)
def test_a_child_gets_the_story_that_matches_what_they_like(level, tags, expected):
    assert passage_id_for_interest(level, tags, DEFAULT) == expected


def test_the_first_tag_counts_double_and_a_second_tag_can_win_alone():
    # Level 4: farming is the second tag, so one point; football is the first, so two.
    assert passage_id_for_interest(4, ["football", "farming"], DEFAULT) == "bank_p2_lost_ball"
    # Farming first: goat story (3, one away) scores 2, the same as the hen's (5), and is easier.
    assert passage_id_for_interest(4, ["farming", "football"], DEFAULT) == "bank_p2_goat_at_gate"
    # A second tag wins alone when the first has nothing within reach.
    assert passage_id_for_interest(4, ["space", "football"], DEFAULT) == "bank_p2_lost_ball"


def test_nothing_that_matches_within_two_levels_means_the_levels_own_passage():
    # No space story within two levels of level 1: the child's own level's passage.
    assert passage_id_for_interest(1, ["space"], "bank_p1_ada_and_the_dog") == (
        "bank_p1_ada_and_the_dog"
    )
    # Every story is at least a level... a story more than two levels away is never chosen.
    for level in range(1, 13):
        picked = passage_id_for_interest(level, ["football", "animals", "space"], DEFAULT)
        if picked != DEFAULT:
            assert abs(INTEREST_BANK[picked][0] - level) <= MAX_LEVEL_GAP


def test_no_tags_or_no_known_level_means_the_default():
    assert passage_id_for_interest(5, [], DEFAULT) == DEFAULT
    assert passage_id_for_interest(None, ["football"], DEFAULT) == DEFAULT


def test_a_tie_goes_to_the_nearer_level_then_the_easier():
    # family within reach of level 4: lost ball and cooking rice, both level 3: by id
    assert passage_id_for_interest(4, ["family"], DEFAULT) == "bank_p2_cooking_rice"
    # level 2, animals: ada and the dog (1) and the goat story (3) are both one away: the easier
    assert passage_id_for_interest(2, ["animals"], DEFAULT) == "bank_p1_ada_and_the_dog"


# ---- _Passages


class _Driver:
    def __init__(self):
        self.arrived = []

    def passage_arrived(self, pair, *, fallback):
        self.arrived.append((pair.read["passage_id"], fallback))


BANK = folder_bank(CONTRACTS)


def _arrives(requester, pick, interest="i like football", level_default="bank_p3_school_garden"):
    async def main():
        passages = _Passages(BANK, level_default, STANDARD, requester, pick)
        passages.driver = _Driver()
        passages.generate(interest, 20_000)
        await asyncio.gather(*passages._calls)
        return passages.driver.arrived

    return asyncio.run(main())


def test_with_no_generator_the_story_is_the_one_that_matches_the_interest():
    async def pick(answer):
        return "bank_p2_lost_ball"

    assert _arrives(None, pick) == [("bank_p2_lost_ball", True)]


def test_when_the_generator_gives_no_story_the_interest_still_picks_the_bank_passage():
    class Requester:
        client = None

        async def request(self, interest, deadline_ms):
            return None

    async def pick(answer):
        return "bank_p2_lost_ball"

    assert _arrives(Requester(), pick) == [("bank_p2_lost_ball", True)]


def test_a_failing_match_or_an_unusable_passage_falls_back_to_the_levels_passage():
    async def broken(answer):
        raise TimeoutError("the tagger took too long")

    async def unusable(answer):
        return "no_such_passage"

    assert _arrives(None, broken) == [("bank_p3_school_garden", True)]
    assert _arrives(None, unusable) == [("bank_p3_school_garden", True)]


def test_a_child_who_said_nothing_gets_the_levels_passage_without_asking_the_tagger():
    async def pick(answer):
        raise AssertionError("not asked")

    assert _arrives(None, pick, interest=None) == [("bank_p3_school_garden", True)]


# ---- the picker the worker builds


def _config(**changes):
    values = {"ai_mode": "live", "interest_chat": True}
    return SimpleNamespace(**{**values, **changes})


def test_there_is_no_picker_in_fixtures_mode_without_the_chat_or_for_the_demo_profile():
    start = SimpleNamespace(child_id="child_1")
    for cfg, profile in (
        (_config(ai_mode="fixtures"), STANDARD),
        (_config(interest_chat=False), STANDARD),
        (_config(), DEMO),
    ):
        assert _interest_picker(None, cfg, start, profile, DEFAULT, MemoryStore({}), None) is None


def test_the_picker_tags_the_answer_and_matches_it_at_the_childs_level(monkeypatch):
    from services.session_agent import livekit_worker

    class Tagger:
        async def tag(self, answer):
            assert answer == "i like football"
            return generation.Interest(("football",))

    monkeypatch.setattr(livekit_worker, "_tagger", lambda settings, shared: Tagger())
    store = MemoryStore({"children/child_1": {"primary_class": 3, "next_passage_arl": 5}})
    start = SimpleNamespace(child_id="child_1")
    pick = _interest_picker(None, _config(), start, STANDARD, DEFAULT, store, None)
    assert asyncio.run(pick("i like football")) == "bank_p3_cup_day"
    # a child record that gives no level: the default for them
    pick = _interest_picker(None, _config(), start, STANDARD, DEFAULT, MemoryStore({}), None)
    assert asyncio.run(pick("i like football")) == DEFAULT
