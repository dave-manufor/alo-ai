"""The session protocol on the LiveKit data channel (schemas/session_protocol.schema.json).

Agent to web app: clip_list, play, step, show_passage, hide_passage, reconnecting,
child_speaking. Web app to agent: played, missing (replies to a play). The agent decides
every step and the web app only follows; it never shows a score, timer or red mark, and
the agent never sends one. child_speaking says only that the child is heard speaking,
for the screen's light; it carries no words and no level.
"""

import json
from collections.abc import Callable, Sequence

from .machine.types import (
    Action,
    ClipAck,
    HidePassage,
    Phase,
    PlayClip,
    PlayWordClip,
    ShowReconnecting,
)

SCHEMA_VERSION = 3  # 3 adds child_speaking; the web app accepts 2 and 3

# The phases the web app has a screen for. INIT and TRANSITION (the 2 s blank after
# reading) send nothing: the screen stays as it was.
STEPS = frozenset(
    {
        Phase.INTEREST_CHAT,
        Phase.MIC_CHECK,
        Phase.READING,
        Phase.RETELL,
        Phase.QUESTIONS,
        Phase.LISTENING,
        Phase.CLOSE,
        Phase.ENDED,
    }
)


def clip_list(clips: Sequence[tuple[str, str, str | None]]) -> dict:
    """The clips the web app should cache: (clip_id, url, text) triples. text is what the
    clip says, for the speech bubble, or None when it must not be shown."""
    return {
        "schema_version": SCHEMA_VERSION,
        "cmd": "clip_list",
        "clips": [{"clip_id": c, "url": url, "text": text} for c, url, text in clips],
    }


# A reliable LiveKit data message is best kept small (about 15 KiB). The whole session's clip
# list is over 20 KiB, so it is sent in several messages, each under this many bytes.
CLIP_LIST_MAX_BYTES = 14_000


def clip_lists(
    clips: Sequence[tuple[str, str, str | None]], max_bytes: int = CLIP_LIST_MAX_BYTES
) -> list[dict]:
    """The same clips as `clip_list`, cut into messages that each encode to at most
    `max_bytes` (a single clip bigger than that goes alone), in the given order."""
    lists: list[dict] = []
    batch: list[tuple[str, str, str | None]] = []
    for clip in clips:
        trial = clip_list([*batch, clip])
        if batch and len(encode(trial)) > max_bytes:
            lists.append(clip_list(batch))
            batch = []
        batch.append(clip)
    if batch:
        lists.append(clip_list(batch))
    return lists


def step(phase: Phase) -> dict | None:
    """The step message for a phase, or None for a phase without a screen of its own."""
    if phase not in STEPS:
        return None
    return {"schema_version": SCHEMA_VERSION, "cmd": "step", "step": phase.value}


def child_speaking(speaking: bool) -> dict:
    """The child started (True) or stopped (False) speaking, from the voice detector."""
    return {"schema_version": SCHEMA_VERSION, "cmd": "child_speaking", "speaking": speaking}


def show_passage(passage: dict) -> dict:
    """The story to read: its title, sentences and level, and nothing the child is asked
    about (no items, propositions or rubrics)."""
    sentences: dict[int, list[str]] = {}
    for token in passage["tokens"]:
        sentences.setdefault(token["sentence_index"], []).append(token["text"])
    return {
        "schema_version": SCHEMA_VERSION,
        "cmd": "show_passage",
        "passage_id": passage["passage_id"],
        "title": passage.get("title", ""),
        "sentences": [" ".join(words) for _, words in sorted(sentences.items())],
        "arl": passage["arl_level"],
    }


def message_for(action: Action, word_clip_id: Callable[[int], str]) -> dict | None:
    """The data-channel message for a machine action, or None if it is not one. Showing
    the passage needs the passage itself, so the driver builds that with show_passage."""
    match action:
        case PlayClip(clip_id=clip_id):
            return {"schema_version": SCHEMA_VERSION, "cmd": "play", "clip_id": clip_id}
        case PlayWordClip(word_index=word_index):
            return {
                "schema_version": SCHEMA_VERSION,
                "cmd": "play",
                "clip_id": word_clip_id(word_index),
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
