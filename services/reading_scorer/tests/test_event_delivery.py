"""How the Reading Scorer receives events and reads its audio on each cloud (SDD 11): one
handler, reached by the Pub/Sub push route on gcp and by the Service Bus queue pump on azure."""

import base64
import io
import json

import aloai_env
import aloai_events
import numpy as np
import pytest
import soundfile
from aloai_blobs import BlobNotFound, MemoryBlobs
from aloai_events import MemoryPublisher, envelope, pump_once
from fastapi.testclient import TestClient
from services.reading_scorer import main
from services.reading_scorer.api import event_handler
from services.reading_scorer.audio import BlobAudio
from services.reading_scorer.scorer import telemetry_path
from services.reading_scorer.tests.support import (
    NOW,
    READING,
    SESSION_ID,
    recorded,
    scorer,
    seeded_store,
)


def settings(cloud: str, **more) -> aloai_env.Config:
    return aloai_env.load(
        {"ALO_ENV": "local", "CLOUD": cloud, "EVENT_QUEUE": "scorer-events"} | more
    )


def recorded_event(**changes) -> dict:
    return envelope("phase1.recorded", SESSION_ID, recorded(**changes), now=NOW)


# ---- the handler


def test_the_handler_scores_a_recording():
    store, publisher = seeded_store(), MemoryPublisher()
    event_handler(scorer(store, publisher))(recorded_event())
    assert store.get(telemetry_path(SESSION_ID)) is not None
    assert [e["type"] for e in publisher.events] == ["phase1.scored"]


def test_the_handler_ignores_a_type_the_scorer_does_not_handle():
    store, publisher = seeded_store(), MemoryPublisher()
    started = recorded_event() | {"type": "session.started"}
    event_handler(scorer(store, publisher))(started)
    assert publisher.events == []


def test_the_handler_parks_a_recording_that_can_never_be_scored_and_returns():
    store, publisher = seeded_store(), MemoryPublisher()
    told = recorded(told_token_indices=[3, 6, 9, 12])
    event_handler(scorer(store, publisher))(envelope("phase1.recorded", SESSION_ID, told, now=NOW))
    assert store.get(f"sessions/{SESSION_ID}/errors/phase1.recorded")["error"] == "ValueError"
    assert publisher.events == []


def test_the_handler_raises_what_may_pass_on_retry_and_parks_nothing():
    store = seeded_store()

    class Down:
        def load(self, uri):
            raise ConnectionError("Blob Storage is unavailable")

    with pytest.raises(ConnectionError):
        event_handler(scorer(store, MemoryPublisher(), audio=Down()))(recorded_event())
    assert store.get(f"sessions/{SESSION_ID}/errors/phase1.recorded") is None


# ---- a Service Bus message reaches the same handler


class Message:
    def __init__(self, event):
        self.body = iter([json.dumps(event).encode()])


class Receiver:
    def __init__(self, *messages):
        self.pending, self.completed, self.abandoned = list(messages), [], []

    def receive_messages(self, max_message_count, max_wait_time):
        return [self.pending.pop(0)] if self.pending else []

    def complete_message(self, message):
        self.completed.append(message)

    def abandon_message(self, message):
        self.abandoned.append(message)


def test_a_phase1_recorded_message_is_scored_and_completed():
    store, publisher = seeded_store(), MemoryPublisher()
    receiver = Receiver(Message(recorded_event()))
    assert pump_once(receiver, event_handler(scorer(store, publisher))) == 1
    assert store.get(telemetry_path(SESSION_ID)) is not None
    assert (len(receiver.completed), receiver.abandoned) == (1, [])


def test_a_message_whose_work_fails_is_abandoned_for_service_bus_to_deliver_again():
    class Down:
        def load(self, uri):
            raise ConnectionError("Blob Storage is unavailable")

    receiver = Receiver(Message(recorded_event()))
    handle = event_handler(scorer(seeded_store(), MemoryPublisher(), audio=Down()))
    assert pump_once(receiver, handle) == 0
    assert (receiver.completed, len(receiver.abandoned)) == ([], 1)


# ---- the app on each cloud


def app_for(cloud: str):
    store, publisher = seeded_store(), MemoryPublisher()
    return main.build_app(settings(cloud), scorer(store, publisher)), store


def test_on_gcp_the_push_route_is_mounted():
    app, store = app_for("gcp")
    data = base64.b64encode(json.dumps(recorded_event()).encode()).decode()
    body = {"message": {"data": data}}
    assert TestClient(app).post("/pubsub/session-events", json=body).status_code == 204
    assert store.get(telemetry_path(SESSION_ID)) is not None


def test_on_azure_the_push_route_is_not_mounted_because_nothing_signs_a_push():
    app, store = app_for("azure")
    response = TestClient(app).post("/pubsub/session-events", json={"message": {"data": ""}})
    assert response.status_code == 404
    assert store.get(telemetry_path(SESSION_ID)) is None


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
        assert (pump.queue, pump.running) == ("scorer-events", True)
        pump.handle(recorded_event())
        assert store.get(telemetry_path(SESSION_ID)) is not None
    assert pump.running is False


def test_the_gcp_app_starts_no_pump(monkeypatch):
    monkeypatch.setattr(aloai_events, "open_queue_pump", lambda *args: pytest.fail("pumped"))
    app, _ = app_for("gcp")
    with TestClient(app):
        pass


# ---- the audio, from either cloud's storage


def flac(samples, rate) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, rate, format="FLAC")
    return buffer.getvalue()


AZURE_READING = "az://audio/3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10/READING/a1b2.flac"


@pytest.mark.parametrize("uri", [READING, AZURE_READING], ids=["gs", "az"])
def test_the_reading_is_read_as_16_khz_mono_whichever_cloud_holds_it(uri):
    tone = 0.1 * np.sin(np.linspace(0, 100, 16_000)).astype(np.float32)
    blobs = MemoryBlobs({uri: flac(tone, 16_000)})
    audio = BlobAudio(blobs).load(uri)
    assert audio.samples.shape == (16_000,)
    assert np.allclose(audio.samples, tone, atol=1e-3)


def test_audio_at_another_sample_rate_is_refused():
    blobs = MemoryBlobs({AZURE_READING: flac(np.zeros(8_000, dtype=np.float32), 8_000)})
    with pytest.raises(ValueError, match="8000 Hz"):
        BlobAudio(blobs).load(AZURE_READING)


def test_a_recording_that_is_not_there_is_a_lookup_error_for_the_handler_to_park():
    with pytest.raises(BlobNotFound) as error:
        BlobAudio(MemoryBlobs()).load(AZURE_READING)
    assert isinstance(error.value, LookupError)


def test_a_missing_recording_is_parked_not_retried():
    store, publisher = seeded_store(), MemoryPublisher()
    handle = event_handler(scorer(store, publisher, audio=BlobAudio(MemoryBlobs())))
    handle(recorded_event(audio_uri=AZURE_READING))
    assert store.get(f"sessions/{SESSION_ID}/errors/phase1.recorded")["error"] == "BlobNotFound"
    assert publisher.events == []
