"""Every score, band, level and profile in Alo.ai (PRD 6).

Pure functions: no I/O, no clock, no randomness and no model calls. The Reading
Scorer, the quick endpoint and final grading all call these, so a number means the
same thing wherever it appears. Models supply only proposition credits and item
points (PRD 7); everything else is computed here.

Constants marked [CAL] are provisional and are recalibrated on pilot data (PRD 13.2).
Changing one needs W3's approval, a new SCORING_MODULE, a validation rerun and a PRD
changelog line (alo-scoring-change).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

SCORING_MODULE = "1.0.0"

Band = Literal["INDEPENDENT", "INSTRUCTIONAL", "SUPPORTED", "FRUSTRATION"]
ProfileCode = Literal[
    "ON_TRACK",
    "UNDERSTANDS_BUILDING_WORD_READING",
    "DECODING_LIMITED",
    "FLUENT_NEEDS_LANGUAGE_SUPPORT",
    "NEEDS_SUPPORT_IN_BOTH",
    "COMPREHENSION_STRATEGY_GAP",
    "INSUFFICIENT_EVIDENCE",
]

ARL_MIN, ARL_MAX = 1, 12
PRIMARY_CLASSES = range(1, 7)

READING_CAP_S = 90
SHORT_READING_S = 60
HIGH_UNCERTAINTY_SHARE = 0.05

ACCURACY_CUT = 95  # [CAL] PRD 6.2
WCPM_CUT = {1: 34, 2: 59, 3: 79, 4: 95, 5: 109, 6: 109}  # [CAL] PRD 6.2, US norms until local ones

RETELL_FULL_COVERAGE = 0.60  # [CAL] PRD 6.3
RETELL_WEIGHT = 0.40  # [CAL] PRD 6.3
ITEM_WEIGHT = 0.60  # [CAL] PRD 6.3
ITEM_MAX_POINTS = 2

COMPREHENSION_CUT = 70  # [CAL] PRD 6.5 and 6.6, for RC and LC
BORDER = 8  # [CAL] PRD 6.5 and 6.6
LISTENING_THRESHOLD = COMPREHENSION_CUT + BORDER

ACCURACY_BANDS: tuple[tuple[float, Band], ...] = (  # [CAL] PRD 6.7
    (98, "INDEPENDENT"),
    (95, "INSTRUCTIONAL"),
    (90, "SUPPORTED"),
)
RC_BANDS: tuple[tuple[float, Band], ...] = (  # [CAL] PRD 6.7
    (90, "INDEPENDENT"),
    (70, "INSTRUCTIONAL"),
    (50, "SUPPORTED"),
)
BAND_ORDER: tuple[Band, ...] = ("FRUSTRATION", "SUPPORTED", "INSTRUCTIONAL", "INDEPENDENT")
REPORTED_OFFSET = {"INDEPENDENT": 0, "INSTRUCTIONAL": 0, "SUPPORTED": -1, "FRUSTRATION": -2}
NEXT_OFFSET = {"INDEPENDENT": 1, "INSTRUCTIONAL": 0, "SUPPORTED": -1, "FRUSTRATION": -2}

TERM_1_MONTHS = range(9, 13)  # [CAL] PRD 6.7 default calendar: term 1 is September to December

BLOCKING_FLAGS = frozenset({"LOW_AUDIO", "OFF_TASK"})
INFORMATIONAL_FLAGS = frozenset(
    {
        "LIVE_FALLBACK",
        "RECONNECTED",
        "DEMO_PROFILE",
        "LIVE_FIRST",
        "LC_NOT_USED",
        "COACH_TEMPLATE_USED",
        "FALLBACK_PASSAGE",
    }
)


# ---- 6.1 fluency and 6.2 word reading


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
    _check_class(primary_class)
    if accuracy_pct is None or wcpm is None:
        return None
    return accuracy_pct >= ACCURACY_CUT and wcpm >= WCPM_CUT[primary_class]


# ---- 6.3 comprehension


def weighted_credit(propositions: Sequence[tuple[int, float]]) -> float:
    """Sum of weight x credit over (weight, credit) pairs; weight 1 (detail) or 2 (core),
    credit 0, 0.5 or 1."""
    for weight, credit in propositions:
        if weight not in (1, 2) or credit not in (0, 0.5, 1):
            raise ValueError(f"bad proposition weight or credit: {weight}, {credit}")
    return sum(weight * credit for weight, credit in propositions)


def retell_coverage(credit: float, total_weight: int) -> float:
    """R_prop: full credit once the retell covers 60% of the total weight."""
    if total_weight <= 0 or not 0 <= credit <= total_weight:
        raise ValueError(f"credit {credit} is not within a total weight of {total_weight}")
    return min(1.0, credit / (RETELL_FULL_COVERAGE * total_weight))


def item_score(points: Sequence[int]) -> float:
    """Q_score: item points over the maximum. Works for any number of items."""
    if not points or any(p not in range(ITEM_MAX_POINTS + 1) for p in points):
        raise ValueError(f"item points must be 0, 1 or 2: {points}")
    return sum(points) / (ITEM_MAX_POINTS * len(points))


def comprehension_score(coverage: float, items: float) -> float:
    """RC on the read passage, LC on the listening passage, from 0 to 100."""
    if not (0 <= coverage <= 1 and 0 <= items <= 1):
        raise ValueError("coverage and item score must be between 0 and 1")
    return round(100 * (RETELL_WEIGHT * coverage + ITEM_WEIGHT * items), 1)


# ---- 6.5 listening module


@dataclass(frozen=True)
class ListeningOutcome:
    lc_used: bool
    flag: str | None


def run_listening_module(quick_rc: float) -> bool:
    """The one decision taken during the session, on the quick RC (PRD 7.4)."""
    return quick_rc < LISTENING_THRESHOLD


def listening_outcome(listening_module_run: bool, final_rc: float | None) -> ListeningOutcome:
    """Reconciles the in-session decision with the final RC. A reading stopped by the
    kindness rule has no RC, so its listening result is always used."""
    if final_rc is None:
        return ListeningOutcome(lc_used=listening_module_run, flag=None)
    if listening_module_run:
        if final_rc >= LISTENING_THRESHOLD:
            return ListeningOutcome(lc_used=False, flag="LC_NOT_USED")
        return ListeningOutcome(lc_used=True, flag=None)
    if final_rc < COMPREHENSION_CUT:
        return ListeningOutcome(lc_used=False, flag="LC_MISSED")
    return ListeningOutcome(lc_used=False, flag=None)


# ---- 6.6 reader profile


@dataclass(frozen=True)
class Profile:
    code: ProfileCode
    provisional: bool


def assign_profile(
    *,
    flags: Collection[str],
    reading_stopped_early: bool,
    d_ok: bool | None,
    rc: float | None,
    lc: float | None,
) -> Profile:
    """PRD 6.6. Pass lc only when the listening result is used (listening_outcome).
    Provisional near a cut, or with any flag that is not informational (PRD 6.8)."""
    code = _profile_code(set(flags), reading_stopped_early, d_ok, rc, lc)
    near_cut = any(
        score is not None and abs(score - COMPREHENSION_CUT) < BORDER for score in (rc, lc)
    )
    provisional = near_cut or any(flag not in INFORMATIONAL_FLAGS for flag in flags)
    return Profile(code=code, provisional=provisional)


def _profile_code(
    flags: set[str],
    reading_stopped_early: bool,
    d_ok: bool | None,
    rc: float | None,
    lc: float | None,
) -> ProfileCode:
    if flags & BLOCKING_FLAGS:
        return "INSUFFICIENT_EVIDENCE"
    if reading_stopped_early:
        if lc is None:
            return "INSUFFICIENT_EVIDENCE"
        return "DECODING_LIMITED" if lc >= COMPREHENSION_CUT else "NEEDS_SUPPORT_IN_BOTH"
    if d_ok is None or rc is None:
        return "INSUFFICIENT_EVIDENCE"
    if rc >= COMPREHENSION_CUT:
        return "ON_TRACK" if d_ok else "UNDERSTANDS_BUILDING_WORD_READING"
    if lc is None:
        return "INSUFFICIENT_EVIDENCE"
    if lc >= COMPREHENSION_CUT:
        return "COMPREHENSION_STRATEGY_GAP" if d_ok else "DECODING_LIMITED"
    return "FLUENT_NEEDS_LANGUAGE_SUPPORT" if d_ok else "NEEDS_SUPPORT_IN_BOTH"


# ---- 6.7 Alo Reading Level


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
    _check_arl(passage_arl)
    if band is None:
        return None
    arl = max(ARL_MIN, passage_arl + REPORTED_OFFSET[band])
    return ReportedLevel(arl=arl, at_least=band == "INDEPENDENT")


def next_passage_level(passage_arl: int, band: Band | None) -> int:
    """With no band the next session retests at the same level."""
    _check_arl(passage_arl)
    if band is None:
        return passage_arl
    return min(ARL_MAX, max(ARL_MIN, passage_arl + NEXT_OFFSET[band]))


def level_confirmed(previous_arl: int | None, reported_arl: int) -> bool:
    """Confirmed once two consecutive sessions agree within one level."""
    return previous_arl is not None and abs(reported_arl - previous_arl) <= 1


def approx_primary_class(arl: int) -> int:
    """ARL 1-2 is about Primary 1, up to ARL 11-12 about Primary 6. Approximate, not normed."""
    _check_arl(arl)
    return (arl + 1) // 2


def start_arl(primary_class: int, on: date, previous_next_arl: int | None = None) -> int:
    """A returning child starts at their last next_passage_arl. A first session starts at
    2 x class - 1 in term 1 and 2 x class in terms 2 and 3."""
    _check_class(primary_class)
    if previous_next_arl is not None:
        _check_arl(previous_next_arl)
        return previous_next_arl
    return 2 * primary_class - (1 if on.month in TERM_1_MONTHS else 0)


def _check_arl(arl: int) -> None:
    if not ARL_MIN <= arl <= ARL_MAX:
        raise ValueError(f"ARL must be {ARL_MIN} to {ARL_MAX}: {arl}")


def _check_class(primary_class: int) -> None:
    if primary_class not in PRIMARY_CLASSES:
        raise ValueError(f"primary_class must be 1 to 6: {primary_class}")
