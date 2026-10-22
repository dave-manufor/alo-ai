"""The session details the worker is dispatched with (POST /v1/sessions, W1 -> W2).

The Account service creates the LiveKit room and dispatches the agent with JSON
metadata. Nothing here comes from the child's browser except through that
service, and VOICE_MODE / SESSION_PROFILE never do (server settings):

    {
      "session_id": "sess_...",          required
      "child_id": "child_...",           required (Firestore id, never a name)
      "context": "HOME" | "SCHOOL",      required
      "capture_mode": "LIVE" | "LOCAL_CAPTURE",   default LIVE
      "passage_id": "..."                a returning child's prepared passage
    }

The shape is schemas/session_start.schema.json (room_metadata), with a fixture in
fixtures/contracts/ that tests/test_contracts.py parses with this module.
"""

import json
from dataclasses import dataclass

from .events import SessionContext


class MetadataError(ValueError):
    pass


@dataclass(frozen=True)
class SessionStart:
    ctx: SessionContext
    child_id: str
    passage_id: str | None


def parse(raw: str, voice_profile_id: str) -> SessionStart:
    try:
        meta = json.loads(raw or "{}")
    except ValueError as error:
        raise MetadataError(f"session metadata is not JSON: {error}") from None
    if not isinstance(meta, dict):
        raise MetadataError("session metadata must be a JSON object")
    missing = [k for k in ("session_id", "child_id", "context") if not meta.get(k)]
    if missing:
        raise MetadataError(f"session metadata lacks {', '.join(missing)}")
    if meta["context"] not in ("HOME", "SCHOOL"):
        raise MetadataError(f"unknown context {meta['context']!r}")
    capture_mode = meta.get("capture_mode", "LIVE")
    if capture_mode not in ("LIVE", "LOCAL_CAPTURE"):
        raise MetadataError(f"unknown capture_mode {capture_mode!r}")
    ctx = SessionContext(
        session_id=meta["session_id"],
        child_ref=meta["child_id"],
        context=meta["context"],
        voice_profile_id=voice_profile_id,
        capture_mode=capture_mode,
    )
    return SessionStart(ctx, meta["child_id"], meta.get("passage_id") or None)
