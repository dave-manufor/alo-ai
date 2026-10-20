"""The Grader's quick endpoint (SDD 11)."""

import aloai_contracts
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import GoogleAPICallError
from services.core.grader.api import router
from services.core.grader.models import GradingError
from services.core.grader.quick import QuickGrader
from services.core.tests.support import RecordedModel, quick_request, seeded_store

RESPONSE = aloai_contracts.validator("grade_quick_response.schema.json")


class BrokenModel:
    def grade(self, task):
        raise GradingError("the model timed out")


def client(model=None):
    app = FastAPI()
    app.include_router(router(QuickGrader(seeded_store(), model or RecordedModel())))
    return TestClient(app)


def test_a_quick_turn_is_scored():
    http = client()
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
    http = client()
    response = http.post("/v1/grade:quick", json=body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is retryable
    RESPONSE.validate(response.json())


def test_a_model_failure_can_be_retried():
    http = client(BrokenModel())
    response = http.post("/v1/grade:quick", json=quick_request("RETELL", 0, "ada went to market"))
    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "GRADING_FAILED",
        "message": "the model timed out",
        "retryable": True,
    }


class Unreachable:
    def grade(self, task):
        raise GoogleAPICallError("Vertex AI is unavailable")


def test_vertex_or_firestore_not_answering_is_a_retryable_503():
    http = client(Unreachable())
    response = http.post("/v1/grade:quick", json=quick_request("RETELL", 0, "ada went to market"))
    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "UPSTREAM_UNAVAILABLE",
        "message": "GoogleAPICallError",
        "retryable": True,
    }
