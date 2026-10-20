"""Core's Pub/Sub push endpoint: each event type reaches its handler (SDD 11)."""

import base64
import logging

import aloai_contracts
import pytest
from aloai_events import MemoryPublisher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.core.api import events_router
from services.core.coach.plan import plan_path
from services.core.grader import paths
from services.core.tests.support import (
    SESSION_ID,
    add_telemetry,
    coach_store,
    contract,
    event,
    events,
    pushed,
    seeded_store,
    session_done,
)


def client(store=None):
    store, publisher = store or seeded_store(), MemoryPublisher()
    app = FastAPI()
    app.include_router(events(store, publisher))
    return TestClient(app), store, publisher


def test_session_done_grades_and_phase1_scored_assembles_the_report():
    http, store, publisher = client()
    done = http.post("/pubsub/session-events", json=pushed(event("session.done", session_done())))
    assert done.status_code == 204
    assert store.get(paths.grading(SESSION_ID)) is not None
    assert store.get(paths.report(SESSION_ID)) is None

    add_telemetry(store)
    scored = {"session_id": SESSION_ID, "telemetry_ref": paths.telemetry(SESSION_ID)}
    response = http.post("/pubsub/session-events", json=pushed(event("phase1.scored", scored)))
    assert response.status_code == 204
    aloai_contracts.READING_REPORT.validate(store.get(paths.report(SESSION_ID)))
    assert [e["type"] for e in publisher.events] == ["report.ready"]


def test_report_ready_starts_the_reading_coach():
    http, store, publisher = client(coach_store())
    ready = contract("event.report_ready.json")
    response = http.post("/pubsub/session-events", json=pushed(ready))
    assert response.status_code == 204
    aloai_contracts.PLAN.validate(store.get(plan_path(SESSION_ID)))
    assert [e["type"] for e in publisher.events] == ["plan.ready"]


def test_other_event_types_are_acknowledged_and_ignored():
    http, _, publisher = client()
    started = {
        "session_id": SESSION_ID,
        "child_ref": "child_demo_001",
        "passage_id": "bank_p3_market_day",
        "context": "SCHOOL",
        "voice_profile_id": "vp_google_v1",
        "voice_mode": "cache_first",
        "session_profile": "demo",
    }
    response = http.post("/pubsub/session-events", json=pushed(event("session.started", started)))
    assert response.status_code == 204
    assert publisher.events == []


def unchecked(**changes) -> dict:
    """A session.done the envelope schema refuses, built by hand as a broken producer would."""
    return pushed(event("session.done", session_done()) | changes)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": {"data": "not base64!"}},
        {"message": {"data": base64.b64encode(b"not json").decode()}},
        unchecked(data={"session_id": SESSION_ID}),
        unchecked(type="teacher.asked"),
        unchecked(schema_version=1),
    ],
    ids=["no message", "not base64", "not json", "missing fields", "unknown type", "old version"],
)
def test_a_push_that_is_not_a_valid_event_is_acknowledged_and_dropped(body, caplog):
    http, store, _ = client()
    with caplog.at_level(logging.WARNING):
        assert http.post("/pubsub/session-events", json=body).status_code == 204
    assert "not a valid event" in caplog.text
    assert store.get(paths.grading(SESSION_ID)) is None


@pytest.mark.parametrize(
    "spoil, error",
    [
        (lambda store: store.docs.pop(paths.session(SESSION_ID)), "LookupError"),
        (lambda store: store.docs.pop("passages/bank_l3_rain"), "LookupError"),
    ],
)
def test_a_session_that_can_never_be_graded_is_parked_and_acknowledged(spoil, error, caplog):
    http, store, _ = client()
    spoil(store)
    with caplog.at_level(logging.ERROR):
        done = http.post(
            "/pubsub/session-events", json=pushed(event("session.done", session_done()))
        )
    assert done.status_code == 204
    parked = store.get(f"sessions/{SESSION_ID}/errors/session.done")
    assert (parked["error"], parked["event_id"]) == (
        error,
        event("session.done", session_done())["event_id"],
    )
    assert f"parked session.done at sessions/{SESSION_ID}/errors/session.done" in caplog.text


def test_an_answer_turn_with_no_item_is_parked():
    http, store, _ = client()
    done = session_done()
    done["turn_audio_uris"].append(done["turn_audio_uris"][3] | {"turn_id": "turn_099", "index": 2})
    assert (
        http.post("/pubsub/session-events", json=pushed(event("session.done", done))).status_code
        == 204
    )
    assert store.get(f"sessions/{SESSION_ID}/errors/session.done")["error"] == "TurnMismatch"


def test_a_failure_that_may_pass_on_retry_is_left_to_pub_sub():
    store = seeded_store()

    class Down:
        def handle(self, data):
            raise ConnectionError("Firestore is unavailable")

    app = FastAPI()
    app.include_router(events_router(Down(), None, None, store))
    http = TestClient(app, raise_server_exceptions=False)
    response = http.post(
        "/pubsub/session-events", json=pushed(event("session.done", session_done()))
    )
    assert response.status_code == 500
    assert store.get(f"sessions/{SESSION_ID}/errors/session.done") is None
