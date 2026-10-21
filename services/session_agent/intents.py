"""Spoken "stop" and "say it again", from a final transcript (PRD 4.2, 4.3).

In scripted mode nothing else listens for these, so a short utterance that is
mostly one of the phrases below becomes ChildStop or RepeatRequest. Long
utterances are answers, even if they contain "stop" ("the bus had to stop").
Never used during the reading, where the words belong to the passage. The
Gemini Live conductor takes this over with end_turn and request_repeat.
"""

import re

from .clips.keys import clean_word
from .machine.types import ChildStop, RepeatRequest

MAX_WORDS = 5

# Public: the Reading Scorer keeps a copy (services/reading_scorer/words.py).
STOP_PHRASES = ("stop", "i want to stop", "i don't want to", "i'm done", "i am done", "no more")
POLITE = ("please", "auntie", "aunty")  # dropped before matching
_REPEAT = ("say it again", "say that again", "again", "repeat", "what", "pardon", "sorry what")


def _phrase(text: str) -> str:
    words = [clean_word(w) for w in re.split(r"\s+", text)]
    return " ".join(w for w in words if w)


def intent(text: str) -> ChildStop | RepeatRequest | None:
    phrase = _phrase(text)
    words = phrase.split()
    if not words or len(words) > MAX_WORDS:
        return None
    for please in POLITE:
        phrase = " ".join(w for w in phrase.split() if w != please)
    if phrase in STOP_PHRASES:
        return ChildStop()
    if phrase in _REPEAT:
        return RepeatRequest()
    return None
