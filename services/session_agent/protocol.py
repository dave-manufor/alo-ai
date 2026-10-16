"""The session protocol on the LiveKit data channel (schemas/session_protocol.schema.json).

Agent to web app: clip_list, play, show_passage, hide_passage, reconnecting.
Web app to agent: played, missing (acks for a clip). The web app never shows a
score, timer or red mark; the agent never sends one.
"""

import json
from collections.abc import Callable, Sequence

from .machine.types import (
    Action,
    ClipAck,
    HidePassage,
    PlayClip,
    PlayWordClip,
    ShowPassage,
    ShowReconnecting,
)

SCHEMA_VERSION = 1


def clip_list(clips: Sequence[tuple[str, str]]) -> dict:
    """The clips the web app should cache before the session starts: (clip_id, url) pairs."""
    return {
        "schema_version": SCHEMA_VERSION,
        "cmd": "clip_list",
        "clips": [{"clip_id": clip_id, "url": url} for clip_id, url in clips],
    }


def message_for(action: Action, word_clip_id: Callable[[int], str]) -> dict | None:
    """The data-channel message for a machine action, or None if it is not one."""
    match action:
        case PlayClip(clip_id=clip_id):
            return {"schema_version": SCHEMA_VERSION, "cmd": "play", "clip_id": clip_id}
        case PlayWordClip(word_index=word_index):
            return {
                "schema_version": SCHEMA_VERSION,
                "cmd": "play",
                "clip_id": word_clip_id(word_index),
            }
        case ShowPassage(passage_id=passage_id):
            return {
                "schema_version": SCHEMA_VERSION,
                "cmd": "show_passage",
                "passage_id": passage_id,
            }
        case HidePassage():
            return {"schema_version": SCHEMA_VERSION, "cmd": "hide_passage"}
        case ShowReconnecting():
            return {"schema_version": SCHEMA_VERSION, "cmd": "reconnecting"}
    return None


def encode(message: dict) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode()


def parse_client(raw: bytes | str) -> ClipAck | None:
    """A `played` or `missing` ack from the web app. Anything else is dropped."""
    try:
        message = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("cmd") not in ("played", "missing"):
        return None
    clip_id = message.get("clip_id")
    if not isinstance(clip_id, str) or not clip_id:
        return None
    return ClipAck(clip_id=clip_id, status=message["cmd"])
