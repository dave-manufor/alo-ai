"""Word labels from two transcripts (PRD 5.3): a word counts only where both agree.

Both have the passage word: CORRECT. Both have the same other word: SUBSTITUTION. Both
skip it: OMISSION. A word "That word is X." was played for: TOLD, from the agent's log.
Any disagreement, or a word both have right that Chirp was unsure of, is UNCERTAIN and
left out of the counts. MISPRONUNCIATION needs the phone-level check, which is not built.

With one transcript (SECOND_TRANSCRIPT=off) there is no second hearing to agree with, so
W3's single rule (2026-10-22) asks more of the one: a different word counts as a misreading
only when the transcript was sure of it (SINGLE_SURE), and a transcript that gives no
confidence at all scores nothing. The Scorer also flags every such reading
SINGLE_TRANSCRIPT, which makes the report provisional.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from typing import Literal

from .words import Heard, Placed, normalize

LOW_CONFIDENCE = 0.5  # [CAL] PRD 5.3
# [CAL] PRD 5.3, one transcript only: how sure it must be of a different word for that word
# to count as a misreading. Below it, and at or above LOW_CONFIDENCE, the word is UNCERTAIN.
SINGLE_SURE = 0.8
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
    gemini: Sequence[Placed] | None,
    told: Collection[int],
) -> list[WordLabel]:
    """Every passage word up to the last one the child reached; the words after it were
    not attempted and are not omissions. gemini is None in single-transcript mode
    (SECOND_TRANSCRIPT=off): see _label_single."""
    if gemini is None:
        labels = [
            _label_single(index, target, chirp[index], index in told)
            for index, target in enumerate(targets)
        ]
    else:
        labels = [
            _label(index, target, chirp[index], gemini[index], index in told)
            for index, target in enumerate(targets)
        ]
    reached = [label.token_index for label in labels if label.label != "OMISSION"]
    labels = labels[: reached[-1] + 1] if reached else []
    if gemini is None and not any(
        p.heard is not None and p.heard.confidence is not None for p in chirp
    ):
        # One transcript with no confidence anywhere: a misreading can't be told apart from
        # a mishearing, so nothing is scored (accuracy and WCPM stay empty rather than wrong).
        labels = [replace(label, label="UNCERTAIN", is_self_corrected=False) for label in labels]
    return labels


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


def _label_single(index: int, target: str, chirp: Placed, told: bool) -> WordLabel:
    """One transcript, no second opinion (SECOND_TRANSCRIPT=off; W3's rule). A right word
    counts unless the transcript was unsure of it (LOW_CONFIDENCE); a different word counts
    as a substitution only when it was sure (SINGLE_SURE); otherwise, or when it gives no
    confidence for the word, the word is UNCERTAIN and left out."""
    word = normalize(target)
    heard = chirp.heard
    self_corrected = False
    if told:
        label: Label = "TOLD"
    elif heard is None:
        label = "OMISSION"
    elif heard.confidence is None or heard.confidence < LOW_CONFIDENCE:
        label = "UNCERTAIN"
    elif normalize(heard.text) == word:
        label = "CORRECT"
        self_corrected = _corrected(word, chirp)
    elif heard.confidence >= SINGLE_SURE:
        label = "SUBSTITUTION"
    else:
        label = "UNCERTAIN"
    return WordLabel(index, target, heard, None, label, self_corrected)


def _corrected(word: str, placed: Placed) -> bool:
    """A near miss heard just before the right word. Transcripts give no times for the
    attempt, so PRD 5.3's 3 s window is not checked."""
    if not placed.before or placed.before[-1] == word:
        return False
    return SequenceMatcher(None, placed.before[-1], word).ratio() >= NEAR_MISS
