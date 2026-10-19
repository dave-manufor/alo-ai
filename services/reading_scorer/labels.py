"""Word labels from two transcripts (PRD 5.3): a word counts only where both agree.

Both have the passage word: CORRECT. Both have the same other word: SUBSTITUTION. Both
skip it: OMISSION. A word "That word is X." was played for: TOLD, from the agent's log.
Any disagreement, or a word both have right that Chirp was unsure of, is UNCERTAIN and
left out of the counts. MISPRONUNCIATION needs the phone-level check, which is not built.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from .words import Heard, Placed, normalize

LOW_CONFIDENCE = 0.5  # [CAL] PRD 5.3
NEAR_MISS = 0.5  # how alike an attempt must be to the word for its correction to count

Label = Literal["CORRECT", "SUBSTITUTION", "OMISSION", "TOLD", "UNCERTAIN"]
ERRORS = frozenset({"SUBSTITUTION", "OMISSION", "TOLD", "MISPRONUNCIATION"})


@dataclass(frozen=True)
class WordLabel:
    token_index: int
    target_word: str
    chirp: Heard | None
    gemini: Heard | None
    label: Label
    is_self_corrected: bool


def label_words(
    targets: Sequence[str],
    chirp: Sequence[Placed],
    gemini: Sequence[Placed],
    told: Collection[int],
) -> list[WordLabel]:
    """Every passage word up to the last one the child reached; the words after it were
    not attempted and are not omissions."""
    labels = [
        _label(index, target, chirp[index], gemini[index], index in told)
        for index, target in enumerate(targets)
    ]
    reached = [label.token_index for label in labels if label.label != "OMISSION"]
    return labels[: reached[-1] + 1] if reached else []


def _label(index: int, target: str, chirp: Placed, gemini: Placed, told: bool) -> WordLabel:
    word = normalize(target)
    heard_chirp = normalize(chirp.heard.text) if chirp.heard else None
    heard_gemini = normalize(gemini.heard.text) if gemini.heard else None
    self_corrected = False
    if told:
        label: Label = "TOLD"
    elif heard_chirp is None and heard_gemini is None:
        label = "OMISSION"
    elif heard_chirp == word and heard_gemini == word:
        unsure = chirp.heard.confidence is not None and chirp.heard.confidence < LOW_CONFIDENCE
        label = "UNCERTAIN" if unsure else "CORRECT"
        self_corrected = not unsure and _corrected(word, chirp) and _corrected(word, gemini)
    elif heard_chirp == heard_gemini:
        label = "SUBSTITUTION"
    else:
        label = "UNCERTAIN"
    return WordLabel(index, target, chirp.heard, gemini.heard, label, self_corrected)


def _corrected(word: str, placed: Placed) -> bool:
    """A near miss heard just before the right word. Transcripts give no times for the
    attempt, so PRD 5.3's 3 s window is not checked."""
    if not placed.before or placed.before[-1] == word:
        return False
    return SequenceMatcher(None, placed.before[-1], word).ratio() >= NEAR_MISS
