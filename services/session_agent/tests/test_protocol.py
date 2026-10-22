import json
from pathlib import Path

import pytest
from services.session_agent import protocol
from services.session_agent.machine.types import (
    ClipAck,
    HidePassage,
    Phase,
    PlayClip,
    PlayWordClip,
    ShowPassage,
    ShowReconnecting,
    SpeakLive,
    StopRecording,
)

CONTRACTS = Path(__file__).resolve().parents[3] / "fixtures" / "contracts"


def word_clip(index: int) -> str:
    return f"word_{index}"


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (PlayClip("retell_prompt"), {"cmd": "play", "clip_id": "retell_prompt"}),
        (PlayWordClip(4), {"cmd": "play", "clip_id": "word_4"}),
        (HidePassage(), {"cmd": "hide_passage"}),
        (ShowReconnecting(), {"cmd": "reconnecting"}),
    ],
)
def test_actions_become_schema_valid_messages(action, expected, validate):
    message = protocol.message_for(action, word_clip)
    assert message == {"schema_version": 3, **expected}
    validate("session_protocol.schema.json", message)


@pytest.mark.parametrize("speaking", [True, False])
def test_child_speaking_is_a_schema_valid_message_with_no_words_in_it(speaking, validate):
    message = protocol.child_speaking(speaking)
    assert message == {"schema_version": 3, "cmd": "child_speaking", "speaking": speaking}
    validate("session_protocol.schema.json", message)


@pytest.mark.parametrize("action", [StopRecording(), SpeakLive("retell_prompt"), ShowPassage("p1")])
def test_other_actions_are_not_data_channel_messages(action):
    assert protocol.message_for(action, word_clip) is None


def test_clip_list_is_schema_valid(validate):
    message = protocol.clip_list(
        [
            ("retell_prompt", "https://x/retell_prompt.mp3", "Tell me the story."),
            ("listening_story", "https://x/story.mp3", None),
        ]
    )
    assert message["clips"] == [
        {
            "clip_id": "retell_prompt",
            "url": "https://x/retell_prompt.mp3",
            "text": "Tell me the story.",
        },
        {"clip_id": "listening_story", "url": "https://x/story.mp3", "text": None},
    ]
    validate("session_protocol.schema.json", message)
    validate("session_protocol.schema.json", protocol.clip_list([]))


@pytest.mark.parametrize("phase", sorted(protocol.STEPS, key=lambda p: p.value))
def test_each_task_has_a_schema_valid_step(validate, phase):
    message = protocol.step(phase)
    assert message == {"schema_version": 3, "cmd": "step", "step": phase.value}
    validate("session_protocol.schema.json", message)


@pytest.mark.parametrize("phase", [Phase.INIT, Phase.TRANSITION])
def test_phases_without_a_screen_send_no_step(phase):
    assert protocol.step(phase) is None


def test_show_passage_carries_the_story_and_no_answer_keys(validate):
    passage = json.loads((CONTRACTS / "passage.bank_p3_market_day.json").read_text())
    message = protocol.show_passage(passage)
    validate("session_protocol.schema.json", message)
    assert message["title"] == "Market Day" and message["arl"] == 3
    assert message["sentences"] == [
        "Ada and Mama went to the market.",
        "Ada saw a red hat.",
        "It cost too much.",
        "Ada smiled and chose a blue hat.",
    ]
    assert " ".join(message["sentences"]) == passage["text_content"]
    assert set(message) == {"schema_version", "cmd", "passage_id", "title", "sentences", "arl"}


def test_encode_is_compact_json():
    assert protocol.encode({"a": 1, "b": "x"}) == b'{"a":1,"b":"x"}'


@pytest.mark.parametrize(
    "raw", [b'{"cmd":"played","clip_id":"c1"}', '{"cmd":"played","clip_id":"c1"}']
)
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
