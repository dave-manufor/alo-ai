"""Fluency and word reading (PRD 6.1, 6.2)."""

from dataclasses import dataclass

from .constants import (
    ACCURACY_CUT,
    HIGH_UNCERTAINTY_SHARE,
    READING_CAP_S,
    SHORT_READING_S,
    WCPM_CUT,
    check_class,
)


@dataclass(frozen=True)
class Fluency:
    words_attempted: int
    words_correct: int
    reading_seconds: float
    accuracy_pct: float | None
    wcpm: float | None
    self_correction_ratio: float | None
    flags: tuple[str, ...]


def fluency(
    *,
    words_attempted: int,
    reading_seconds: float,
    substitutions: int,
    omissions: int,
    told: int,
    mispronunciations: int,
    self_corrections: int,
    uncertain: int,
) -> Fluency:
    """PRD 6.1. UNCERTAIN words (the two transcripts disagree, PRD 5.3) are left out of
    both the words scored and the errors, so they count neither for nor against the child."""
    counts = (
        words_attempted,
        substitutions,
        omissions,
        told,
        mispronunciations,
        self_corrections,
        uncertain,
    )
    if min(counts) < 0 or reading_seconds < 0:
        raise ValueError("counts and reading_seconds must not be negative")
    errors = substitutions + omissions + told + mispronunciations
    scored = words_attempted - uncertain
    if errors > scored:
        raise ValueError("more errors and uncertain words than words attempted")

    seconds = min(reading_seconds, READING_CAP_S)
    correct = scored - errors
    misreads = substitutions + omissions + mispronunciations
    flags = []
    if seconds < SHORT_READING_S:
        flags.append("SHORT_READING")
    if words_attempted and uncertain / words_attempted > HIGH_UNCERTAINTY_SHARE:
        flags.append("HIGH_UNCERTAINTY")
    return Fluency(
        words_attempted=words_attempted,
        words_correct=correct,
        reading_seconds=seconds,
        accuracy_pct=round(100 * correct / scored, 1) if scored else None,
        wcpm=round(60 * correct / seconds, 1) if scored and seconds else None,
        self_correction_ratio=(
            round(self_corrections / (self_corrections + misreads), 2)
            if self_corrections + misreads
            else None
        ),
        flags=tuple(flags),
    )


def word_reading_ok(
    accuracy_pct: float | None, wcpm: float | None, primary_class: int
) -> bool | None:
    """D_ok in PRD 6.2. None when the reading gave no usable accuracy or WCPM."""
    check_class(primary_class)
    if accuracy_pct is None or wcpm is None:
        return None
    return accuracy_pct >= ACCURACY_CUT and wcpm >= WCPM_CUT[primary_class]
