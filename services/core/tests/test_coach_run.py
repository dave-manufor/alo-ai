"""The Reading Coach run: the recorded ADK run, its authorization and audit, the rewrite
and template fallbacks, consent, the feature flag and redelivery (PRD 3.1, 12.1)."""

import copy
import itertools
import json
from datetime import UTC, datetime

import aloai_contracts
import pytest
from aloai_events import MemoryPublisher
from services.core.coach.agent import RecordedModel
from services.core.coach.clients import Outbox, StoryRequests
from services.core.coach.plan import plan_path
from services.core.coach.run import ReadingCoach
from services.core.grader import paths
from services.core.tests.support import (
    CHILD_ID,
    GUARDIAN_ID,
    RECORDED,
    SESSION_ID,
    coach_store,
    contract,
)

NOW = datetime(2026, 1, 15, 9, 9, 20, tzinfo=UTC)
AUDIO_URI = "gs://aloai-dev-audio/sess_demo_001/summary/summary.mp3"
REPORT_READY = contract("event.report_ready.json")["data"]
RECORDED_TURNS = json.loads((RECORDED / "coach" / f"{SESSION_ID}.json").read_text())["turns"]
SAVE_PLAN = 3


class CountingNotifier:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def notify(self, **request) -> str:
        self.sent.append(request)
        return f"delivery_{len(self.sent)}"


class FixedSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str, session_id: str) -> str | None:
        self.spoken.append(text)
        return AUDIO_URI


class Models:
    """Hands out a RecordedModel of the given turns, counting runs."""

    def __init__(self, turns: list[dict]) -> None:
        self.turns = turns
        self.runs = 0

    def __call__(self, session_id: str) -> RecordedModel:
        self.runs += 1
        return RecordedModel(model="recorded/test", turns=self.turns)


def run(store=None, turns=None, *, enabled=True, notifier=None, models=None):
    store = store or coach_store()
    models = models or Models(RECORDED_TURNS if turns is None else turns)
    publisher, speaker = MemoryPublisher(), FixedSpeaker()
    ids = (f"00000000-0000-4000-8000-{n:012d}" for n in itertools.count(1))
    coach = ReadingCoach(
        store=store,
        publisher=publisher,
        stories=StoryRequests(store),
        notifier=notifier or CountingNotifier(),
        speaker=speaker,
        model_for=models,
        enabled=enabled,
        clock=lambda: NOW,
        new_id=lambda: next(ids),
    )
    coach.handle(REPORT_READY)
    return coach, publisher, speaker


def audit(store) -> list[dict]:
    return [doc for path, doc in store.docs.items() if path.startswith("audit_log/")]


def with_save_plan(**changes) -> list[dict]:
    turns = copy.deepcopy(RECORDED_TURNS)
    turns[SAVE_PLAN]["parts"][0]["args"] |= changes
    return turns


def test_the_recorded_run_saves_the_plan_in_the_contract():
    coach, publisher, speaker = run()
    store = coach.store
    assert store.get(plan_path(SESSION_ID)) == contract("plan.sess_demo_001.json")
    assert store.get(paths.report(SESSION_ID))["flags"] == ["DEMO_PROFILE", "SHORT_READING"]
    summary = RECORDED_TURNS[SAVE_PLAN]["parts"][0]["args"]["summary"]
    assert store.get(paths.report(SESSION_ID))["parent_reporting"]["summary_script"] == summary
    assert speaker.spoken == [summary]
    assert store.get("story_requests/story_sess_demo_001")["tags"] == ["food", "animals"]
    assert store.get(paths.child(CHILD_ID))["next_session_at"] == "2026-01-22T09:09:20Z"
    assert coach.notifier.sent == [
        {
            "template_id": "report_ready",
            "guardian_id": GUARDIAN_ID,
            "child_id": CHILD_ID,
            "session_id": SESSION_ID,
        }
    ]
    [event] = publisher.events
    aloai_contracts.EVENT_ENVELOPE.validate(event)
    assert event["data"] == contract("event.plan_ready.json")["data"]


def test_every_tool_call_is_authorized_and_audited():
    coach, _, _ = run()
    entries = audit(coach.store)
    assert [entry["tool"] for entry in entries] == [
        "get_report",
        "get_history",
        "get_activity_library",
        "search_books",
        "queue_story",
        "schedule_session",
        "save_plan",
        "send_parent_email",
    ]
    assert all(entry["allowed"] for entry in entries)
    assert {(entry["agent"], entry["principal_id"]) for entry in entries} == {
        ("reading_coach", GUARDIAN_ID)
    }
    assert all(entry["result_size"] > 0 for entry in entries)


@pytest.mark.parametrize(
    "call, reason",
    [
        (
            {"call": "write_score", "args": {"session_id": SESSION_ID}},
            "write_score is forbidden for every agent",
        ),
        (
            {"call": "get_history", "args": {"child_id": "child_other"}},
            "child_id is outside this run",
        ),
        (
            {
                "call": "send_parent_email",
                "args": {"child_id": CHILD_ID, "template_id": "report_ready"},
            },
            "send_parent_email reached its limit of 1 calls in a run",
        ),
    ],
)
def test_a_refused_call_is_audited_and_the_run_goes_on(call, reason):
    turns = copy.deepcopy(RECORDED_TURNS)
    turns.insert(-1, {"parts": [call]})
    coach, _, _ = run(turns=turns)
    refused = [entry for entry in audit(coach.store) if not entry["allowed"]]
    assert [(entry["tool"], entry["reason"], entry["result_size"]) for entry in refused] == [
        (call["call"], reason, None)
    ]
    assert coach.store.get(plan_path(SESSION_ID))["template_used"] is False


def test_a_refused_summary_is_rewritten_once():
    turns = with_save_plan(summary="Chidi scored 95 today.")
    turns.insert(SAVE_PLAN + 1, copy.deepcopy(RECORDED_TURNS[SAVE_PLAN]))
    coach, publisher, _ = run(turns=turns)
    assert coach.store.get(plan_path(SESSION_ID))["template_used"] is False
    saves = [entry for entry in audit(coach.store) if entry["tool"] == "save_plan"]
    assert len(saves) == 2
    assert publisher.events[0]["data"]["template_used"] is False


def test_a_second_refused_summary_uses_the_template():
    turns = with_save_plan(summary="Chidi scored 95 today.")
    turns.insert(SAVE_PLAN + 1, copy.deepcopy(turns[SAVE_PLAN]))
    coach, publisher, speaker = run(turns=turns)
    assert coach.store.get(plan_path(SESSION_ID))["template_used"] is True
    assert "95" not in speaker.spoken[0]
    assert publisher.events[0]["data"]["template_used"] is True


@pytest.mark.parametrize(
    "turns",
    [
        RECORDED_TURNS[:2],
        [{**turn, "tokens": 31_000} if n == 0 else turn for n, turn in enumerate(RECORDED_TURNS)],
        [{"parts": [{"call": "get_report", "args": {"session_id": SESSION_ID}}]}] * 13,
    ],
    ids=["turns run out", "token budget", "model call limit"],
)
def test_a_failed_run_saves_the_template_plan_and_still_emails(turns):
    coach, publisher, _ = run(turns=turns)
    assert coach.store.get(plan_path(SESSION_ID))["template_used"] is True
    assert coach.store.get(paths.report(SESSION_ID))["flags"] == [
        "DEMO_PROFILE",
        "SHORT_READING",
        "COACH_TEMPLATE_USED",
    ]
    assert len(coach.notifier.sent) == 1
    assert [event["type"] for event in publisher.events] == ["plan.ready"]


def test_a_missing_recording_saves_the_template_plan():
    def no_recording(session_id):
        return RecordedModel.from_file(RECORDED / "coach" / "sess_missing.json")

    coach, _, _ = run(models=no_recording)
    assert coach.store.get(plan_path(SESSION_ID))["template_used"] is True


def test_with_the_coach_off_the_template_plan_is_saved_without_the_agent():
    models = Models(RECORDED_TURNS)
    coach, _, _ = run(enabled=False, models=models)
    assert models.runs == 0
    assert audit(coach.store) == []
    assert coach.store.get(plan_path(SESSION_ID))["template_used"] is True
    assert len(coach.notifier.sent) == 1


@pytest.mark.parametrize("consent", [None, {"guardian_id": "guardian_other", "child_id": CHILD_ID}])
def test_without_consent_nothing_is_read_or_written(consent):
    store = coach_store()
    store.docs.pop("consents/consent_demo_001")
    if consent:
        store.set("consents/consent_other", consent)
    models = Models(RECORDED_TURNS)
    coach, publisher, _ = run(store, models=models)
    assert models.runs == 0
    assert store.get(plan_path(SESSION_ID)) is None
    assert coach.notifier.sent == []
    assert publisher.events == []


def test_a_redelivered_report_ready_finishes_without_a_second_plan():
    store = coach_store()
    models = Models(RECORDED_TURNS)
    run(store, models=models, notifier=Outbox(store))
    first = store.get(plan_path(SESSION_ID))
    _, publisher, speaker = run(store, models=models, notifier=Outbox(store))
    assert models.runs == 1
    assert store.get(plan_path(SESSION_ID)) == first
    assert speaker.spoken == []
    assert [path for path in store.docs if path.startswith("outbox/")] == [
        "outbox/sess_demo_001_report_ready"
    ]
    assert [event["type"] for event in publisher.events] == ["plan.ready"]


def test_a_plan_saved_before_its_summary_was_spoken_is_spoken_on_redelivery():
    store = coach_store()
    run(store)
    store.merge(plan_path(SESSION_ID), {"summary_audio_uri": None})
    _, _, speaker = run(store)
    assert len(speaker.spoken) == 1
    assert store.get(plan_path(SESSION_ID))["summary_audio_uri"] == AUDIO_URI


class BrokenStories:
    def queue(self, **request) -> str:
        raise ConnectionError("the generator is down")


def test_a_tool_that_fails_is_audited_and_the_template_plan_is_saved():
    store = coach_store()
    coach = ReadingCoach(
        store=store,
        publisher=MemoryPublisher(),
        stories=BrokenStories(),
        notifier=CountingNotifier(),
        speaker=FixedSpeaker(),
        model_for=Models(RECORDED_TURNS),
        clock=lambda: NOW,
    )
    coach.handle(REPORT_READY)
    [failed] = [entry for entry in audit(store) if entry["tool"] == "queue_story"]
    assert (failed["allowed"], failed["result_size"]) == (True, None)
    assert store.get(plan_path(SESSION_ID))["template_used"] is True


def test_the_template_flag_is_added_once():
    store = coach_store()
    store.merge(paths.report(SESSION_ID), {"flags": ["COACH_TEMPLATE_USED"]})
    run(store, enabled=False)
    assert store.get(paths.report(SESSION_ID))["flags"] == ["COACH_TEMPLATE_USED"]
