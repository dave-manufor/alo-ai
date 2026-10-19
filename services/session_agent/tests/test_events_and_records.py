import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from services.session_agent import session_store
from services.session_agent.events import (
    MemoryPublisher,
    SessionContext,
    build_event,
)
from services.session_agent.machine import initial_state, step
from services.session_agent.machine.types import (
    EmitEvent,
    MicResult,
    PassageReady,
    QuickScore,
    ReadingDone,
    ReadingProgress,
    Silence,
    Start,
    StartRecording,
    Timer,
    TurnEnd,
)
from services.session_agent.recording import AudioLog

SESSION_UUID = "3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10"
CTX = SessionContext(
    session_id="sess_demo_001",
    child_ref="child_demo_001",
    context="SCHOOL",
    voice_profile_id="vp_google_v1",
    capture_mode="LIVE",
)
NOW = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)


def counting_uuids():
    count = iter(range(1, 1000))
    return lambda: uuid.UUID(f"a1b2c3d4-0000-4000-8000-{next(count):012d}")


def audio_log():
    return AudioLog("aloai-dev-audio", SESSION_UUID, counting_uuids())


# ---- audio log


def test_turns_are_numbered_and_named_by_uuid_v4():
    log = audio_log()
    first = log.new_turn("READING")
    second = log.new_turn("RETELL")
    assert (first.turn_id, second.turn_id) == ("turn_001", "turn_002")
    assert first.audio_uri == (
        f"gs://aloai-dev-audio/{SESSION_UUID}/READING/a1b2c3d4-0000-4000-8000-000000000001.flac"
    )
    assert log.turns == (first, second)


def test_default_ids_are_random_uuid_v4():
    log = AudioLog("b", SESSION_UUID)
    name = log.new_turn("READING").audio_uri.rsplit("/", 1)[1].removesuffix(".flac")
    assert uuid.UUID(name).version == 4


def test_session_folder_must_be_a_uuid_v4():
    with pytest.raises(ValueError, match="UUID v4"):
        AudioLog("b", str(uuid.uuid1()))


def test_reading_uri_is_the_latest_reading_turn():
    log = audio_log()
    assert log.reading_uri() is None
    log.new_turn("MIC_CHECK")
    first = log.new_turn("READING")
    assert log.reading_uri() == first.audio_uri
    second = log.new_turn("READING")
    assert log.reading_uri() == second.audio_uri


def test_repeated_recordings_of_one_item_are_numbered_as_parts():
    log = audio_log()
    log.new_turn("RETELL")
    log.new_turn("RETELL")  # "Anything else?"
    log.new_turn("QUESTION", 0)
    log.new_turn("QUESTION", 0)  # a repeat request
    log.new_turn("QUESTION", 1)
    assert [(t["phase"], t["index"], t["part"]) for t in log.turn_audio_uris()] == [
        ("RETELL", 0, 0),
        ("RETELL", 0, 1),
        ("QUESTION", 0, 0),
        ("QUESTION", 0, 1),
        ("QUESTION", 1, 0),
    ]


def test_turn_audio_uris_are_schema_valid(validate):
    log = audio_log()
    log.new_turn("READING")
    log.new_turn("QUESTION", 1)
    assert [t["phase"] for t in log.turn_audio_uris()] == ["READING", "QUESTION"]
    validate(
        "event_envelope.schema.json",
        {
            "event_id": str(uuid.uuid4()),
            "type": "session.done",
            "schema_version": 2,
            "occurred_at": "2026-01-15T09:00:00Z",
            "session_id": "s",
            "data": {
                "session_id": "s",
                "passage_id": "p1",
                "turn_audio_uris": log.turn_audio_uris(),
                "capture_mode": "LIVE",
                "session_settings": {"voice_mode": "cache_first", "session_profile": "standard"},
                "flags": [],
                "reading_stopped_early": False,
                "listening_module_run": False,
            },
        },
    )


# ---- events


def test_phase1_recorded_needs_a_recorded_reading():
    emit = EmitEvent("phase1.recorded", {"passage_id": "p1", "told_token_indices": []})
    with pytest.raises(ValueError, match="reading turn"):
        build_event(emit, CTX, audio_log(), event_id=str(uuid.uuid4()), now=NOW)


def test_event_time_is_written_in_utc():
    log = audio_log()
    log.new_turn("READING")
    emit = EmitEvent("phase1.recorded", {"passage_id": "p1", "told_token_indices": [2]})
    lagos = timezone(timedelta(hours=1))
    event = build_event(
        emit, CTX, log, event_id=str(uuid.uuid4()), now=datetime(2026, 1, 15, 10, 0, tzinfo=lagos)
    )
    assert event["occurred_at"] == "2026-01-15T09:00:00Z"


def test_publisher_collects_events():
    publisher = MemoryPublisher()
    publisher.publish({"a": 1})
    assert publisher.events == [{"a": 1}]


# ---- Firestore records


def test_session_record_is_schema_valid(validate):
    record = session_store.session_record(
        CTX,
        child_id="child_demo_001",
        status="COMPLETE",
        voice_mode="cache_first",
        session_profile="standard",
        passage_id="bank_p3_market_day",
        passage_source="BANK",
        flags=("LIVE_FALLBACK",),
        created_at=NOW,
    )
    assert record["flags"] == ["LIVE_FALLBACK"] and record["created_at"] == "2026-01-15T09:00:00Z"
    validate("session_record.schema.json", record)


def test_turn_record_is_schema_valid(validate):
    turn = audio_log().new_turn("QUESTION", 2)
    record = session_store.turn_record(turn, asr_transcript="the cat sat")
    assert record["live_transcript"] is None
    assert (record["index"], record["part"]) == (2, 0)
    validate("session_record.schema.json", record)


def test_document_paths_and_memory_documents():
    assert session_store.session_path("s1") == "sessions/s1"
    assert session_store.turn_path("s1", "turn_001") == "sessions/s1/turns/turn_001"
    docs = session_store.MemoryDocuments()
    docs.set("sessions/s1", {"a": 1})
    assert docs.docs == {"sessions/s1": {"a": 1}}


# ---- the machine's real output satisfies the contracts


def drive(state, event, log, publisher, validate):
    """Run one event; record a turn per StartRecording; publish and validate each event."""
    state, actions = step(state, event)
    for action in actions:
        if isinstance(action, StartRecording):
            log.new_turn(action.turn_phase, action.index)
        elif isinstance(action, EmitEvent):
            built = build_event(action, CTX, log, event_id=str(uuid.uuid4()), now=NOW)
            validate("event_envelope.schema.json", built)
            publisher.publish(built)
    return state


def test_a_full_session_publishes_events_that_match_the_schemas(validate):
    log, publisher = audio_log(), MemoryPublisher()
    state = initial_state("standard", "cache_first")
    for event in [
        Start(),
        TurnEnd("ANSWERED"),
        PassageReady("gen1"),
        MicResult(True),
        Silence(5000, 5),
        Silence(5000, 8),
        ReadingDone(75_000),
    ]:
        state = drive(state, event, log, publisher, validate)
    state = drive(state, Timer(f"transition:{state.task_seq}"), log, publisher, validate)
    # Retell and its follow-up, then the three questions.
    for _ in range(5):
        state = drive(state, TurnEnd("ANSWERED"), log, publisher, validate)
    state = drive(state, QuickScore(False), log, publisher, validate)
    state = drive(state, Timer(f"close:{state.task_seq}"), log, publisher, validate)

    types = [e["type"] for e in publisher.events]
    assert types == ["session.started", "phase1.recorded", "session.done"]
    recorded = publisher.events[1]["data"]
    assert recorded["told_token_indices"] == [5, 8]
    assert recorded["audio_uri"] == log.reading_uri()
    done = publisher.events[2]["data"]
    assert [t["phase"] for t in done["turn_audio_uris"]][:3] == [
        "INTEREST_CHAT",
        "MIC_CHECK",
        "READING",
    ]
    answers = [(t["phase"], t["index"], t["part"]) for t in done["turn_audio_uris"][3:]]
    assert answers == [
        ("RETELL", 0, 0),
        ("RETELL", 0, 1),
        ("QUESTION", 0, 0),
        ("QUESTION", 1, 0),
        ("QUESTION", 2, 0),
    ]
    assert done["passage_id"] == "gen1" and "listening_passage_id" not in done
    assert state.status == "COMPLETE"


def test_a_session_stopped_early_publishes_the_listening_passage(validate):
    log, publisher = audio_log(), MemoryPublisher()
    state = initial_state("demo", "cache_first")
    for event in [
        Start(),
        TurnEnd("ANSWERED"),
        PassageReady("gen1", "listen1"),
        MicResult(True),
        ReadingProgress(30_000, 4),  # the kindness rule ends the reading
    ]:
        state = drive(state, event, log, publisher, validate)
    state = drive(state, Timer(f"listening_story:{state.task_seq}"), log, publisher, validate)
    for _ in range(2):  # the listening retell and the demo's one item
        state = drive(state, TurnEnd("ANSWERED"), log, publisher, validate)
    state = drive(state, Timer(f"close:{state.task_seq}"), log, publisher, validate)

    done = publisher.events[-1]["data"]
    assert done["reading_stopped_early"] is True and done["listening_module_run"] is True
    assert done["listening_passage_id"] == "listen1"
    assert [t["phase"] for t in done["turn_audio_uris"]][-2:] == [
        "LISTENING_RETELL",
        "LISTENING_QUESTION",
    ]
