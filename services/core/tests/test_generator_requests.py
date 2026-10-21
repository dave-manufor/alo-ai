"""plan.ready pre-generates the child's next story from the Coach's story request
(PRD 4.5, SDD 11): stored once, the child pointed at it, the request marked last."""

from datetime import UTC, datetime

import aloai_contracts
import httpx
import pytest
import spacy
from aloai_events import anyone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import ValidationError
from services.core.api import events_router
from services.core.generator.models import FixtureModel
from services.core.generator.pipeline import DeadlineExceeded, GateFailed, Generated, Generator
from services.core.generator_requests import PREGENERATE_DEADLINE_MS, NextStories
from services.core.grader import paths
from services.core.tests.support import (
    RECORDED,
    SESSION_ID,
    contract,
    event,
    pushed,
    seeded_store,
)

REQUEST = f"story_requests/story_{SESSION_ID}"
NEXT = "gen_next_sess_demo_001"
DONE_AT = datetime(2026, 1, 15, 9, 20, tzinfo=UTC)


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


class Recording:
    """A generator that keeps what it was asked, and answers with the given outcome."""

    def __init__(self, outcome) -> None:
        self.outcome, self.asked = outcome, []

    def generate(self, request, passage_id, listening_passage_id):
        self.asked.append((request, passage_id, listening_passage_id))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def store_with_request(**changes):
    store = seeded_store()
    # The recorded demo story is ARL 4 on animals and adventure.
    store.docs[REQUEST] = contract("story_request.queued.json") | {"arl": 4} | changes
    return store


def stories(generator, store) -> NextStories:
    return NextStories(generator, store, clock=lambda: DONE_AT)


def test_the_next_story_is_stored_and_the_child_and_request_point_at_it(nlp):
    store = store_with_request()
    model = FixtureModel(RECORDED / "generator")
    stories(Generator(model, nlp, "aloai-dev-clips", "v1"), store).handle(SESSION_ID)
    passage = store.get(paths.passage(NEXT))
    assert not list(aloai_contracts.PASSAGE.iter_errors(passage))
    assert passage["length_profile"] == "DEMO"  # the session's profile
    assert passage["topic_tags"] == ["food", "music"]
    assert store.get(paths.child("child_demo_001"))["next_passage_id"] == NEXT
    assert store.get(paths.child("child_demo_001"))["primary_class"] == 2  # merged, not replaced
    done = store.get(REQUEST)
    assert not list(aloai_contracts.STORY_REQUEST.iter_errors(done))
    assert done | {"arl": 2} == contract("story_request.done.json")


def test_the_request_is_generated_within_the_bound_at_the_coachs_level():
    store = store_with_request()
    generator = Recording(Generated({"passage_id": NEXT}, 1, 4.0))
    with pytest.raises(ValidationError):  # the stub passage is not a whole passage
        stories(generator, store).handle(SESSION_ID)
    ((request, passage_id, listening),) = generator.asked
    assert (request.target_arl, request.tags) == (4, ("food", "music"))
    assert request.deadline_ms == PREGENERATE_DEADLINE_MS == 60_000
    assert (request.length_profile, request.voice_profile_id) == ("DEMO", "vp_google_v1")
    assert (passage_id, listening) == (NEXT, "bank_l3_rain")
    assert store.get(paths.passage(NEXT)) is None


@pytest.mark.parametrize("failure", [GateFailed([], 2), DeadlineExceeded("too slow")])
def test_a_story_that_fails_the_gate_or_the_bound_marks_the_request_failed(failure):
    store = store_with_request()
    stories(Recording(failure), store).handle(SESSION_ID)
    assert store.get(REQUEST)["status"] == "FAILED"
    assert store.get(REQUEST)["processed_at"] == "2026-01-15T09:20:00Z"
    assert "passage_id" not in store.get(REQUEST)
    assert store.get(paths.child("child_demo_001")).get("next_passage_id") is None


@pytest.mark.parametrize("failure", [GateFailed([], 2), DeadlineExceeded("too slow")])
def test_a_failed_story_clears_the_one_the_child_just_read(failure):
    # Session N read gen_next_{N-1}; without this session N+1 would read it again.
    store = store_with_request()
    store.merge(paths.child("child_demo_001"), {"next_passage_id": "gen_next_sess_old"})
    stories(Recording(failure), store).handle(SESSION_ID)
    child = store.get(paths.child("child_demo_001"))
    assert child["next_passage_id"] is None
    assert child["primary_class"] == 2  # merged, not replaced
    assert store.get(REQUEST)["status"] == "FAILED"


@pytest.mark.parametrize("status", ["DONE", "FAILED"])
def test_a_handled_request_is_skipped(status):
    store = store_with_request(status=status)
    generator = Recording(AssertionError("must not generate"))
    stories(generator, store).handle(SESSION_ID)
    assert generator.asked == []


def test_no_request_means_nothing_to_generate_and_no_old_story_to_read_again():
    store = seeded_store()
    store.merge(paths.child("child_demo_001"), {"next_passage_id": "gen_next_sess_old"})
    generator = Recording(AssertionError("must not generate"))
    stories(generator, store).handle(SESSION_ID)
    assert generator.asked == []
    assert store.get(paths.child("child_demo_001"))["next_passage_id"] is None
    assert store.get(REQUEST) is None


def test_no_request_and_no_session_changes_nothing():
    store = seeded_store()
    del store.docs[paths.session(SESSION_ID)]
    before = dict(store.docs)
    stories(Recording(AssertionError("must not generate")), store).handle(SESSION_ID)
    assert store.docs == before


def test_a_stored_story_is_not_generated_again_after_a_crash():
    store = store_with_request()
    store.docs[paths.passage(NEXT)] = {"passage_id": NEXT}  # stored, then the process died
    generator = Recording(AssertionError("must not generate"))
    stories(generator, store).handle(SESSION_ID)
    assert store.get(REQUEST)["status"] == "DONE"
    assert store.get(paths.child("child_demo_001"))["next_passage_id"] == NEXT


def test_vertex_down_is_left_to_pub_sub():
    store = store_with_request()
    with pytest.raises(httpx.ConnectError):
        stories(Recording(httpx.ConnectError("refused")), store).handle(SESSION_ID)
    assert "status" not in store.get(REQUEST)


def plan_ready():
    return pushed(
        event(
            "plan.ready",
            {"session_id": SESSION_ID, "plan_ref": "plans/plan_demo", "template_used": False},
        )
    )


def app(store, next_stories) -> TestClient:
    routes = FastAPI()
    routes.include_router(events_router(None, None, None, store, anyone, next_stories))
    return TestClient(routes, raise_server_exceptions=False)


def test_plan_ready_runs_the_next_story():
    store = store_with_request()
    generator = Recording(GateFailed([], 2))
    assert (
        app(store, stories(generator, store))
        .post("/pubsub/session-events", json=plan_ready())
        .status_code
        == 204
    )
    assert store.get(REQUEST)["status"] == "FAILED"


def test_a_request_that_breaks_its_schema_is_parked():
    store = store_with_request(tags=["cars"])
    http = app(store, stories(Recording(AssertionError("must not generate")), store))
    assert http.post("/pubsub/session-events", json=plan_ready()).status_code == 204
    assert store.get(f"sessions/{SESSION_ID}/errors/plan.ready")["error"] == "ValidationError"


def test_plan_ready_is_ignored_without_a_generator():
    store = store_with_request()
    assert app(store, None).post("/pubsub/session-events", json=plan_ready()).status_code == 204
    assert "status" not in store.get(REQUEST)
