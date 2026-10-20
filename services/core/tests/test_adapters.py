"""The Grader's adapters to Vertex AI and Speech-to-Text, against fake clients: no
test reaches a Google service."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from services.core.grader.asr import (
    ChirpTranscriber,
    FixtureTranscriber,
    transcript,
    without_unset_confidence,
)
from services.core.grader.models import (
    FixtureGradingModel,
    GradingError,
    GradingTask,
    VertexGradingModel,
)
from services.core.grader.prompts import INSTRUCTIONS
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


def test_a_transcript_with_no_confidence_marks_no_word():
    assert without_unset_confidence([("a", 0.0), ("red", 0.0)]) == [("a", None), ("red", None)]
    assert transcript([("a", None), ("red", None)]) == "a red"
    assert without_unset_confidence([("a", 0.0), ("red", 0.9)]) == [("a", 0.0), ("red", 0.9)]
    assert without_unset_confidence([]) == []


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


def test_the_quick_call_answers_without_thinking_inside_five_seconds():
    output = grader_output({}, {f"{PASSAGE_ID}_q1": 2})
    models = FakeModels(json.dumps(output))
    VertexGradingModel(SimpleNamespace(models=models)).grade(
        replace(task(), model="gemini-2.5-flash")
    )
    VertexGradingModel(SimpleNamespace(models=models)).grade(task())
    flash, pro = models.calls
    assert (flash.config.thinking_config.thinking_budget, flash.config.http_options.timeout) == (
        0,
        5000,
    )
    assert (pro.config.thinking_config, pro.config.http_options.timeout) == (None, 60000)
