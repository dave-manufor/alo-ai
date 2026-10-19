"""One session through the Grader on recorded responses, as `make replay` will run it:
quick scores during the session, then session.done and phase1.scored in either order."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.core import contracts
from services.core.events import MemoryPublisher
from services.core.grader import paths
from services.core.grader.api import router
from services.core.grader.asr import FixtureTranscriber
from services.core.grader.final import FinalGrader
from services.core.grader.models import FixtureGradingModel
from services.core.grader.quick import QuickGrader
from services.core.tests.support import (
    RECORDED,
    SESSION_ID,
    add_telemetry,
    assembler,
    event,
    pushed,
    quick_request,
    seeded_store,
    session_done,
)


def replay(telemetry_first: bool) -> tuple[dict, MemoryPublisher, list[dict]]:
    store, publisher = seeded_store(), MemoryPublisher()
    model = FixtureGradingModel(RECORDED / "grader")
    reports = assembler(store, publisher)
    app = FastAPI()
    app.include_router(
        router(
            QuickGrader(store, model),
            FinalGrader(store, model, FixtureTranscriber(RECORDED / "asr"), reports),
            reports,
        )
    )
    http = TestClient(app)
    turns = [
        ("RETELL", 0, "ada and her mama went to the market and she saw a red hat"),
        ("QUESTION", 0, "it was red"),
        ("QUESTION", 1, ""),
    ]
    quick = [http.post("/v1/grade:quick", json=quick_request(*turn)).json() for turn in turns]

    scored = {"session_id": SESSION_ID, "telemetry_ref": paths.telemetry(SESSION_ID)}
    if telemetry_first:
        add_telemetry(store)
        http.post("/pubsub/session-events", json=pushed(event("phase1.scored", scored)))
        http.post("/pubsub/session-events", json=pushed(event("session.done", session_done())))
    else:
        http.post("/pubsub/session-events", json=pushed(event("session.done", session_done())))
        add_telemetry(store)
        http.post("/pubsub/session-events", json=pushed(event("phase1.scored", scored)))
    return store.get(paths.report(SESSION_ID)), publisher, quick


@pytest.mark.parametrize("telemetry_first", [True, False])
def test_a_replayed_session_ends_in_one_report(telemetry_first):
    report, publisher, quick = replay(telemetry_first)
    assert quick[-1] == {"schema_version": 1, "complete": True, "run_listening_module": True}
    contracts.READING_REPORT.validate(report)
    assert report["comprehension"]["reading_comprehension"] == 70.0
    assert report["comprehension"]["quick_reading_comprehension"] == 70.0
    assert report["comprehension"]["quick_vs_final_item_agreement"] == 1.0
    assert report["profile"] == {
        "code": "UNDERSTANDS_BUILDING_WORD_READING",
        "provisional": True,
        "primary_need": "Understands stories; reading the words is still developing",
        "instructional_focus": (
            "Practise the sounds in the words that were hard today, "
            "and keep story questions at class level."
        ),
    }
    assert report["level"]["next_passage_arl"] == 2
    assert [e["type"] for e in publisher.events] == ["report.ready"]
