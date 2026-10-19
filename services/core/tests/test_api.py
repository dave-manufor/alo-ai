"""The Grader's HTTP routes: the quick endpoint and the Pub/Sub push endpoint (SDD 11)."""

import base64

import aloai_contracts
import pytest
from aloai_events import MemoryPublisher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.core.grader import paths
from services.core.grader.api import router
from services.core.grader.asr import FixtureTranscriber
from services.core.grader.final import FinalGrader
from services.core.grader.models import GradingError
from services.core.grader.quick import QuickGrader
from services.core.tests.support import (
    RECORDED,
    SESSION_ID,
    RecordedModel,
    add_telemetry,
    assembler,
    event,
    pushed,
    quick_request,
    seeded_store,
    session_done,
)

RESPONSE = aloai_contracts.validator("grade_quick_response.schema.json")


class BrokenModel:
    def grade(self, task):
        raise GradingError("the model timed out")


def client(model=None):
    store, publisher = seeded_store(), MemoryPublisher()
    model = model or RecordedModel()
    reports = assembler(store, publisher)
    app = FastAPI()
    app.include_router(
        router(
            QuickGrader(store, model),
            FinalGrader(store, model, FixtureTranscriber(RECORDED / "asr"), reports),
            reports,
        )
    )
    return TestClient(app), store, publisher


def test_a_quick_turn_is_scored():
    http, _, _ = client()
    response = http.post("/v1/grade:quick", json=quick_request("RETELL", 0, "ada went to market"))
    assert response.status_code == 200
    RESPONSE.validate(response.json())


@pytest.mark.parametrize(
    "body, status, code, retryable",
    [
        (quick_request("READING", 0, "x"), 400, "INVALID_REQUEST", False),
        ([1, 2], 400, "INVALID_REQUEST", False),
        (quick_request("RETELL", 0, "x") | {"passage_id": "nope"}, 404, "PASSAGE_NOT_FOUND", False),
        (quick_request("QUESTION", 2, "x"), 400, "UNKNOWN_ITEM", False),
    ],
)
def test_quick_errors_use_the_sdd_shape(body, status, code, retryable):
    http, _, _ = client()
    response = http.post("/v1/grade:quick", json=body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is retryable
    RESPONSE.validate(response.json())


def test_a_model_failure_can_be_retried():
    http, _, _ = client(BrokenModel())
    response = http.post("/v1/grade:quick", json=quick_request("RETELL", 0, "ada went to market"))
    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "GRADING_FAILED",
        "message": "the model timed out",
        "retryable": True,
    }


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
