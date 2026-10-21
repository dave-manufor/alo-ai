"""Placing what a transcript heard against the passage (PRD 5.3)."""

import pytest
from services.reading_scorer.words import POLITE, STOP_PHRASES, Heard, Placed, align, normalize
from services.session_agent import intents

PASSAGE = ["ada", "saw", "a", "red", "hat"]


def heard(text: str) -> list[Heard]:
    return [Heard(word) for word in text.split()]


@pytest.mark.parametrize(
    "word, normalized",
    [
        ("Jàpá,", "japa"),
        ("Market.", "market"),
        ("we'll", "we'll"),
        ("we’ll", "we'll"),
        ("‘quoted’", "quoted"),
        ("'quoted'", "quoted"),
    ],
)
def test_words_match_without_case_accents_or_punctuation(word, normalized):
    assert normalize(word) == normalized


def test_an_exact_reading_places_every_word():
    placed = align(PASSAGE, heard("Ada saw a red hat."))
    assert [p.heard.text for p in placed] == ["Ada", "saw", "a", "red", "hat."]
    assert all(p.before == () for p in placed)


def test_a_misread_word_takes_the_place_of_the_passage_word():
    placed = align(PASSAGE, heard("ada sew a red hat"))
    assert placed[1] == Placed(Heard("sew"))


def test_a_skipped_word_has_nothing_in_its_place():
    placed = align(PASSAGE, heard("ada saw red hat"))
    assert placed[2] == Placed(None)


def test_an_added_word_is_kept_before_the_passage_word_it_precedes():
    placed = align(PASSAGE, heard("ada sow saw a red hat"))
    assert placed[1] == Placed(Heard("saw"), before=("sow",))


def test_words_added_after_the_last_passage_word_are_dropped():
    placed = align(PASSAGE, heard("ada saw a red hat the end"))
    assert placed[-1] == Placed(Heard("hat"))


def test_a_reading_that_stops_leaves_the_rest_unplaced():
    placed = align(PASSAGE, heard("ada saw"))
    assert [p.heard for p in placed[2:]] == [None, None, None]


def test_nothing_heard_places_nothing():
    assert align(PASSAGE, []) == [Placed(None)] * 5


def test_words_said_after_stopping_are_extra_words_not_misreadings():
    placed = align(PASSAGE, heard("ada saw done"))
    assert [p.heard for p in placed] == [Heard("ada"), Heard("saw"), None, None, None]
    assert placed[2].before == ("done",)


@pytest.mark.parametrize("said", ["ada saw a red hut", "ada saw a red cap"])
def test_a_misread_last_word_is_still_a_misreading(said):
    placed = align(PASSAGE, heard(said))
    assert placed[-1] == Placed(Heard(said.split()[-1]))


def test_words_said_up_to_the_end_stand_for_the_passage_words_left():
    placed = align(PASSAGE, heard("ada saw a big cap"))
    assert [p.heard.text for p in placed[3:]] == ["big", "cap"]


def test_a_word_nothing_like_the_passage_word_still_takes_its_place_mid_passage():
    placed = align(PASSAGE, heard("ada saw a big hat"))
    assert placed[3] == Placed(Heard("big"))


@pytest.mark.parametrize(
    "said, read",
    [
        ("ada saw a im done", 3),
        ("ada saw a red im done", 4),
        ("Ada saw a, I'm done, Auntie.", 3),
        ("ada saw a red please stop", 4),
        ("ada saw a red i want to stop", 4),
        ("ada saw a red auntie im done", 4),
        ("ada saw a red hat i am done", 5),
    ],
)
def test_saying_stop_at_the_end_is_not_reading_on(said, read):
    placed = align(PASSAGE, heard(said))
    assert [p.heard is not None for p in placed] == [True] * read + [False] * (5 - read)
    assert all(p.before == () for p in placed)


def test_saying_only_stop_places_nothing():
    assert align(PASSAGE, heard("I'm done")) == [Placed(None)] * 5


def test_a_passage_that_ends_in_a_stop_word_is_read_as_written():
    passage = ["the", "bus", "had", "to", "stop"]
    placed = align(passage, heard("the bus had to stop"))
    assert [p.heard.text for p in placed] == passage


def test_a_stop_phrase_partly_read_as_the_passage_stays_a_reading():
    placed = align(["she", "had", "no", "money"], heard("she had no more"))
    assert [p.heard.text for p in placed] == ["she", "had", "no", "more"]


def test_a_polite_word_read_as_the_passage_stays_when_the_stop_after_it_is_dropped():
    placed = align(["ada", "met", "auntie", "bola"], heard("ada met auntie im done"))
    assert [p.heard.text for p in placed[:3]] == ["ada", "met", "auntie"]
    assert placed[3] == Placed(None)


def test_the_stop_phrases_and_polite_words_are_the_session_agents():
    # The scorer image doesn't carry the Session Agent, so words.py keeps a copy.
    assert set(STOP_PHRASES) == set(intents.STOP_PHRASES)
    assert set(POLITE) == set(intents.POLITE)
