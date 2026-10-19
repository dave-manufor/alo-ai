"""Core's Pub/Sub push endpoint: each event type reaches its handler (SDD 11)."""

import base64

import aloai_contracts
import pytest
from aloai_events import MemoryPublisher
from fastapi import FastAPI
from fastapi.testclient import TestClient
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


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": {"data": "not base64!"}},
        {"message": {"data": base64.b64encode(b"not json").decode()}},
        pushed(event("session.done", {"session_id": SESSION_ID})),
    ],
)
def test_a_push_without_a_valid_event_is_refused(body):
    http, _, _ = client()
    assert http.post("/pubsub/session-events", json=body).status_code == 400
