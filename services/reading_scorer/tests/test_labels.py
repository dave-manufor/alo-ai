"""Word labels from two transcripts (PRD 5.3): a word counts only where both agree."""

import pytest
from services.reading_scorer.labels import label_words
from services.reading_scorer.words import Heard, Placed, align

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


# ---- one transcript (SECOND_TRANSCRIPT=off): W3's single rule


def single(chirp, told=()):
    return label_words(TARGETS, chirp, None, set(told))


def single_labels(chirp, told=()):
    return [label.label for label in single(chirp, told)]


def test_one_transcript_labels_a_right_word_correct_and_a_different_one_a_substitution():
    assert single_labels(ALL_RIGHT) == ["CORRECT"] * 5
    assert single_labels(placed("ada", "sew", "a", "red", "hat"))[1] == "SUBSTITUTION"


@pytest.mark.parametrize("heard", ["saw", "sew"])
def test_one_transcript_leaves_out_a_word_it_was_unsure_of_right_or_wrong(heard):
    unsure = placed("ada", (heard, 0.3), "a", "red", "hat")
    assert single_labels(unsure)[1] == "UNCERTAIN"


def test_one_transcript_counts_a_misreading_only_when_it_is_sure_of_it():
    assert single_labels(placed("ada", ("sew", 0.8), "a", "red", "hat"))[1] == "SUBSTITUTION"
    assert single_labels(placed("ada", ("sew", 0.79), "a", "red", "hat"))[1] == "UNCERTAIN"


def test_one_transcript_counts_a_right_word_it_was_fairly_sure_of():
    assert single_labels(placed("ada", ("saw", 0.6), "a", "red", "hat"))[1] == "CORRECT"


def test_one_transcript_leaves_out_a_word_it_gives_no_confidence_for():
    some_missing = placed("ada", ("sew", None), ("a", None), "red", "hat")
    assert single_labels(some_missing)[1:3] == ["UNCERTAIN", "UNCERTAIN"]


def test_one_transcript_without_any_confidence_scores_nothing():
    """Not even a told word or an omission: with no word scored, accuracy stays empty
    instead of showing only the errors."""
    none = placed(("ada", None), None, ("a", None), ("red", None), None)
    labels = single(none, told=[2])
    assert [label.label for label in labels] == ["UNCERTAIN"] * 4
    assert not any(label.is_self_corrected for label in labels)


def test_one_transcript_nothing_heard_is_an_omission_and_a_told_word_is_told():
    assert single_labels(placed("ada", None, "a", "red", "hat"))[1] == "OMISSION"
    assert single_labels(ALL_RIGHT, told=[1])[1] == "TOLD"


def test_one_transcript_keeps_no_second_hearing_and_can_see_a_self_correction():
    corrected = placed("ada", "saw", "a", "red", "hat", before=("sow",))
    [_, saw, *_] = single(corrected)
    assert (saw.label, saw.is_self_corrected, saw.gemini) == ("CORRECT", True, None)
    assert not single(placed("ada", ("saw", 0.2), "a", "red", "hat", before=("sow",)))[
        1
    ].is_self_corrected


def test_one_transcript_still_stops_at_the_last_word_reached():
    stopped = placed("ada", "saw", None, None, None)
    assert single_labels(stopped) == ["CORRECT", "CORRECT"]


def test_words_after_the_last_one_reached_were_not_attempted():
    stopped = placed("ada", "saw", None, None, None)
    assert labels_of(stopped, stopped) == ["CORRECT", "CORRECT"]


def test_a_reading_with_nothing_reached_has_no_labels():
    silent = placed(None, None, None, None, None)
    assert labels_of(silent, silent) == []


@pytest.mark.parametrize(
    "said, labels",
    [
        ("ada saw done", ["CORRECT", "CORRECT"]),
        ("ada saw", ["CORRECT", "CORRECT"]),
        ("ada saw a red cap", ["CORRECT"] * 4 + ["SUBSTITUTION"]),
        ("ada saw a big cap", ["CORRECT"] * 3 + ["SUBSTITUTION"] * 2),
        ("ada saw a red cat", ["CORRECT"] * 4 + ["SUBSTITUTION"]),
    ],
    ids=["stopped, then said a word", "stopped", "unlike last word", "two unlike", "near miss"],
)
def test_a_reading_that_stops_drops_the_rest_but_one_read_to_the_end_keeps_its_errors(said, labels):
    passage = ["ada", "saw", "a", "red", "hat"]
    heard = [Heard(word, 0.9) for word in said.split()]
    found = label_words(passage, align(passage, heard), align(passage, heard), told=set())
    assert [label.label for label in found] == labels
