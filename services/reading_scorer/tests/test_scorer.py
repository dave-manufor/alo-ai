"""Phase 1 scoring end to end on the recorded transcripts (PRD 5.3, 10.2)."""

import aloai_contracts
from aloai_events import MemoryPublisher
from services.reading_scorer.scorer import telemetry_path
from services.reading_scorer.tests.support import (
    NOW,
    SESSION_ID,
    TELEMETRY,
    recorded,
    scorer,
    seeded_store,
)
from services.reading_scorer.transcribers import FixtureReading
from services.reading_scorer.words import Heard


class Silence:
    def heard(self, audio_uri, passage):
        return []


def test_the_recorded_reading_gives_the_contract_telemetry():
    store, publisher = seeded_store(), MemoryPublisher()
    scorer(store, publisher).handle(recorded())
    assert store.get(telemetry_path(SESSION_ID)) == TELEMETRY


def test_scoring_announces_phase1_scored():
    publisher = MemoryPublisher()
    scorer(seeded_store(), publisher).handle(recorded())
    [event] = publisher.events
    aloai_contracts.EVENT_ENVELOPE.validate(event)
    assert event["type"] == "phase1.scored"
    assert event["occurred_at"] == NOW.isoformat().replace("+00:00", "Z")
    assert event["data"] == {
        "session_id": SESSION_ID,
        "telemetry_ref": f"sessions/{SESSION_ID}/phase1/telemetry",
    }


def test_a_redelivered_event_is_not_scored_again():
    store, publisher = seeded_store(), MemoryPublisher()
    reading = scorer(store, publisher)
    reading.handle(recorded())
    store.merge(telemetry_path(SESSION_ID), {"flags": ["marker"]})
    reading.handle(recorded())
    assert store.get(telemetry_path(SESSION_ID))["flags"] == ["marker"]
    assert len(publisher.events) == 2
    assert reading.audio.loaded == [recorded()["audio_uri"]]


def test_only_the_words_reached_are_aligned():
    store = seeded_store()
    timing_scorer = scorer(store, MemoryPublisher())
    timing_scorer.handle(recorded())
    [words] = timing_scorer.aligner.aligned
    assert len(words) == 23
    assert words[:3] == ["ada", "and", "mama"]


def test_a_silent_reading_attempts_nothing():
    store = seeded_store()
    silent = scorer(store, MemoryPublisher(), chirp=Silence(), gemini=Silence())
    silent.handle(recorded(told_token_indices=[]))
    telemetry = store.get(telemetry_path(SESSION_ID))
    aloai_contracts.PHASE1_TELEMETRY.validate(telemetry)
    assert (telemetry["words_attempted"], telemetry["accuracy_pct"], telemetry["wcpm"]) == (
        0,
        None,
        None,
    )
    assert telemetry["word_events"] == []
    assert telemetry["prosody"]["reported"] is False


def test_a_reading_stopped_part_way_counts_only_what_was_reached(tmp_path):
    first_sentence = [["ada", 0.95], ["and", 0.95], ["mama", 0.95], ["went", 0.95]]
    for engine in ("chirp", "gemini"):
        (tmp_path / f"a1b2c3d4-0000-4000-8000-000000000001.{engine}.json").write_text(
            '{"words": ' + str(first_sentence).replace("'", '"') + "}"
        )
    store = seeded_store()
    scorer(
        store,
        MemoryPublisher(),
        chirp=FixtureReading(tmp_path, "chirp"),
        gemini=FixtureReading(tmp_path, "gemini"),
    ).handle(recorded(told_token_indices=[]))
    telemetry = store.get(telemetry_path(SESSION_ID))
    assert telemetry["words_attempted"] == 4
    assert telemetry["error_counts"]["omission"] == 0
    assert telemetry["accuracy_pct"] == 100.0


def test_what_each_transcript_heard_is_kept_for_review():
    store = seeded_store()
    scorer(store, MemoryPublisher(), gemini=Silence()).handle(recorded())
    events = store.get(telemetry_path(SESSION_ID))["word_events"]
    assert {e["label"] for e in events} <= {"UNCERTAIN", "TOLD"}
    assert events[0]["chirp_hypothesis"] == "ada"
    assert events[0]["gemini_hypothesis"] is None
    assert Heard("ada").confidence is None
