"""POST /v1/passages:generate (SDD 11): a gated passage, stored once, or an error the
Session Agent answers with its bank passage."""

import aloai_contracts
import httpx
import pytest
import spacy
from aloai_store import MemoryStore
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable
from services.core.generator.models import FixtureModel
from services.core.generator.pipeline import DeadlineExceeded, GateFailed, Generated, Generator
from services.core.generator_api import router
from services.core.tests.support import RECORDED, contract

PATH = "passages/gen_sess_demo_001"


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


class Counting(FixtureModel):
    def __init__(self) -> None:
        super().__init__(RECORDED / "generator")
        self.calls = 0

    def call(self, call):
        self.calls += 1
        return super().call(call)


class Failing:
    """A generator whose every request ends in the given error, or the given result."""

    def __init__(self, outcome) -> None:
        self.outcome = outcome

    def generate(self, request, passage_id, listening_passage_id):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def bank() -> MemoryStore:
    return MemoryStore(
        {
            "passages/bank_l3_rain": contract("passage.bank_l3_rain.json"),
            "passages/bank_p3_market_day": contract("passage.bank_p3_market_day.json"),
        }
    )


def client(generator, store) -> TestClient:
    app = FastAPI()
    app.include_router(router(generator, store))
    return TestClient(app)


def generator(nlp, model=None) -> Generator:
    return Generator(model or Counting(), nlp, "aloai-dev-clips", "v1")


def post(http, **changes):
    return http.post(
        "/v1/passages:generate", json=contract("passage_generate.request.json") | changes
    )


def test_the_contract_request_gets_a_stored_gated_passage(nlp):
    store = bank()
    response = post(client(generator(nlp), store))
    assert response.status_code == 200
    body = response.json()
    assert not list(aloai_contracts.PASSAGE_GENERATE_RESPONSE.iter_errors(body))
    assert body == {
        "schema_version": 1,
        "passage_id": "gen_sess_demo_001",
        "listening_passage_id": "bank_l3_rain",
        "attempts": 1,
        "estimated_arl": 3.88,
    }
    stored = store.get(PATH)
    assert not list(aloai_contracts.PASSAGE.iter_errors(stored))
    assert stored["source"] == "GENERATED" and stored["voice_profile_id"] == "vp_google_v1"


def test_a_repeated_request_returns_the_stored_passage_without_a_model_call(nlp):
    model = Counting()
    http = client(generator(nlp, model), bank())
    first = post(http).json()
    calls = model.calls
    assert post(http).json() == first
    assert model.calls == calls == 4  # the Writer and three Critic calls, once


@pytest.mark.parametrize(
    "changes",
    [
        {"tags": ["cars"]},
        {"transcript": "I like goats"},  # the child's own words never reach the generator
        {"detail": "Big Goat!"},
        {"target_arl": 13},
    ],
)
def test_a_request_outside_the_contract_is_refused(nlp, changes):
    store = bank()
    response = post(client(generator(nlp), store), **changes)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert store.get(PATH) is None


@pytest.mark.parametrize(
    ("error", "status", "code", "retryable"),
    [
        (GateFailed([], 2), 422, "GATE_FAILED", False),
        (DeadlineExceeded("the deadline passed"), 504, "DEADLINE", False),
        (httpx.ConnectError("refused"), 503, "UPSTREAM_UNAVAILABLE", True),
        (ServiceUnavailable("firestore"), 503, "UPSTREAM_UNAVAILABLE", True),
    ],
)
def test_no_passage_is_an_error_and_never_a_bank_passage(error, status, code, retryable):
    store = bank()
    response = post(client(Failing(error), store))
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is retryable
    assert "passage_id" not in response.json()
    assert store.get(PATH) is None


def test_no_listening_passage_for_the_profile(nlp):
    store = MemoryStore({"passages/bank_l3_rain": contract("passage.bank_l3_rain.json")})
    response = post(client(generator(nlp), store), length_profile="STANDARD")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NO_LISTENING_PASSAGE"


def test_a_passage_that_breaks_the_schema_is_never_stored():
    store = bank()
    broken = Generated({"passage_id": "gen_sess_demo_001"}, 1, 3.9)
    response = post(client(Failing(broken), store))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INVALID_PASSAGE"
    assert store.get(PATH) is None


def test_a_repeated_request_that_stored_first_wins(nlp):
    winner = {
        "passage_id": "gen_sess_demo_001",
        "paired_listening_passage_id": "bank_l3_rain",
        "generation": {"attempts": 2, "estimated_arl": 4.1},
    }

    class Raced(MemoryStore):
        def create(self, path, data):
            self.docs[path] = winner
            return False

    store = Raced(bank().docs)
    body = post(client(generator(nlp), store)).json()
    assert (body["attempts"], body["estimated_arl"]) == (2, 4.1)
