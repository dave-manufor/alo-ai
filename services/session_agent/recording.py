"""Where each turn's audio goes (PRD 5, SDD 4).

The child's audio is recorded per turn, independently of Gemini Live, and is the
only input to grading. Objects are 16 kHz mono FLAC named by UUID v4:

    gs://{audio bucket}/{session_uuid}/{phase}/{uuid4}.flac

This module only names turns and keeps the list; the audio is written by the worker.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from .machine.types import TurnPhase


@dataclass(frozen=True)
class Turn:
    turn_id: str
    phase: TurnPhase
    audio_uri: str


class AudioLog:
    def __init__(
        self,
        bucket_name: str,
        session_uuid: str,
        new_uuid: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        if uuid.UUID(session_uuid).version != 4:
            raise ValueError("session_uuid must be a UUID v4")
        self._bucket_name = bucket_name
        self._session_uuid = session_uuid
        self._new_uuid = new_uuid
        self._turns: list[Turn] = []

    @property
    def turns(self) -> tuple[Turn, ...]:
        return tuple(self._turns)

    def new_turn(self, phase: TurnPhase) -> Turn:
        name = f"{self._session_uuid}/{phase}/{self._new_uuid()}.flac"
        turn = Turn(f"turn_{len(self._turns) + 1:03d}", phase, f"gs://{self._bucket_name}/{name}")
        self._turns.append(turn)
        return turn

    def turn_audio_uris(self) -> list[dict]:
        """The turn_audio_uris of the session.done event."""
        return [
            {"turn_id": t.turn_id, "phase": t.phase, "audio_uri": t.audio_uri}
            for t in self._turns
        ]

    def reading_uri(self) -> str | None:
        """The audio of the most recent reading turn (the phase1.recorded event)."""
        for turn in reversed(self._turns):
            if turn.phase == "READING":
                return turn.audio_uri
        return None
