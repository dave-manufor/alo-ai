"""The Alo Reading Level and the book band (PRD 6.7, 8)."""

from dataclasses import dataclass
from datetime import date

from .constants import (
    ACCURACY_BANDS,
    ARL_MIN,
    BAND_ORDER,
    BOOK_BAND_OFFSETS,
    NEXT_OFFSET,
    RC_BANDS,
    REPORTED_OFFSET,
    TERM_1_MONTHS,
    Band,
    ProfileCode,
    check_arl,
    check_class,
    clamp_arl,
)


@dataclass(frozen=True)
class ReportedLevel:
    arl: int
    at_least: bool


def performance_band(
    accuracy_pct: float | None, rc: float | None, *, reading_stopped_early: bool = False
) -> Band | None:
    """The lower of the accuracy and RC bands. A reading stopped by the kindness rule is
    FRUSTRATION, which sets the next passage two levels lower (PRD 4.3). None when either
    measure is missing."""
    if reading_stopped_early:
        return "FRUSTRATION"
    if accuracy_pct is None or rc is None:
        return None
    return min(_band(accuracy_pct, ACCURACY_BANDS), _band(rc, RC_BANDS), key=BAND_ORDER.index)


def _band(value: float, cuts: tuple[tuple[float, Band], ...]) -> Band:
    for cut, band in cuts:
        if value >= cut:
            return band
    return "FRUSTRATION"


def reported_level(passage_arl: int, band: Band | None) -> ReportedLevel | None:
    """INDEPENDENT is shown as "ARL n or above" (at_least)."""
    check_arl(passage_arl)
    if band is None:
        return None
    arl = max(ARL_MIN, passage_arl + REPORTED_OFFSET[band])
    return ReportedLevel(arl=arl, at_least=band == "INDEPENDENT")


def next_passage_level(passage_arl: int, band: Band | None) -> int:
    """With no band the next session retests at the same level."""
    check_arl(passage_arl)
    if band is None:
        return passage_arl
    return clamp_arl(passage_arl + NEXT_OFFSET[band])


def level_confirmed(previous_arl: int | None, reported_arl: int) -> bool:
    """Confirmed once two consecutive sessions agree within one level."""
    return previous_arl is not None and abs(reported_arl - previous_arl) <= 1


def approx_primary_class(arl: int) -> int:
    """ARL 1-2 is about Primary 1, up to ARL 11-12 about Primary 6. Approximate, not normed."""
    check_arl(arl)
    return (arl + 1) // 2


def start_arl(primary_class: int, on: date, previous_next_arl: int | None = None) -> int:
    """A returning child starts at their last next_passage_arl. A first session starts at
    2 x class - 1 in term 1 and 2 x class in terms 2 and 3."""
    check_class(primary_class)
    if previous_next_arl is not None:
        check_arl(previous_next_arl)
        return previous_next_arl
    return 2 * primary_class - (1 if on.month in TERM_1_MONTHS else 0)


def book_band(profile: ProfileCode, reported_arl: int | None) -> tuple[int, int] | None:
    """The ARL range books are recommended from, around L = reported_arl. None for
    INSUFFICIENT_EVIDENCE or without a reported level."""
    if profile not in BOOK_BAND_OFFSETS or reported_arl is None:
        return None
    check_arl(reported_arl)
    low, high = BOOK_BAND_OFFSETS[profile]
    return clamp_arl(reported_arl + low), clamp_arl(reported_arl + high)
