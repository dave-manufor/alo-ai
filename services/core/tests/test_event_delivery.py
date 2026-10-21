"""How Core receives events on each cloud (SDD 11): one handler, reached by the Pub/Sub push
route on gcp and by the Service Bus queue pump on azure."""

import json
from types import SimpleNamespace

import aloai_env
import aloai_events
import pytest
from aloai_events import MemoryPublisher, pump_once
from aloai_store import MemoryStore
from fastapi.testclient import TestClient
from services.core import main
from services.core.api import event_handler
from services.core.grader import paths
from services.core.grader.models import FixtureGradingModel
from services.core.grader.quick import QuickGrader
from services.core.tests.support import (
    RECORDED,
    SESSION_ID,
    add_telemetry,
    coach_store,
    contract,
    event,
    handler,
    parts,
    pushed,
    quick_request,
    seeded_store,
    session_done,
)


def settings(cloud: str, **more) -> aloai_env.Config:
    return aloai_env.load({"ALO_ENV": "local", "CLOUD": cloud, "EVENT_QUEUE": "core-events"} | more)


def app_for(cloud: str, store=None, publisher=None, next_stories=None):
    store, publisher = store or seeded_store(), publisher or MemoryPublisher()
    final, assembler, coach = parts(store, publisher)
    quick = QuickGrader(store, FixtureGradingModel(RECORDED / "grader"))
    generator = SimpleNamespace()  # the generator route only holds it until a request
    app = main.build_app(
        settings(cloud), quick, final, assembler, coach, store, generator, next_stories
    )
    return app, store


# ---- the handler


def test_the_handler_grades_assembles_and_coaches_as_the_push_route_does():
    store, publisher = seeded_store(), MemoryPublisher()
    handle = handler(store, publisher)
    handle(event("session.done", session_done()))
    assert store.get(paths.grading(SESSION_ID)) is not None

    add_telemetry(store)
    scored = {"session_id": SESSION_ID, "telemetry_ref": paths.telemetry(SESSION_ID)}
    handle(event("phase1.scored", scored))
    assert [e["type"] for e in publisher.events] == ["report.ready"]

    coach_store_, coach_publisher = coach_store(), MemoryPublisher()
    handler(coach_store_, coach_publisher)(contract("event.report_ready.json"))
    assert [e["type"] for e in coach_publisher.events] == ["plan.ready"]


def test_the_handler_ignores_a_type_core_does_not_handle():
    publisher = MemoryPublisher()
    started = {
        "session_id": SESSION_ID,
        "child_ref": "child_demo_001",
        "passage_id": "bank_p3_market_day",
        "context": "SCHOOL",
        "voice_profile_id": "vp_google_v1",
        "voice_mode": "cache_first",
        "session_profile": "demo",
    }
    handler(seeded_store(), publisher)(event("session.started", started))
    assert publisher.events == []


def test_the_handler_parks_what_can_never_succeed_and_returns():
    store = seeded_store()
    store.docs.pop(paths.session(SESSION_ID))
    handler(store, MemoryPublisher())(event("session.done", session_done()))
    assert store.get(f"sessions/{SESSION_ID}/errors/session.done")["error"] == "LookupError"


def test_the_handler_raises_what_may_pass_on_retry_and_parks_nothing():
    store = seeded_store()

    class Down:
        def handle(self, data):
            raise ConnectionError("Cosmos DB is unavailable")

    with pytest.raises(ConnectionError):
        event_handler(Down(), None, None, store)(event("session.done", session_done()))
    assert store.get(f"sessions/{SESSION_ID}/errors/session.done") is None


# ---- a Service Bus message reaches the same handler


class Message:
    def __init__(self, event_dict):
        self.body = iter([json.dumps(event_dict).encode()])


class Receiver:
    def __init__(self, *messages):
        self.pending, self.completed, self.abandoned = list(messages), [], []

    def receive_messages(self, max_message_count, max_wait_time):
        return [self.pending.pop(0)] if self.pending else []

    def complete_message(self, message):
        self.completed.append(message)

    def abandon_message(self, message):
        self.abandoned.append(message)


def test_a_session_done_message_is_graded_and_completed():
    store = seeded_store()
    receiver = Receiver(Message(event("session.done", session_done())))
    assert pump_once(receiver, handler(store, MemoryPublisher())) == 1
    assert store.get(paths.grading(SESSION_ID)) is not None
    assert (len(receiver.completed), receiver.abandoned) == (1, [])


def test_a_message_that_can_never_be_graded_is_parked_and_completed():
    store = seeded_store()
    store.docs.pop(paths.session(SESSION_ID))
    receiver = Receiver(Message(event("session.done", session_done())))
    assert pump_once(receiver, handler(store, MemoryPublisher())) == 1
    assert store.get(f"sessions/{SESSION_ID}/errors/session.done") is not None
    assert (len(receiver.completed), receiver.abandoned) == (1, [])


def test_a_message_whose_work_fails_is_abandoned_for_service_bus_to_deliver_again():
    class Down:
        def handle(self, data):
            raise ConnectionError("Cosmos DB is unavailable")

    receiver = Receiver(Message(event("session.done", session_done())))
    handle = event_handler(Down(), None, None, seeded_store())
    assert pump_once(receiver, handle) == 0
    assert (receiver.completed, len(receiver.abandoned)) == ([], 1)


# ---- the app on each cloud


def test_on_gcp_the_push_route_is_mounted():
    app, store = app_for("gcp")
    http = TestClient(app)
    response = http.post(
        "/pubsub/session-events", json=pushed(event("session.done", session_done()))
    )
    assert response.status_code == 204
    assert store.get(paths.grading(SESSION_ID)) is not None


def test_on_azure_the_push_route_is_not_mounted_because_nothing_signs_a_push():
    app, store = app_for("azure")
    http = TestClient(app)
    response = http.post(
        "/pubsub/session-events", json=pushed(event("session.done", session_done()))
    )
    assert response.status_code == 404
    assert store.get(paths.grading(SESSION_ID)) is None
    assert http.post("/v1/grade:quick", json=quick_request("READING", 0, "")).status_code == 400


def test_the_azure_app_pumps_its_queue_into_the_handler_while_it_runs(monkeypatch):
    pumps = []

    class Pump:
        def __init__(self, config, queue, handle):
            self.queue, self.handle, self.running = queue, handle, False
            pumps.append(self)

        def start(self):
            self.running = True

        def stop(self):
            self.running = False

    monkeypatch.setattr(aloai_events, "open_queue_pump", Pump)
    app, store = app_for("azure")
    with TestClient(app):
        [pump] = pumps
        assert (pump.queue, pump.running) == ("core-events", True)
        pump.handle(event("session.done", session_done()))
        assert store.get(paths.grading(SESSION_ID)) is not None
    assert pump.running is False


def test_the_gcp_app_starts_no_pump(monkeypatch):
    monkeypatch.setattr(aloai_events, "open_queue_pump", lambda *args: pytest.fail("pumped"))
    app, _ = app_for("gcp")
    with TestClient(app):
        pass


# ---- what is not built for azure yet says so


@pytest.fixture
def in_memory(monkeypatch):
    monkeypatch.setattr(main, "open_store", lambda config: MemoryStore())
    monkeypatch.setattr(main, "open_publisher", lambda config: MemoryPublisher())


@pytest.mark.parametrize(
    "env, what",
    [
        ({"AI_MODE": "fixtures"}, "book search"),
        ({"AI_MODE": "live"}, "AI_MODE=live"),
    ],
    ids=["book search", "live AI"],
)
def test_core_on_azure_names_what_is_not_built_yet(in_memory, env, what):
    with pytest.raises(aloai_env.ConfigError, match=what):
        main.create_app({"ALO_ENV": "local", "CLOUD": "azure", "EVENT_QUEUE": "core-events"} | env)


def test_the_live_coach_model_and_voice_are_not_built_for_azure_either():
    live = settings("azure", AI_MODE="live")
    with pytest.raises(aloai_env.ConfigError, match="AI_MODE=live"):
        main._coach_model(live)
    with pytest.raises(aloai_env.ConfigError, match="AI_MODE=live"):
        main._speaker(live, {})


def test_the_coach_email_is_called_with_a_token_for_the_chosen_cloud(monkeypatch):
    asked, sent = [], []
    monkeypatch.setattr(
        main,
        "service_token",
        lambda config, audience: asked.append((config.cloud, audience)) or "t",
    )

    def post(url, **kwargs):
        sent.append((url, kwargs["headers"]))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"delivery_id": "d1"})

    monkeypatch.setattr(main.requests, "post", post)
    notifier = main._notifier(
        settings("azure", ALO_ENV=""), {"ACCOUNT_URL": "https://account.internal"}, MemoryStore()
    )
    delivery = notifier.notify(
        template_id="plan_ready", guardian_id="g", child_id="c", session_id=SESSION_ID
    )
    assert delivery == "d1"
    assert asked == [("azure", "https://account.internal")]
    assert sent == [("https://account.internal/internal/notify", {"Authorization": "Bearer t"})]


# ---- plan.ready pre-generates the next story, on either cloud (GENERATOR_ON)


class NextStoriesFake:
    def __init__(self):
        self.sessions = []

    def handle(self, session_id):
        self.sessions.append(session_id)


def plan_ready():
    return contract("event.plan_ready.json")


def handler_with(next_stories):
    store, publisher = seeded_store(), MemoryPublisher()
    final, assembler, coach = parts(store, publisher)
    return event_handler(final, assembler, coach, store, next_stories)


def test_plan_ready_pre_generates_the_next_story_when_the_generator_is_on():
    next_stories = NextStoriesFake()
    handler_with(next_stories)(plan_ready())
    assert next_stories.sessions == [plan_ready()["session_id"]]


def test_plan_ready_is_ignored_while_the_generator_is_off():
    handler_with(None)(plan_ready())  # no error, nothing to call


def test_a_plan_ready_message_reaches_the_generator_through_the_service_bus_pump():
    next_stories = NextStoriesFake()
    receiver = Receiver(Message(plan_ready()))
    assert pump_once(receiver, handler_with(next_stories)) == 1
    assert next_stories.sessions == [plan_ready()["session_id"]]
    assert (len(receiver.completed), receiver.abandoned) == (1, [])


def test_a_story_that_cannot_be_generated_is_retried_not_lost_on_the_queue():
    class Down:
        def handle(self, session_id):
            raise ConnectionError("Azure OpenAI is unavailable")

    receiver = Receiver(Message(plan_ready()))
    assert pump_once(receiver, handler_with(Down())) == 0
    assert (receiver.completed, len(receiver.abandoned)) == ([], 1)


def test_on_gcp_the_push_route_hands_plan_ready_to_the_generator():
    next_stories = NextStoriesFake()
    app, _ = app_for("gcp", next_stories=next_stories)
    response = TestClient(app).post("/pubsub/session-events", json=pushed(plan_ready()))
    assert response.status_code == 204
    assert next_stories.sessions == [plan_ready()["session_id"]]


def test_on_azure_the_pump_hands_plan_ready_to_the_generator(monkeypatch):
    pumps = []

    class Pump:
        def __init__(self, config, queue, handle):
            self.handle = handle
            pumps.append(self)

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(aloai_events, "open_queue_pump", Pump)
    next_stories = NextStoriesFake()
    app, _ = app_for("azure", next_stories=next_stories)
    with TestClient(app):
        pumps[0].handle(plan_ready())
    assert next_stories.sessions == [plan_ready()["session_id"]]


@pytest.mark.parametrize(
    "flag, on", [({}, False), ({"GENERATOR_ON": "false"}, False), ({"GENERATOR_ON": "true"}, True)]
)
def test_the_generator_switch_decides_whether_plan_ready_is_acted_on(monkeypatch, flag, on):
    seen = {}
    monkeypatch.setattr(main, "open_store", lambda config: MemoryStore())
    monkeypatch.setattr(main, "open_publisher", lambda config: MemoryPublisher())
    monkeypatch.setattr(main, "_book_search", lambda config: None)
    monkeypatch.setattr(main, "_generator", lambda config, env: "generator")
    monkeypatch.setattr(main, "build_app", lambda *args: seen.setdefault("args", args))
    main.create_app({"ALO_ENV": "local", "AI_MODE": "fixtures", **flag})
    *_, generator, next_stories = seen["args"]
    assert generator == "generator"
    assert (next_stories is not None) is on


def test_the_live_generator_on_azure_is_refused_until_it_is_built():
    with pytest.raises(aloai_env.ConfigError, match="AI_MODE=live"):
        main._generator(settings("azure", AI_MODE="live"), {})
