"""Fluency and word reading (PRD 6.1, 6.2)."""

from dataclasses import dataclass

from .constants import (
    ACCURACY_CUT,
    HIGH_UNCERTAINTY_SHARE,
    NORM_TOLD_WAIT_S,
    READING_CAP_S,
    SHORT_READING_S,
    TOLD_WAIT_S,
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
    told_waits: int,
    mispronunciations: int,
    self_corrections: int,
    uncertain: int,
) -> Fluency:
    """PRD 6.1. UNCERTAIN words (the two transcripts disagree, PRD 5.3) are left out of
    both the words scored and the errors, so they count neither for nor against the child.

    told_waits: the told words whose wait fell inside the reading time (all but a told
    first word). WCPM leaves out the part of each wait beyond the norms' 3 s, so it stays
    comparable with WCPM_CUT; reading_seconds stays as measured. Waits that cannot fit in
    the reading time are refused.

    The values are exact, so the cuts compare the true numbers; the report rounds them
    for display."""
    counts = (
        words_attempted,
        substitutions,
        omissions,
        told,
        told_waits,
        mispronunciations,
        self_corrections,
        uncertain,
    )
    if min(counts) < 0 or reading_seconds < 0:
        raise ValueError("counts and reading_seconds must not be negative")
    if told_waits > told:
        raise ValueError("more told waits than told words")
    errors = substitutions + omissions + told + mispronunciations
    scored = words_attempted - uncertain
    if errors > scored:
        raise ValueError("more errors and uncertain words than words attempted")

    seconds = min(reading_seconds, READING_CAP_S)
    if told_waits * TOLD_WAIT_S > seconds:
        raise ValueError(f"{told_waits} told waits of {TOLD_WAIT_S} s cannot fit in {seconds} s")
    wcpm_seconds = seconds - told_waits * (TOLD_WAIT_S - NORM_TOLD_WAIT_S)
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
        accuracy_pct=100 * correct / scored if scored else None,
        wcpm=60 * correct / wcpm_seconds if scored and wcpm_seconds else None,
        self_correction_ratio=(
            self_corrections / (self_corrections + misreads)
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
