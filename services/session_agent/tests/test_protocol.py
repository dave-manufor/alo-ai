import json

import pytest
from services.session_agent import protocol
from services.session_agent.machine.types import (
    ClipAck,
    HidePassage,
    PlayClip,
    PlayWordClip,
    ShowPassage,
    ShowReconnecting,
    SpeakLive,
    StopRecording,
)


def word_clip(index: int) -> str:
    return f"word_{index}"


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (PlayClip("retell_prompt"), {"cmd": "play", "clip_id": "retell_prompt"}),
        (PlayWordClip(4), {"cmd": "play", "clip_id": "word_4"}),
        (ShowPassage("p1"), {"cmd": "show_passage", "passage_id": "p1"}),
        (HidePassage(), {"cmd": "hide_passage"}),
        (ShowReconnecting(), {"cmd": "reconnecting"}),
    ],
)
def test_actions_become_schema_valid_messages(action, expected, validate):
    message = protocol.message_for(action, word_clip)
    assert message == {"schema_version": 1, **expected}
    validate("session_protocol.schema.json", message)


@pytest.mark.parametrize("action", [StopRecording(), SpeakLive("retell_prompt")])
def test_other_actions_are_not_data_channel_messages(action):
    assert protocol.message_for(action, word_clip) is None


def test_clip_list_is_schema_valid(validate):
    message = protocol.clip_list([("greeting_1", "https://x/greeting_1.mp3")])
    assert message["clips"] == [{"clip_id": "greeting_1", "url": "https://x/greeting_1.mp3"}]
    validate("session_protocol.schema.json", message)
    validate("session_protocol.schema.json", protocol.clip_list([]))


def test_encode_is_compact_json():
    assert protocol.encode({"a": 1, "b": "x"}) == b'{"a":1,"b":"x"}'


@pytest.mark.parametrize("raw", [b'{"cmd":"played","clip_id":"c1"}', '{"cmd":"played","clip_id":"c1"}'])
def test_played_ack_is_parsed(raw):
    assert protocol.parse_client(raw) == ClipAck("c1", "played")


def test_missing_ack_is_parsed():
    raw = json.dumps({"schema_version": 1, "cmd": "missing", "clip_id": "word_3"})
    assert protocol.parse_client(raw) == ClipAck("word_3", "missing")


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"[1, 2]",
        b'{"cmd":"play","clip_id":"c1"}',
        b'{"cmd":"played"}',
        b'{"cmd":"played","clip_id":""}',
        b'{"cmd":"played","clip_id":7}',
    ],
)
def test_anything_else_from_the_client_is_dropped(raw):
    assert protocol.parse_client(raw) is None
