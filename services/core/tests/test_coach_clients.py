"""The Coach's clients outside Core, with fakes in place of HTTP, Text-to-Speech and
Cloud Storage."""

from types import SimpleNamespace

from aloai_store import MemoryStore
from google.cloud import texttospeech
from services.core.coach.clients import (
    AccountNotifier,
    ChirpSpeaker,
    Outbox,
    SilentSpeaker,
    StoryRequests,
)

REQUEST = {
    "template_id": "report_ready",
    "guardian_id": "guardian_demo_001",
    "child_id": "child_demo_001",
    "session_id": "sess_demo_001",
}


def test_a_story_request_is_one_per_session():
    store = MemoryStore()
    stories = StoryRequests(store)
    stories.queue(session_id="sess_demo_001", child_id="child_demo_001", arl=2, tags=["food"])
    stories.queue(session_id="sess_demo_001", child_id="child_demo_001", arl=2, tags=["music"])
    assert list(store.docs) == ["story_requests/story_sess_demo_001"]
    assert store.docs["story_requests/story_sess_demo_001"]["tags"] == ["music"]


def test_the_outbox_keeps_the_first_email_of_a_session():
    store = MemoryStore()
    outbox = Outbox(store)
    assert outbox.notify(**REQUEST) == outbox.notify(**REQUEST) == "sess_demo_001_report_ready"
    assert list(store.docs) == ["outbox/sess_demo_001_report_ready"]


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"delivery_id": "dlv_1"}


def test_the_account_service_is_called_with_cores_id_token():
    posts = []

    def post(url, **kwargs):
        posts.append((url, kwargs))
        return FakeResponse()

    notifier = AccountNotifier(
        "http://account:8080", post, lambda audience: f"token-for-{audience}"
    )
    assert notifier.notify(**REQUEST) == "dlv_1"
    [(url, kwargs)] = posts
    assert url == "http://account:8080/internal/notify"
    assert kwargs["headers"] == {"Authorization": "Bearer token-for-http://account:8080"}
    assert kwargs["json"] == {
        "template_id": "report_ready",
        "guardian_id": "guardian_demo_001",
        "child_id": "child_demo_001",
        "idempotency_key": "sess_demo_001_report_ready",
    }


class FakeTts:
    def __init__(self) -> None:
        self.requests = []

    def synthesize_speech(self, **request):
        self.requests.append(request)
        return SimpleNamespace(audio_content=b"mp3")


class FakeBucket:
    name = "aloai-dev-audio"

    def __init__(self) -> None:
        self.uploads = {}

    def blob(self, name):
        bucket = self

        class Blob:
            def upload_from_string(self, data, content_type):
                bucket.uploads[name] = (data, content_type)

        return Blob()


def test_the_summary_is_spoken_in_the_voice_and_saved_with_the_session():
    tts, bucket = FakeTts(), FakeBucket()
    speaker = ChirpSpeaker(tts, bucket, "en-GB-Chirp3-HD-Kore")
    uri = speaker.speak("Hello from Auntie Kemi.", "sess_demo_001")
    assert uri == "gs://aloai-dev-audio/sess_demo_001/summary/summary.mp3"
    assert bucket.uploads == {"sess_demo_001/summary/summary.mp3": (b"mp3", "audio/mpeg")}
    [request] = tts.requests
    assert request["input"].text == "Hello from Auntie Kemi."
    assert (request["voice"].language_code, request["voice"].name) == (
        "en-GB",
        "en-GB-Chirp3-HD-Kore",
    )
    assert request["audio_config"].audio_encoding == texttospeech.AudioEncoding.MP3
    assert request["audio_config"].speaking_rate == 0.9


def test_without_a_voice_nothing_is_spoken():
    assert SilentSpeaker().speak("Hello.", "sess_demo_001") is None
