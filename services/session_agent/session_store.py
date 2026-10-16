"""Firestore records the Session Agent writes (schemas/session_record.schema.json).

    sessions/{session_id}                 one session
    sessions/{session_id}/turns/{turn_id} one recorded turn

Only builders and paths here; the Firestore client is wired in with the worker.
`voice_mode` and `session_profile` are the server's values, saved so a report can
say how the session ran.
"""

from datetime import UTC, datetime
from typing import Protocol

from .events import SessionContext
from .recording import Turn

SCHEMA_VERSION = 1


class Documents(Protocol):
    def set(self, path: str, data: dict) -> None: ...


class MemoryDocuments:
    """Stands in for Firestore in tests and AI_MODE=fixtures."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def set(self, path: str, data: dict) -> None:
        self.docs[path] = data


def session_path(session_id: str) -> str:
    return f"sessions/{session_id}"


def turn_path(session_id: str, turn_id: str) -> str:
    return f"sessions/{session_id}/turns/{turn_id}"


def session_record(
    ctx: SessionContext,
    *,
    child_id: str,
    status: str,
    voice_mode: str,
    session_profile: str,
    passage_id: str,
    passage_source: str,
    flags: tuple[str, ...],
    created_at: datetime,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "child_id": child_id,
        "status": status,
        "context": ctx.context,
        "capture_mode": ctx.capture_mode,
        "voice_mode": voice_mode,
        "session_profile": session_profile,
        "passage_id": passage_id,
        "passage_source": passage_source,
        "flags": list(flags),
        "voice_profile_id": ctx.voice_profile_id,
        "created_at": created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def turn_record(
    turn: Turn, *, live_transcript: str | None = None, asr_transcript: str | None = None
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": turn.phase,
        "audio_uri": turn.audio_uri,
        "live_transcript": live_transcript,
        "asr_transcript": asr_transcript,
    }
