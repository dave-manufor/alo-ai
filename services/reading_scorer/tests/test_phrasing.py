"""Prosody phrasing from pauses, word times and boundaries (PRD 5.5)."""

from services.reading_scorer.labels import WordLabel
from services.reading_scorer.phrasing import phrasing

# Two eligible sentences: "Ada and Mama went home." / "They ate rice and beans."
TEXTS = ["Ada", "and", "Mama", "went", "home.", "They", "ate", "rice", "and", "beans."]
BOUNDARIES = [
    "NONE",
    "NONE",
    "NONE",
    "NONE",
    "TERMINAL",
    "NONE",
    "NONE",
    "PHRASE",
    "NONE",
    "TERMINAL",
]
TOKENS = [
    {"text": text, "sentence_index": 0 if index < 5 else 1, "syntactic_boundary_after": boundary}
    for index, (text, boundary) in enumerate(zip(TEXTS, BOUNDARIES))
]
WORDS = len(TOKENS)
TIMES = [(1000 * index, 1000 * index + 600) for index in range(WORDS)]


def labels(errors=(), count=WORDS) -> list[WordLabel]:
    return [
        WordLabel(
            i, TEXTS[i].lower(), None, None, "SUBSTITUTION" if i in errors else "CORRECT", False
        )
        for i in range(count)
    ]


def pause_after(index: int, length: int = 300) -> tuple[int, int]:
    start = TIMES[index][1] + 50
    return start, start + length


def score(pauses, errors=(), accuracy=96.0, count=WORDS):
    return phrasing(TOKENS, labels(errors, count), TIMES[:count], pauses, accuracy)


def test_no_pauses_inside_phrases_is_full_phrasing():
    result = score([pause_after(4), pause_after(7)])
    assert (result.reported, result.pause_intrusion_rate, result.phrasing) == (True, 0.0, 100)


def test_a_pause_inside_a_phrase_intrudes():
    result = score([pause_after(1)])
    assert (result.pause_intrusion_rate, result.phrasing) == (0.333, 0)


def test_a_pause_next_to_a_misread_word_is_a_decoding_pause():
    assert score([pause_after(1)], errors=[2]).phrasing == 100


def test_a_pause_shorter_than_180_ms_is_not_a_pause():
    assert score([pause_after(1, length=150)]).phrasing == 100


def test_a_pause_inside_a_word_is_not_a_phrasing_pause():
    assert score([(TIMES[1][0] + 100, TIMES[1][0] + 400)]).phrasing == 100


def test_a_sentence_with_two_errors_is_left_out():
    result = score([pause_after(1)], errors=[3, 4])
    assert result.reported is False


def test_a_sentence_not_read_to_the_end_is_left_out():
    assert score([], count=8).reported is False


def test_phrasing_needs_90_percent_accuracy():
    assert score([], accuracy=89.0).reported is False
