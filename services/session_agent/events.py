"""Turn the machine's EmitEvent actions into published events (schemas/event_envelope.schema.json).

The machine knows the passage, the flags and the session settings. This module
adds what it does not: the session ids, the audio paths and the envelope. One
topic (`aloai.session-events`), at-least-once delivery, so event_id lets a
consumer drop duplicates.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from .machine.types import EmitEvent
from .recording import AudioLog

# The version of each event's data (schemas/event_envelope.schema.json). Must match
# aloai_events.SCHEMA_VERSIONS (tests/test_shared_contracts.py).
SCHEMA_VERSIONS = {"session.started": 1, "phase1.recorded": 1, "session.done": 2}


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    child_ref: str  # an opaque reference, never a name
    context: str  # HOME | SCHOOL
    voice_profile_id: str
    capture_mode: str  # LIVE | LOCAL_CAPTURE


class Publisher(Protocol):
    def publish(self, event: dict) -> None: ...


class MemoryPublisher:
    """Collects events for tests and AI_MODE=fixtures."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)


def build_event(
    emit: EmitEvent,
    ctx: SessionContext,
    audio: AudioLog,
    *,
    event_id: str,
    now: datetime,
) -> dict:
    return {
        "event_id": event_id,
        "type": emit.type,
        "schema_version": SCHEMA_VERSIONS[emit.type],
        "occurred_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "session_id": ctx.session_id,
        "data": _data(emit, ctx, audio),
    }


def _data(emit: EmitEvent, ctx: SessionContext, audio: AudioLog) -> dict:
    d = emit.data
    if emit.type == "session.started":
        return {
            "session_id": ctx.session_id,
            "child_ref": ctx.child_ref,
            "passage_id": d["passage_id"],
            "context": ctx.context,
            "voice_profile_id": ctx.voice_profile_id,
            "voice_mode": d["voice_mode"],
            "session_profile": d["session_profile"],
        }
    if emit.type == "phase1.recorded":
        audio_uri = audio.reading_uri()
        if audio_uri is None:
            raise ValueError("phase1.recorded without a recorded reading turn")
        return {
            "session_id": ctx.session_id,
            "audio_uri": audio_uri,
            "passage_id": d["passage_id"],
            "told_token_indices": d["told_token_indices"],
        }
    data = {
        "session_id": ctx.session_id,
        "passage_id": d["passage_id"],
        "turn_audio_uris": audio.turn_audio_uris(),
        "capture_mode": ctx.capture_mode,
        "session_settings": d["session_settings"],
        "flags": d["flags"],
        "reading_stopped_early": d["reading_stopped_early"],
        "listening_module_run": d["listening_module_run"],
    }
    if "listening_passage_id" in d:
        data["listening_passage_id"] = d["listening_passage_id"]
    return data
