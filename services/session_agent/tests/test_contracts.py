"""Contract tests: every fixture in fixtures/contracts/ validates against its schema.

Schemas live in schemas/ (PRD 14.2). Cross-file $refs resolve by file name.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures" / "contracts"

REGISTRY = Registry().with_resources(
    (path.name, Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.schema.json")
)


def _load(path: Path):
    return json.loads(path.read_text())


def _validator(schema_file: str) -> Draft202012Validator:
    return Draft202012Validator(
        _load(SCHEMAS / schema_file), registry=REGISTRY, format_checker=FormatChecker()
    )


def _fixture(name: str):
    return _load(FIXTURES / name)


EVENT_FIXTURES = [
    "event.session_started.json",
    "event.phase1_recorded.json",
    "event.session_done.json",
]


@pytest.mark.parametrize("name", EVENT_FIXTURES)
def test_event_fixtures_validate(name):
    _validator("event_envelope.schema.json").validate(_fixture(name))


@pytest.mark.parametrize("name", EVENT_FIXTURES)
def test_event_type_matches_data_shape(name):
    # An event whose data belongs to another type must be rejected.
    event = _fixture(name)
    other = {
        "session.started": "phase1.recorded",
        "phase1.recorded": "session.done",
        "session.done": "session.started",
    }[event["type"]]
    event["type"] = other
    assert not _validator("event_envelope.schema.json").is_valid(event)


@pytest.mark.parametrize("name", ["session_record.session.json", "session_record.turn.json"])
def test_session_record_fixtures_validate(name):
    _validator("session_record.schema.json").validate(_fixture(name))


def test_session_protocol_fixture_messages_validate():
    validator = _validator("session_protocol.schema.json")
    messages = _fixture("session_protocol.json")
    for message in messages:
        validator.validate(message)
    assert {m["cmd"] for m in messages} == {
        "clip_list",
        "play",
        "show_passage",
        "hide_passage",
        "reconnecting",
        "played",
        "missing",
    }


def test_every_schema_has_a_fixture():
    # Each schema file must be exercised by at least one fixture above.
    covered = {
        "event_envelope.schema.json",
        "session_started.schema.json",
        "phase1_recorded.schema.json",
        "session_done.schema.json",
        "session_record.schema.json",
        "session_protocol.schema.json",
    }
    assert {p.name for p in SCHEMAS.glob("*.schema.json")} == covered


def test_unknown_field_is_rejected():
    event = _fixture("event.phase1_recorded.json")
    event["data"]["child_name"] = "not allowed"
    assert not _validator("event_envelope.schema.json").is_valid(event)


def test_bad_schema_version_is_rejected():
    event = _fixture("event.session_done.json")
    event["schema_version"] = 2
    assert not _validator("event_envelope.schema.json").is_valid(event)


def test_non_uuid_event_id_is_rejected():
    event = _fixture("event.session_started.json")
    event["event_id"] = "not-a-uuid"
    assert not _validator("event_envelope.schema.json").is_valid(event)


def test_voice_mode_cannot_be_invented():
    record = copy.deepcopy(_fixture("session_record.session.json"))
    record["voice_mode"] = "browser_choice"
    assert not _validator("session_record.schema.json").is_valid(record)


def test_audio_uri_must_be_gcs():
    event = _fixture("event.phase1_recorded.json")
    event["data"]["audio_uri"] = "https://example.com/a.flac"
    assert not _validator("event_envelope.schema.json").is_valid(event)


def test_protocol_message_with_extra_field_is_rejected():
    message = {"schema_version": 1, "cmd": "play", "clip_id": "x", "score": 90}
    assert not _validator("session_protocol.schema.json").is_valid(message)
