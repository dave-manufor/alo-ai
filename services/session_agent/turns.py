"""End of a child's turn from the VAD, outside the reading (PRD 4.1, 4.3, 5.1).

Pure: the caller passes the clock and the VAD's start and end of speech. A turn
ends ANSWERED after the child spoke and then stayed quiet for the turn's end
silence, and reports SILENCE for every 8 s with no speech at all (the machine
nudges once, then moves on). The wait for an answer starts when the prompt has
finished playing, not when it was sent.

In scripted mode this is the whole end-of-speech decision. LiveKit's turn
detector runs inside its LLM pipeline, so it arrives with the Gemini Live
conductor and its end_turn (PRD 4.2).
"""

from dataclasses import dataclass
from typing import Literal

SILENCE_MS = 8_000  # no speech at all: one SILENCE (PRD 4.3)
RETELL_END_MS = 4_000  # the retell ends after 4 s of silence (PRD 4.1)
ANSWER_END_MS = 1_500  # a pause that ends an answer or the chat; rehearse before changing
MIC_END_MS = 1_000  # the count to five has ended

TurnKind = Literal["answer", "retell", "mic"]
_END_MS = {"answer": ANSWER_END_MS, "retell": RETELL_END_MS, "mic": MIC_END_MS}


@dataclass
class TurnTaker:
    active: bool = False
    kind: TurnKind = "answer"
    _waiting_since: int = 0
    _speaking: bool = False
    _heard: bool = False
    _last_speech_end: int = 0

    def start(self, kind: TurnKind, now_ms: int) -> None:
        self.active, self.kind = True, kind
        self._waiting_since = now_ms
        self._speaking = self._heard = False

    def stop(self) -> None:
        self.active = False

    def prompt_finished(self, now_ms: int) -> None:
        """A prompt finished playing: the wait for speech starts again from now."""
        if self.active and not self._heard:
            self._waiting_since = now_ms

    def speech_started(self, now_ms: int) -> None:
        self._speaking = True
        self._heard = True

    def speech_ended(self, now_ms: int) -> None:
        self._speaking = False
        self._last_speech_end = now_ms

    def tick(self, now_ms: int) -> Literal["ANSWERED", "SILENCE"] | None:
        if not self.active or self._speaking:
            return None
        if self._heard:
            if now_ms - self._last_speech_end >= _END_MS[self.kind]:
                self.active = False
                return "ANSWERED"
            return None
        if now_ms - self._waiting_since >= SILENCE_MS:
            self._waiting_since = now_ms
            return "SILENCE"
        return None
