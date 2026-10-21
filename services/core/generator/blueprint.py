"""The passage blueprint and the two length profiles (PRD 4.5, 4.1).

Every number is [CAL]: provisional until the pilot (PRD 13). A change here needs W3's
sign-off, because the difficulty gate and the book cross-check read it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    """One row of the READ blueprint: two ARLs share a row."""

    arls: tuple[int, int]
    words: tuple[int, int]
    max_mean_sentence: float  # words per sentence
    zipf_threshold: float  # a word is "common" at or above this Zipf frequency (wordfreq)
    zipf_share: float  # at least this share of words must be common
    max_long_share: float  # at most this share of words with 3+ syllables


ROWS = (
    Row((1, 2), (50, 70), 7, 4.5, 0.95, 0.02),  # P1
    Row((3, 4), (100, 120), 9, 4.0, 0.92, 0.03),  # P2
    Row((5, 6), (120, 150), 11, 3.5, 0.90, 0.05),  # P3
    Row((7, 8), (150, 180), 13, 3.5, 0.88, 0.07),  # P4
    Row((9, 10), (170, 200), 15, 3.0, 0.85, 0.09),  # P5
    Row((11, 12), (190, 220), 17, 3.0, 0.82, 0.11),  # P6
)

DIFFICULTY_TOLERANCE = 0.5  # the estimated ARL must be within this of the target (PRD 4.5 G4)


def row_for(arl: int) -> Row:
    for row in ROWS:
        if row.arls[0] <= arl <= row.arls[1]:
            return row
    raise ValueError(f"ARL must be 1 to 12, got {arl}")


@dataclass(frozen=True)
class LengthRules:
    """What the Writer must produce and the gate must find, per length profile."""

    name: str  # STANDARD | DEMO, as in the passage schema
    words: tuple[int, int] | None  # None: the blueprint row's range
    propositions: tuple[int, int]
    core_min: int  # propositions with weight 2
    literal_items: int
    inferential_items: int


STANDARD = LengthRules("STANDARD", None, (6, 14), 3, 2, 1)
DEMO = LengthRules("DEMO", (70, 80), (4, 8), 2, 1, 1)  # 75 +/- 5 words (PRD 4.1)

_PROFILES = {rules.name: rules for rules in (STANDARD, DEMO)}


def rules_for(length_profile: str) -> LengthRules:
    try:
        return _PROFILES[length_profile]
    except KeyError:
        raise ValueError(
            f"length_profile must be STANDARD or DEMO, got {length_profile!r}"
        ) from None


def word_range(arl: int, length_profile: str) -> tuple[int, int]:
    return rules_for(length_profile).words or row_for(arl).words
