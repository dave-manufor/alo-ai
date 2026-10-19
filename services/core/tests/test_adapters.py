"""The adapters to Vertex AI, Speech-to-Text, Firestore and Pub/Sub, against fake
clients: no test reaches a Google service."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from google.api_core.exceptions import AlreadyExists
from services.core.events import PubSubPublisher
from services.core.grader.asr import ChirpTranscriber, FixtureTranscriber, transcript
from services.core.grader.models import (
    FixtureGradingModel,
    GradingError,
    GradingTask,
    VertexGradingModel,
)
from services.core.grader.prompts import INSTRUCTIONS
from services.core.store import FirestoreStore
from services.core.tests.support import PASSAGE_ID, RECORDED, contract, grader_output

PASSAGE = contract("passage.bank_p3_market_day.json")


def task(pass_number=1) -> GradingTask:
    return GradingTask(
        key=f"{PASSAGE_ID}/pass{pass_number}",
        session_id="sess_demo_001",
        model="gemini-2.5-pro",
        passage=PASSAGE,
        retell="ada went to the <market>",
        answers={f"{PASSAGE_ID}_q1": "it was red"},
        primary_class=2,
        pass_number=pass_number,
    )


class FakeModels:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        return SimpleNamespace(text=self.text)


def test_vertex_grading_asks_gemini_for_a_grader_output_at_temperature_zero():
    output = grader_output({"p1": 1, "p2": 1, "p3": 0, "p4": 0}, {f"{PASSAGE_ID}_q1": 2})
    models = FakeModels(json.dumps(output))
    assert VertexGradingModel(SimpleNamespace(models=models)).grade(task()) == output
    [call] = models.calls
    assert call.model == "gemini-2.5-pro"
    assert call.config.temperature == 0
    assert "$schema" not in call.config.response_json_schema
    assert call.contents.startswith(INSTRUCTIONS)
    assert "<child>ada went to the market</child>" in call.contents
    assert "<child>it was red</child>" in call.contents
    assert "The child is in Primary 2." in call.contents


def test_the_two_passes_see_the_exemplars_in_different_orders():
    prompts = []
    for pass_number in (1, 2):
        models = FakeModels("{}")
        VertexGradingModel(SimpleNamespace(models=models)).grade(task(pass_number))
        prompts.append(models.calls[0].contents)
    assert prompts[0] != prompts[1]
    models = FakeModels("{}")
    VertexGradingModel(SimpleNamespace(models=models)).grade(task(1))
    assert models.calls[0].contents == prompts[0]


@pytest.mark.parametrize("text", ["not json", None])
def test_an_answer_that_is_not_json_is_refused(text):
    with pytest.raises(GradingError):
        VertexGradingModel(SimpleNamespace(models=FakeModels(text))).grade(task())


def test_recorded_grading_needs_a_recording_for_the_call():
    model = FixtureGradingModel(RECORDED / "grader")
    with pytest.raises(GradingError):
        model.grade(task(pass_number=9))
    with pytest.raises(GradingError):
        model.grade(replace(task(), session_id="sess_unknown"))


def test_low_confidence_words_are_marked_for_the_grader():
    assert transcript([("a", 0.9), ("red", 0.49), ("hat", 0.5)]) == "a [?red?] hat"


def test_chirp_is_asked_for_word_confidence_in_the_eu():
    def word(text, confidence):
        return SimpleNamespace(word=text, confidence=confidence)

    results = [
        SimpleNamespace(alternatives=[SimpleNamespace(words=[word("it", 0.9), word("was", 0.8)])]),
        SimpleNamespace(alternatives=[]),
        SimpleNamespace(alternatives=[SimpleNamespace(words=[word("red", 0.4)])]),
    ]
    requests = []
    client = SimpleNamespace(
        recognize=lambda request: requests.append(request) or SimpleNamespace(results=results)
    )
    words = ChirpTranscriber(client, "aloai-dev").words("gs://aloai-dev-audio/s/RETELL/t.flac")
    assert words == [("it", 0.9), ("was", 0.8), ("red", 0.4)]
    [request] = requests
    assert request.recognizer == "projects/aloai-dev/locations/eu/recognizers/_"
    assert request.uri == "gs://aloai-dev-audio/s/RETELL/t.flac"
    assert request.config.model == "chirp_3"
    assert request.config.features.enable_word_confidence


def test_recorded_words_are_found_by_the_audio_object_name():
    uri = "gs://bucket/session/QUESTION/a1b2c3d4-0000-4000-8000-000000000013.flac"
    assert FixtureTranscriber(RECORDED / "asr").words(uri) == [
        ("it", 0.95),
        ("was", 0.95),
        ("red", 0.95),
    ]


class FakeDocument:
    def __init__(self, documents, path):
        self._documents, self._path = documents, path

    def get(self):
        data = self._documents.get(self._path)
        return SimpleNamespace(exists=data is not None, to_dict=lambda: data)

    def set(self, data, merge=False):
        base = self._documents.get(self._path, {}) if merge else {}
        self._documents[self._path] = base | data

    def create(self, data):
        if self._path in self._documents:
            raise AlreadyExists("exists")
        self._documents[self._path] = data


class FakeFirestore:
    def __init__(self):
        self.documents = {}
        self.filters = []

    def document(self, path):
        return FakeDocument(self.documents, path)

    def collection(self, name):
        def where(filter):
            self.filters.append(filter)
            found = [d for p, d in self.documents.items() if p.startswith(f"{name}/")]
            return SimpleNamespace(
                stream=lambda: [SimpleNamespace(to_dict=lambda d=d: d) for d in found]
            )

        return SimpleNamespace(where=where)


def test_firestore_documents_are_read_written_merged_and_created_once():
    client = FakeFirestore()
    store = FirestoreStore(client)
    assert store.get("reports/a") is None
    store.set("children/c", {"primary_class": 2})
    store.merge("children/c", {"next_passage_arl": 3})
    assert store.get("children/c") == {"primary_class": 2, "next_passage_arl": 3}
    assert store.create("reports/a", {"child_id": "c"}) is True
    assert store.create("reports/a", {"child_id": "other"}) is False
    assert store.where("reports", "child_id", "c") == [{"child_id": "c"}]
    [query] = client.filters
    assert (query.field_path, query.op_string, query.value) == ("child_id", "==", "c")


def test_events_are_published_with_their_type_as_an_attribute():
    published = []
    client = SimpleNamespace(
        topic_path=lambda project, topic: f"projects/{project}/topics/{topic}",
        publish=lambda topic, data, **attrs: (
            published.append((topic, data, attrs)) or SimpleNamespace(result=lambda: "1")
        ),
    )
    PubSubPublisher(client, "aloai-dev").publish({"type": "report.ready", "session_id": "s"})
    [(topic, data, attrs)] = published
    assert topic == "projects/aloai-dev/topics/aloai.session-events"
    assert json.loads(data) == {"type": "report.ready", "session_id": "s"}
    assert attrs == {"type": "report.ready"}
