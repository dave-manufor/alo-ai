"""End of a child's turn from the VAD, outside the reading (PRD 4.1, 4.3, 5.1).

Pure: the caller passes the clock and the VAD's start and end of speech. A turn
ends ANSWERED after the child spoke and then stayed quiet for the turn's end
silence, and reports SILENCE for every 8 s with no speech at all (the machine
nudges once, then moves on).

Kemi's own prompts are not the child. While a prompt is playing on the child's phone
(from the `play` the agent sent to its `played` or `missing` ack) and for a moment after:
- the 8 s silence is not counted, so a slow download cannot use up the child's wait;
- speech the detector reports is ignored, because it is Kemi's voice coming back through
  the phone's microphone, not an answer. The caller must also leave it out of the mic
  check's level and the transcript.

In scripted mode this is the whole end-of-speech decision. LiveKit's turn
detector runs inside its LLM pipeline, so it arrives with the Gemini Live
conductor and its end_turn (PRD 4.2).
"""

from dataclasses import dataclass
from typing import Literal

SILENCE_MS = 8_000  # no speech at all: one SILENCE (PRD 4.3)
RETELL_END_MS = 4_000  # the retell ends after 4 s of silence (PRD 4.1)
ANSWER_END_MS = 1_500  # a pause that ends an answer or the chat; rehearse before changing
MIC_END_MS = 2_000  # the count to five has ended: a child counts with pauses between numbers
MIC_MIN_VOICED_MS = 2_000  # about how long the count takes
MIC_SHORT_END_MS = 4_000  # a count shorter than that ends after this pause instead
PLAY_SAFETY_MS = 60_000  # a play with no ack for this long is taken as over (a lost ack)
ECHO_TAIL_MS = 300  # the end of a clip's sound still in the room after its ack

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
    _speech_began: int = 0
    _voiced_ms: int = 0
    _playing_since: int | None = None
    _prompt_ended: int = -ECHO_TAIL_MS
    _ignored_start: bool = False

    def start(self, kind: TurnKind, now_ms: int) -> None:
        self.active, self.kind = True, kind
        self._waiting_since = now_ms
        self._speaking = self._heard = self._ignored_start = False
        self._voiced_ms = 0

    def stop(self) -> None:
        self.active = False

    def prompt_started(self, now_ms: int) -> None:
        """A clip was sent to the child's phone."""
        self._playing_since = now_ms

    def prompt_finished(self, now_ms: int) -> None:
        """The clip finished (or could not play): the wait for speech starts from now."""
        self._playing_since = None
        self._prompt_ended = now_ms
        if self.active and not self._heard:
            self._waiting_since = now_ms

    def ignoring(self, now_ms: int) -> bool:
        """True while a prompt is playing or has only just stopped: what the microphone
        hears then is Kemi's voice in the room."""
        if self._playing_since is not None and now_ms - self._playing_since < PLAY_SAFETY_MS:
            return True
        return now_ms - self._prompt_ended < ECHO_TAIL_MS

    def speech_started(self, now_ms: int) -> bool:
        """The VAD heard speech. False if it is ignored (Kemi's own voice)."""
        if self.ignoring(now_ms):
            self._ignored_start = True
            return False
        self._ignored_start = False
        self._speaking = True
        self._heard = True
        self._speech_began = now_ms
        return True

    def speech_ended(self, now_ms: int) -> bool:
        """The VAD heard the speech stop. False if its start was ignored."""
        if self._ignored_start:
            self._ignored_start = False
            return False
        self._speaking = False
        self._last_speech_end = now_ms
        self._voiced_ms += max(0, now_ms - self._speech_began)
        return True

    def tick(self, now_ms: int) -> Literal["ANSWERED", "SILENCE"] | None:
        if not self.active or self._speaking:
            return None
        if self._playing_since is not None and now_ms - self._playing_since < PLAY_SAFETY_MS:
            return None  # the child is still hearing the prompt
        if self._heard:
            if now_ms - self._last_speech_end >= self._end_ms():
                self.active = False
                return "ANSWERED"
            return None
        if now_ms - self._waiting_since >= SILENCE_MS:
            self._waiting_since = now_ms
            return "SILENCE"
        return None

    def _end_ms(self) -> int:
        if self.kind == "mic" and self._voiced_ms < MIC_MIN_VOICED_MS:
            return MIC_SHORT_END_MS
        return _END_MS[self.kind]
