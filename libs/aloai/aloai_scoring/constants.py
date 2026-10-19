"""Every constant of the scoring engine, with the module version reports store.

Constants marked [CAL] are provisional and are recalibrated on pilot data (PRD 13.2).
Changing one needs W3's approval, a new SCORING_MODULE, a validation rerun and a PRD
changelog line (alo-scoring-change).
"""

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
TOLD_WAIT_S = 5  # PRD 4.1: the Session Agent's wait before "That word is X." (its TOLD_WORD_MS)
NORM_TOLD_WAIT_S = 3  # [CAL] PRD 6.2: the norms behind WCPM_CUT tell a word after 3 s

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

RETELL_PASS_TOLERANCE = 1.0  # PRD 7.2
RETELL_SPREAD_LIMIT = 2.0  # PRD 7.2

BOOK_BAND_OFFSETS = {  # PRD 8, as (low, high) around the reported ARL
    "ON_TRACK": (0, 1),
    "UNDERSTANDS_BUILDING_WORD_READING": (-1, 0),
    "DECODING_LIMITED": (-2, -1),
    "FLUENT_NEEDS_LANGUAGE_SUPPORT": (-1, 0),
    "NEEDS_SUPPORT_IN_BOTH": (-2, -1),
    "COMPREHENSION_STRATEGY_GAP": (0, 0),
}

PAUSE_MS = 180  # [CAL] PRD 5.5: a silent interval this long counts as a pause
PHRASING_FULL_INTRUSION = 0.25  # [CAL] PRD 5.5: phrasing reaches 0 at this intrusion rate
PROSODY_MIN_ACCURACY = 90  # PRD 5.5
PROSODY_MIN_SENTENCES = 2  # PRD 5.5
ELIGIBLE_MIN_WORDS = 5  # PRD 5.5: an eligible sentence has at least 5 words
ELIGIBLE_MAX_ERRORS = 1  # PRD 5.5: and fewer than 2 errors

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


def check_arl(arl: int) -> None:
    if not ARL_MIN <= arl <= ARL_MAX:
        raise ValueError(f"ARL must be {ARL_MIN} to {ARL_MAX}: {arl}")


def check_class(primary_class: int) -> None:
    if primary_class not in PRIMARY_CLASSES:
        raise ValueError(f"primary_class must be 1 to 6: {primary_class}")


def clamp_arl(arl: int) -> int:
    return min(ARL_MAX, max(ARL_MIN, arl))
