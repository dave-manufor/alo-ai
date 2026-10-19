"""Tests for prosody phrasing in aloai_scoring (PRD 5.5).

Chidi's worked session is the acceptance example: 4 intrusive pauses in 26 phrases.
"""

import aloai_scoring as scoring
import pytest
from aloai_scoring import Prosody


def test_chidi_phrasing_matches_the_worked_session():
    result = scoring.prosody(
        accuracy_pct=97.7, eligible_sentences=14, intrusive_pauses=4, chunks=26
    )
    assert result == Prosody(
        reported=True, pause_intrusion_rate=0.154, phrasing=38, expression=None, overall=38
    )


@pytest.mark.parametrize("intrusive, phrasing", [(0, 100), (5, 50), (10, 0), (20, 0)])
def test_phrasing_falls_to_zero_at_a_quarter_of_the_chunks(intrusive, phrasing):
    result = scoring.prosody(
        accuracy_pct=95.0, eligible_sentences=3, intrusive_pauses=intrusive, chunks=40
    )
    assert result.phrasing == phrasing


@pytest.mark.parametrize(
    "accuracy, sentences, chunks",
    [(89.9, 3, 10), (None, 3, 10), (95.0, 1, 10), (95.0, 3, 0)],
)
def test_phrasing_needs_90_percent_accuracy_two_eligible_sentences_and_a_chunk(
    accuracy, sentences, chunks
):
    result = scoring.prosody(
        accuracy_pct=accuracy, eligible_sentences=sentences, intrusive_pauses=1, chunks=chunks
    )
    assert result == Prosody(reported=False)


@pytest.mark.parametrize(
    "words, errors, declarative, eligible",
    [
        (5, 0, True, True),
        (5, 1, True, True),
        (4, 0, True, False),
        (6, 2, True, False),
        (8, 0, False, False),
    ],
)
def test_an_eligible_sentence_is_declarative_with_5_words_and_under_2_errors(
    words, errors, declarative, eligible
):
    assert (
        scoring.sentence_eligible(words=words, errors=errors, declarative=declarative) is eligible
    )


def test_the_pause_length_is_180_ms():
    assert scoring.PAUSE_MS == 180
