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
        "passage.schema.json",
        "grade_quick_request.schema.json",
        "grade_quick_response.schema.json",
        "phase1_telemetry.schema.json",
        "grader_output.schema.json",
        "reading_report.schema.json",
        "phase1_scored.schema.json",
        "report_ready.schema.json",
        "plan_ready.schema.json",
        "plan.schema.json",
        "topic_tag.schema.json",
        "passage_generate_request.schema.json",
        "passage_generate_response.schema.json",
        "story_request.schema.json",
        "book.schema.json",
    }
    assert {p.name for p in SCHEMAS.glob("*.schema.json")} == covered


PASSAGE_FIXTURES = ["passage.bank_p3_market_day.json", "passage.bank_l3_rain.json"]


@pytest.mark.parametrize("name", PASSAGE_FIXTURES)
def test_passage_fixture_validates(name):
    _validator("passage.schema.json").validate(_fixture(name))


@pytest.mark.parametrize("name", PASSAGE_FIXTURES)
def test_passage_fixture_is_consistent(name):
    passage = _fixture(name)
    tokens = passage["tokens"]
    assert [t["token_index"] for t in tokens] == list(range(len(tokens)))
    assert passage["word_count"] == len(tokens)
    assert " ".join(t["text"] for t in tokens) == passage["text_content"]
    sentences = sorted({t["sentence_index"] for t in tokens})
    assert sentences == list(range(len(sentences)))
    # Each sentence ends on its last token with TERMINAL, and nowhere else.
    for token, following in zip(tokens, [*tokens[1:], None], strict=True):
        ends = following is None or following["sentence_index"] != token["sentence_index"]
        assert (token["syntactic_boundary_after"] == "TERMINAL") == ends
    assert all(p["sentence_index"] < len(sentences) for p in passage["propositions"])
    assert all(i["target_sentence_index"] < len(sentences) for i in passage["items"])
    assert [i["order"] for i in passage["items"]] == list(range(1, len(passage["items"]) + 1))


def test_fixtures_describe_one_session():
    read = _fixture("passage.bank_p3_market_day.json")
    listen = _fixture("passage.bank_l3_rain.json")
    record = _fixture("session_record.session.json")
    started = _fixture("event.session_started.json")["data"]
    recorded = _fixture("event.phase1_recorded.json")["data"]
    done = _fixture("event.session_done.json")["data"]
    assert (
        read["paired_listening_passage_id"] == listen["passage_id"] == done["listening_passage_id"]
    )
    assert listen["mode"] == "LISTEN"
    assert read["passage_id"] == record["passage_id"] == recorded["passage_id"]
    assert read["passage_id"] == started["passage_id"] == done["passage_id"]
    assert all(0 <= i < len(read["tokens"]) for i in recorded["told_token_indices"])
    assert read["length_profile"] == "DEMO"
    assert record["session_profile"] == started["session_profile"] == "demo"
    assert done["session_settings"]["session_profile"] == "demo"
    assert read["voice_profile_id"] == record["voice_profile_id"] == started["voice_profile_id"]
    questions = sorted(t["index"] for t in done["turn_audio_uris"] if t["phase"] == "QUESTION")
    assert questions == list(range(len(read["items"])))
    heard = [t["index"] for t in done["turn_audio_uris"] if t["phase"] == "LISTENING_QUESTION"]
    assert heard == list(range(len(listen["items"])))


@pytest.mark.parametrize(
    ("name", "items", "valid"),
    [
        ("passage.bank_l3_rain.json", 1, True),
        ("passage.bank_l3_rain.json", 0, False),
        ("passage.bank_p3_market_day.json", 2, True),
        ("passage.bank_p3_market_day.json", 1, False),
    ],
)
def test_a_listening_passage_may_have_one_item_and_a_reading_passage_needs_two(name, items, valid):
    passage = _fixture(name)
    passage["items"] = passage["items"][:items]
    assert _validator("passage.schema.json").is_valid(passage) is valid


def test_a_reading_passage_names_its_listening_passage():
    passage = _fixture("passage.bank_p3_market_day.json")
    del passage["paired_listening_passage_id"]
    assert not _validator("passage.schema.json").is_valid(passage)


def test_session_done_names_the_listening_passage_only_when_it_ran():
    validator = _validator("event_envelope.schema.json")
    event = _fixture("event.session_done.json")
    del event["data"]["listening_passage_id"]
    assert not validator.is_valid(event)
    event["data"]["listening_module_run"] = False
    assert validator.is_valid(event)
    event["data"]["listening_passage_id"] = "bank_l3_rain"
    assert not validator.is_valid(event)


@pytest.mark.parametrize("field", ["index", "part"])
def test_every_turn_says_which_item_and_part_it_is(field):
    event = _fixture("event.session_done.json")
    del event["data"]["turn_audio_uris"][0][field]
    assert not _validator("event_envelope.schema.json").is_valid(event)
    turn = _fixture("session_record.turn.json")
    del turn[field]
    assert not _validator("session_record.schema.json").is_valid(turn)


def test_book_fixture_validates():
    _validator("book.schema.json").validate(_fixture("book.sample.json"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("arl", 13),
        ("topic_tags", ["dinosaurs"]),
        ("embedding", [0.1, 0.2]),
        ("embedding_model", "some-other-model"),
        ("file_hash", "not-a-hash"),
        ("raw_uri", "https://example.org/book.pdf"),
        ("child_name", "not allowed"),
    ],
)
def test_book_with_a_bad_field_is_rejected(field, value):
    book = {**_fixture("book.sample.json"), field: value}
    assert not _validator("book.schema.json").is_valid(book)


@pytest.mark.parametrize("field", ["licence", "attribution", "author", "held_for_review"])
def test_a_book_must_say_its_licence_attribution_author_and_review_state(field):
    book = _fixture("book.sample.json")
    del book[field]
    assert not _validator("book.schema.json").is_valid(book)


def test_passage_with_an_unknown_field_is_rejected():
    passage = _fixture("passage.bank_p3_market_day.json")
    passage["tokens"][0]["child_name"] = "not allowed"
    assert not _validator("passage.schema.json").is_valid(passage)


def test_passage_needs_four_propositions():
    passage = _fixture("passage.bank_p3_market_day.json")
    passage["propositions"] = passage["propositions"][:3]
    assert not _validator("passage.schema.json").is_valid(passage)


def test_unknown_field_is_rejected():
    event = _fixture("event.phase1_recorded.json")
    event["data"]["child_name"] = "not allowed"
    assert not _validator("event_envelope.schema.json").is_valid(event)


@pytest.mark.parametrize(
    ("name", "version"),
    [
        ("event.session_done.json", 1),
        ("event.session_done.json", 3),
        ("event.phase1_recorded.json", 2),
        ("event.session_started.json", 2),
    ],
)
def test_bad_schema_version_is_rejected(name, version):
    event = _fixture(name)
    event["schema_version"] = version
    assert not _validator("event_envelope.schema.json").is_valid(event)


def test_short_reading_is_not_a_session_agent_flag():
    record = _fixture("session_record.session.json")
    record["flags"] = ["SHORT_READING"]
    assert not _validator("session_record.schema.json").is_valid(record)


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


def test_generator_request_and_response_fixtures_validate():
    _validator("passage_generate_request.schema.json").validate(
        _fixture("passage_generate.request.json")
    )
    _validator("passage_generate_response.schema.json").validate(
        _fixture("passage_generate.response.json")
    )


@pytest.mark.parametrize("name", ["story_request.queued.json", "story_request.done.json"])
def test_story_request_fixtures_validate(name):
    _validator("story_request.schema.json").validate(_fixture(name))


def test_every_topic_tag_validates_and_the_fixture_lists_them_all():
    validator = _validator("topic_tag.schema.json")
    tags = _fixture("topic_tags.json")
    assert len(tags) == 12
    assert all(validator.is_valid(tag) for tag in tags)
    assert tags == _load(SCHEMAS / "topic_tag.schema.json")["enum"]


@pytest.mark.parametrize("tag", ["dyslexia", "Animals", "food and cooking", "", None])
def test_a_tag_outside_the_taxonomy_is_rejected(tag):
    assert not _validator("topic_tag.schema.json").is_valid(tag)


@pytest.mark.parametrize(
    "change",
    [
        {"tags": ["animals", "space", "music"]},
        {"tags": ["animals", "animals"]},
        {"tags": ["dyslexia"]},
        {"detail": "Goat"},
        {"detail": "a very small goat"},
        {"target_arl": 13},
        {"length_profile": "SHORT"},
        {"deadline_ms": 0},
        {"child_name": "not allowed"},
    ],
)
def test_a_bad_generate_request_is_rejected(change):
    request = {**_fixture("passage_generate.request.json"), **change}
    assert not _validator("passage_generate_request.schema.json").is_valid(request)


@pytest.mark.parametrize("field", ["detail", "genre_hint"])
def test_the_optional_request_fields_may_be_left_out(field):
    request = _fixture("passage_generate.request.json")
    del request[field]
    assert _validator("passage_generate_request.schema.json").is_valid(request)


@pytest.mark.parametrize("change", [{"attempts": 3}, {"attempts": 0}, {"score": 90}])
def test_a_bad_generate_response_is_rejected(change):
    response = {**_fixture("passage_generate.response.json"), **change}
    assert not _validator("passage_generate_response.schema.json").is_valid(response)


@pytest.mark.parametrize(
    "change",
    [
        {"tags": []},
        {"tags": ["food", "food"]},
        {"tags": ["food", "music", "space"]},
        {"status": "OK"},
    ],
)
def test_a_bad_story_request_is_rejected(change):
    request = {**_fixture("story_request.queued.json"), **change}
    assert not _validator("story_request.schema.json").is_valid(request)


def test_a_pre_generated_passage_never_reuses_an_id_in_the_same_session():
    request = _fixture("story_request.done.json")
    in_session = _fixture("passage_generate.response.json")["passage_id"]
    assert request["passage_id"] == f"gen_next_{request['session_id']}"
    assert request["passage_id"] not in (f"story_{request['session_id']}", in_session)
