"""Position tracker for the reading phase (SDD 4, PRD 4.1).

Follows where the child is in the passage by fuzzy-matching speech-to-text
partials to the passage tokens. It reports three things to the state machine:

- `stall(now_ms)`  5.0 s with no progress on the same word -> Silence(ms, word_index).
  No progress, not silence: a child sounding a word out gets the same 5 s.
- `progress(now_ms, told)` the words read so far, without the words the child was
  told, for the kindness rule -> ReadingProgress. The tracker cannot judge a word
  correct live, so this approximates "words correct" (PRD 4.3).
- `done(now_ms)`   the last word was reached -> ReadingDone

Pure: the caller passes the clock. It counts words and finds positions; it does
not score anything. The matching constants decide when "That word is X." plays,
so change them only after rehearsing with real readings.
"""

from collections.abc import Iterable, Sequence
from difflib import SequenceMatcher

from .clips.keys import clean_word
from .machine.profiles import TOLD_WORD_MS
from .machine.types import ReadingDone, ReadingProgress, Silence

SIMILARITY = 0.75  # how alike a heard word and a passage word must be
LOOKAHEAD = 3  # how many passage words a child may skip ahead and still be followed


def _similar(heard: str, expected: str) -> bool:
    return heard == expected or SequenceMatcher(None, heard, expected).ratio() >= SIMILARITY


class PositionTracker:
    def __init__(self, token_texts: Sequence[str]) -> None:
        self._words = [clean_word(text) for text in token_texts]
        self._position = 0  # index of the next word to be read
        self._segment_start = 0  # position when the current utterance began
        self._words_read = 0
        self._counted: set[int] = set()
        self._started_ms: int | None = None
        self._last_advance_ms = 0
        self._stalled_on: set[int] = set()
        self._skip_blank()

    @property
    def position(self) -> int:
        return self._position

    @property
    def words_read(self) -> int:
        return len(self._counted)

    def start(self, now_ms: int) -> None:
        self._started_ms = now_ms
        self._last_advance_ms = now_ms

    def on_partial(self, transcript: str, now_ms: int) -> None:
        """A speech-to-text partial. It holds the whole utterance so far, and may revise it."""
        position = self._blank_end(self._segment_start)
        for heard in (clean_word(part) for part in transcript.split()):
            if not heard:
                continue
            match = self._find(heard, position)
            if match is None:
                continue
            self._counted.add(match)
            position = self._blank_end(match + 1)
        if position > self._position:
            self._position = position
            self._last_advance_ms = now_ms

    def on_final(self, transcript: str, now_ms: int) -> None:
        """The utterance is final; the next one is matched from here."""
        self.on_partial(transcript, now_ms)
        self._segment_start = self._position

    def stall(self, now_ms: int) -> Silence | None:
        """No progress for TOLD_WORD_MS on one word. Reported once per word."""
        if self._started_ms is None or self.done_reached:
            return None
        waited = now_ms - self._last_advance_ms
        if waited < TOLD_WORD_MS or self._position in self._stalled_on:
            return None
        self._stalled_on.add(self._position)
        return Silence(ms=waited, word_index=self._position)

    def progress(self, now_ms: int, told: Iterable[int] = ()) -> ReadingProgress:
        """told: the token indices the child was told (the machine's TOLD log)."""
        words_read = len(self._counted - set(told))
        return ReadingProgress(elapsed_ms=self._elapsed(now_ms), words_read=words_read)

    def done(self, now_ms: int) -> ReadingDone | None:
        if not self.done_reached:
            return None
        return ReadingDone(elapsed_ms=self._elapsed(now_ms))

    @property
    def done_reached(self) -> bool:
        return self._position >= len(self._words)

    # ---- internals

    def _elapsed(self, now_ms: int) -> int:
        return 0 if self._started_ms is None else now_ms - self._started_ms

    def _find(self, heard: str, position: int) -> int | None:
        stop = min(position + LOOKAHEAD + 1, len(self._words))
        for index in range(position, stop):
            if self._words[index] and _similar(heard, self._words[index]):
                return index
        return None

    def _blank_end(self, position: int) -> int:
        """Step over tokens with no word in them (stray punctuation)."""
        while position < len(self._words) and not self._words[position]:
            position += 1
        return position

    def _skip_blank(self) -> None:
        self._position = self._segment_start = self._blank_end(0)
