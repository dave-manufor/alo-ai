"""The Reading Scorer's push subscription (SDD 11) and its start-up guard."""

import base64
import json

import aloai_env
import pytest
from aloai_events import MemoryPublisher, envelope
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.reading_scorer.api import router
from services.reading_scorer.main import create_app
from services.reading_scorer.scorer import telemetry_path
from services.reading_scorer.tests.support import NOW, SESSION_ID, recorded, scorer, seeded_store


def pushed(event_type: str, data: dict) -> dict:
    event = envelope(
        event_type, SESSION_ID, data, event_id="6f1c2f0e-3a55-4a7e-9d1a-2b8c5e0a1002", now=NOW
    )
    return {"message": {"data": base64.b64encode(json.dumps(event).encode()).decode()}}


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
    [{}, {"message": {"data": "%%%"}}, pushed("phase1.recorded", {"session_id": SESSION_ID})],
)
def test_a_push_without_a_valid_event_is_refused(body):
    http, _, _ = client()
    assert http.post("/pubsub/session-events", json=body).status_code == 400


def test_the_scorer_refuses_to_start_with_local_shortcuts_on_cloud_run():
    with pytest.raises(aloai_env.ConfigError):
        create_app({"ALO_ENV": "local", "K_SERVICE": "aloai-reading-scorer"})
