"""The Reading Scorer's push subscription (SDD 11) and its start-up guard."""

import base64
import json
import logging

import aloai_env
import pytest
from aloai_events import MemoryPublisher, envelope
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.reading_scorer.api import router
from services.reading_scorer.main import create_app
from services.reading_scorer.scorer import telemetry_path
from services.reading_scorer.tests.support import NOW, SESSION_ID, recorded, scorer, seeded_store


def push(event: dict) -> dict:
    return {"message": {"data": base64.b64encode(json.dumps(event).encode()).decode()}}


def pushed(event_type: str, data: dict) -> dict:
    return push(envelope(event_type, SESSION_ID, data, now=NOW))


def unchecked(event_type: str, data: dict) -> dict:
    """A push the envelope schema refuses, built by hand as a broken producer would."""
    scored = {"session_id": SESSION_ID, "telemetry_ref": telemetry_path(SESSION_ID)}
    return push(
        envelope("phase1.scored", SESSION_ID, scored, now=NOW) | {"type": event_type, "data": data}
    )


def client():
    store, publisher = seeded_store(), MemoryPublisher()
    app = FastAPI()
    app.include_router(router(scorer(store, publisher)))
    return TestClient(app), store, publisher


def test_phase1_recorded_is_scored():
    http, store, publisher = client()
    response = http.post("/pubsub/session-events", json=pushed("phase1.recorded", recorded()))
    assert response.status_code == 204
    assert store.get(telemetry_path(SESSION_ID))["words_attempted"] == 23
    assert [event["type"] for event in publisher.events] == ["phase1.scored"]


def test_other_event_types_are_acknowledged_and_ignored():
    http, _, publisher = client()
    scored = {"session_id": SESSION_ID, "telemetry_ref": telemetry_path(SESSION_ID)}
    assert (
        http.post("/pubsub/session-events", json=pushed("phase1.scored", scored)).status_code == 204
    )
    assert publisher.events == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": {"data": "%%%"}},
        unchecked("phase1.recorded", {"session_id": SESSION_ID}),
        unchecked("teacher.asked", {"session_id": SESSION_ID}),
    ],
    ids=["no message", "not base64", "phase1.recorded without its fields", "unknown type"],
)
def test_a_push_that_is_not_a_valid_event_is_acknowledged_and_dropped(body, caplog):
    http, _, publisher = client()
    with caplog.at_level(logging.WARNING):
        assert http.post("/pubsub/session-events", json=body).status_code == 204
    assert "not a valid event" in caplog.text
    assert publisher.events == []


def test_a_recording_that_can_never_be_scored_is_parked_and_acknowledged(caplog):
    http, store, publisher = client()
    del store.docs["passages/bank_p3_market_day"]
    with caplog.at_level(logging.ERROR):
        response = http.post("/pubsub/session-events", json=pushed("phase1.recorded", recorded()))
    assert response.status_code == 204
    parked = store.get(f"sessions/{SESSION_ID}/errors/phase1.recorded")
    assert (parked["type"], parked["error"]) == ("phase1.recorded", "LookupError")
    assert "LookupError" in caplog.text and "passages/" not in caplog.text
    assert publisher.events == []


def test_the_scorer_refuses_to_start_with_local_shortcuts_on_cloud_run():
    with pytest.raises(aloai_env.ConfigError):
        create_app({"ALO_ENV": "local", "K_SERVICE": "aloai-reading-scorer"})


def test_told_waits_that_cannot_fit_are_parked_not_retried():
    http, store, publisher = client()
    told = recorded(told_token_indices=[3, 6, 9, 12])
    response = http.post("/pubsub/session-events", json=pushed("phase1.recorded", told))
    assert response.status_code == 204
    assert store.get(f"sessions/{SESSION_ID}/errors/phase1.recorded")["error"] == "ValueError"
    assert publisher.events == []
