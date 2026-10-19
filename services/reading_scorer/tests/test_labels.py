"""Word labels from two transcripts (PRD 5.3): a word counts only where both agree."""

import pytest
from services.reading_scorer.labels import label_words
from services.reading_scorer.words import Heard, Placed

TARGETS = ["ada", "saw", "a", "red", "hat"]


def placed(*words, before=()) -> list[Placed]:
    """One Placed per passage word; None for a skipped word, (word, confidence) to set it."""
    result = []
    for index, word in enumerate(words):
        if word is None:
            result.append(Placed(None))
            continue
        text, confidence = word if isinstance(word, tuple) else (word, 0.95)
        result.append(Placed(Heard(text, confidence), before if index == 1 else ()))
    return result


def labels_of(chirp, gemini, told=()):
    return [label.label for label in label_words(TARGETS, chirp, gemini, set(told))]


ALL_RIGHT = placed("ada", "saw", "a", "red", "hat")


def test_both_right_is_correct():
    assert labels_of(ALL_RIGHT, ALL_RIGHT) == ["CORRECT"] * 5


def test_both_right_but_chirp_unsure_is_uncertain():
    unsure = placed("ada", ("saw", 0.49), "a", "red", "hat")
    assert labels_of(unsure, ALL_RIGHT)[1] == "UNCERTAIN"


def test_the_same_other_word_is_a_substitution():
    misread = placed("ada", "sew", "a", "red", "hat")
    assert labels_of(misread, misread)[1] == "SUBSTITUTION"


def test_both_skipping_it_is_an_omission():
    skipped = placed("ada", None, "a", "red", "hat")
    assert labels_of(skipped, skipped)[1] == "OMISSION"


@pytest.mark.parametrize(
    "chirp, gemini",
    [
        (placed("ada", "sew", "a", "red", "hat"), ALL_RIGHT),
        (placed("ada", "sew", "a", "red", "hat"), placed("ada", "sow", "a", "red", "hat")),
        (placed("ada", None, "a", "red", "hat"), placed("ada", "sew", "a", "red", "hat")),
    ],
)
def test_any_disagreement_is_uncertain(chirp, gemini):
    assert labels_of(chirp, gemini)[1] == "UNCERTAIN"


def test_a_told_word_is_told_whatever_was_heard():
    assert labels_of(ALL_RIGHT, ALL_RIGHT, told=[1])[1] == "TOLD"


def test_a_near_miss_just_before_the_right_word_is_a_self_correction():
    corrected = placed("ada", "saw", "a", "red", "hat", before=("sow",))
    [_, saw, *_] = label_words(TARGETS, corrected, corrected, set())
    assert (saw.label, saw.is_self_corrected) == ("CORRECT", True)


@pytest.mark.parametrize("before", [("saw",), ("elephant",), ()])
def test_a_repeat_or_an_unrelated_word_is_not_a_self_correction(before):
    heard = placed("ada", "saw", "a", "red", "hat", before=before)
    assert not label_words(TARGETS, heard, heard, set())[1].is_self_corrected


def test_both_transcripts_must_hear_the_correction():
    corrected = placed("ada", "saw", "a", "red", "hat", before=("sow",))
    assert not label_words(TARGETS, corrected, ALL_RIGHT, set())[1].is_self_corrected


def test_words_after_the_last_one_reached_were_not_attempted():
    stopped = placed("ada", "saw", None, None, None)
    assert labels_of(stopped, stopped) == ["CORRECT", "CORRECT"]


def test_a_reading_with_nothing_reached_has_no_labels():
    silent = placed(None, None, None, None, None)
    assert labels_of(silent, silent) == []
