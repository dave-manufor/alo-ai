"""Prosody phrasing (PRD 5.5). Display-only: it never feeds comprehension, level or profile.

Expression stays off until a Nigerian English reference voice exists (PRD 4.6), so the
overall prosody score is the phrasing score.
"""

from dataclasses import dataclass

from .constants import (
    ELIGIBLE_MAX_ERRORS,
    ELIGIBLE_MIN_WORDS,
    PHRASING_FULL_INTRUSION,
    PROSODY_MIN_ACCURACY,
    PROSODY_MIN_SENTENCES,
)


@dataclass(frozen=True)
class Prosody:
    reported: bool
    pause_intrusion_rate: float | None = None
    f0_word_corr: float | None = None
    phrasing: float | None = None
    expression: float | None = None
    overall: float | None = None


def sentence_eligible(*, words: int, errors: int, declarative: bool) -> bool:
    return declarative and words >= ELIGIBLE_MIN_WORDS and errors <= ELIGIBLE_MAX_ERRORS


def prosody(
    *, accuracy_pct: float | None, eligible_sentences: int, intrusive_pauses: int, chunks: int
) -> Prosody:
    """P_intrusion is the intrusive pauses (not at a phrase, clause or sentence boundary,
    and not next to an error or told word) over the syntactic chunks read. Phrasing is
    reported only at 90% accuracy or more, over at least 2 eligible sentences."""
    if (
        accuracy_pct is None
        or accuracy_pct < PROSODY_MIN_ACCURACY
        or eligible_sentences < PROSODY_MIN_SENTENCES
        or chunks == 0
    ):
        return Prosody(reported=False)
    rate = intrusive_pauses / chunks
    phrasing = round(100 * (1 - min(1, rate / PHRASING_FULL_INTRUSION)))
    return Prosody(
        reported=True, pause_intrusion_rate=round(rate, 3), phrasing=phrasing, overall=phrasing
    )
