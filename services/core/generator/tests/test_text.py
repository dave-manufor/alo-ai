"""Word handling, and parity with the Session Agent's clip keys (PRD 4.5 G5)."""

import pytest
from services.core.generator.text import HOMOGRAPHS, clean_word, split_edges, words_of
from services.session_agent.clips import keys

SAMPLES = [
    "Jàpá,",
    "Japa",
    "we'll",
    "we’ll",
    "‘Hello’",
    '"Come',
    "market.",
    "hat!",
    "don’t",
    "—",
    "",
    "'quoted'",
    "Ünï-cödé",
    "ADA",
    "3rd",
]


@pytest.mark.parametrize("text", SAMPLES)
def test_clean_word_is_the_clip_stores_rule(text):
    assert clean_word(text) == keys.clean_word(text)


def test_the_homographs_are_the_clip_stores():
    assert HOMOGRAPHS == keys.HOMOGRAPHS


def test_accents_stay_so_japa_and_japa_with_accents_are_different_words():
    assert clean_word("Jàpá") == "jàpá" != clean_word("Japa")


@pytest.mark.parametrize(
    ("token", "edges"),
    [
        ("market.", ("", "market", ".")),
        ('"Come', ('"', "Come", "")),
        ('here,"', ("", "here", ',"')),
        ("don't", ("", "don't", "")),
        ("—", ("—", "", "")),  # no word at all: the whole token is "leading"
        ("(hat)", ("(", "hat", ")")),
    ],
)
def test_split_edges(token, edges):
    assert split_edges(token) == edges


def test_words_of_skips_tokens_with_no_letters():
    assert words_of(["Ada ran — fast.", "He   left!"]) == ["ada", "ran", "fast", "he", "left"]
