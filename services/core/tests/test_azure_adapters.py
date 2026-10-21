"""The Grader's and the Coach's adapters to Azure OpenAI, Azure AI Speech and Cosmos DB, against
fake clients: no test reaches Azure. These do not replace the evaluation sets (PRD 13.4),
which have to be run against the real deployments."""

import io
import json
from types import SimpleNamespace

import aloai_env
import numpy as np
import openai
import pytest
import soundfile
from aloai_blobs import BlobNotFound, MemoryBlobs
from aloai_events import MemoryPublisher
from services.core import main
from services.core.coach.azure import AzureSpeaker, azure_coach_model
from services.core.grader import paths
from services.core.grader.azure import (
    FORMAT,
    NEAREST,
    AzureEmbedder,
    AzureGradingModel,
    AzureSpeechTranscriber,
    CosmosBookSearch,
    azure_model,
    versions,
)
from services.core.grader.models import (
    GRADER_MODEL,
    GRADER_TIMEOUT_S,
    QUICK_MODEL,
    QUICK_TIMEOUT_S,
    GradingError,
    GradingTask,
    UpstreamErrors,
    grade,
)
from services.core.grader.prompts import INSTRUCTIONS
from services.core.tests.support import (
    PASSAGE_ID,
    SESSION_ID,
    add_telemetry,
    assembler,
    contract,
    event,
    grader_output,
    handler,
    seeded_store,
    session_done,
)

PASSAGE = contract("passage.bank_p3_market_day.json")
DEPLOYMENTS = {
    "grader": "gpt-4.1",
    "quick": "gpt-4.1-mini",
    "coach": "gpt-4.1-coach",
    "embedding": "embed-small",
}


def azure(**more) -> aloai_env.Config:
    env = {
        "ALO_ENV": "local",
        "CLOUD": "azure",
        "AZURE_OPENAI_ENDPOINT": "https://aloai.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENTS": json.dumps(DEPLOYMENTS),
        "AZURE_SPEECH_LOCALE": "en-NG",
        "EVENT_QUEUE": "core-events",
    }
    return aloai_env.load(env | more)


def task(model=GRADER_MODEL, pass_number=1) -> GradingTask:
    return GradingTask(
        key=f"{PASSAGE_ID}/pass{pass_number}",
        session_id="sess_demo_001",
        model=model,
        passage=PASSAGE,
        retell="ada went to the <market>",
        answers={f"{PASSAGE_ID}_q1": "it was red"},
        primary_class=2,
        pass_number=pass_number,
    )


OUTPUT = grader_output({"p1": 1, "p2": 1, "p3": 0, "p4": 0}, {f"{PASSAGE_ID}_q1": 2})


class ChatFake:
    def __init__(self, content=json.dumps(OUTPUT), choices=None):
        self.calls = []
        self._response = SimpleNamespace(
            choices=choices
            if choices is not None
            else [SimpleNamespace(message=SimpleNamespace(content=content))]
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


# ---- grading


def test_azure_grading_asks_the_grader_deployment_for_a_grader_output_at_temperature_zero():
    client = ChatFake()
    model = AzureGradingModel(client, quick="gpt-4.1-mini", grader="gpt-4.1")
    assert model.grade(task()) == OUTPUT
    [call] = client.calls
    assert call["model"] == "gpt-4.1"
    assert call["temperature"] == 0
    assert call["timeout"] == GRADER_TIMEOUT_S
    [message] = call["messages"]
    assert message["role"] == "user"
    assert message["content"].startswith(INSTRUCTIONS)
    assert "<child>ada went to the market</child>" in message["content"]
    assert "The child is in Primary 2." in message["content"]


def test_the_quick_call_uses_the_quick_deployment_and_its_short_timeout():
    client = ChatFake()
    AzureGradingModel(client, quick="gpt-4.1-mini", grader="gpt-4.1").grade(task(QUICK_MODEL))
    [call] = client.calls
    assert (call["model"], call["timeout"]) == ("gpt-4.1-mini", QUICK_TIMEOUT_S)


def test_the_answer_is_asked_for_in_the_grader_output_schema():
    client = ChatFake()
    AzureGradingModel(client, "q", "g").grade(task())
    response_format = client.calls[0]["response_format"]
    assert response_format is FORMAT
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]
    assert schema["name"] == "grader_output"
    assert "$schema" not in schema["schema"]
    assert schema["strict"] is False


def test_the_two_passes_see_the_exemplars_in_different_orders():
    prompts = []
    for pass_number in (1, 2):
        client = ChatFake()
        AzureGradingModel(client, "q", "g").grade(task(pass_number=pass_number))
        prompts.append(client.calls[0]["messages"][0]["content"])
    assert prompts[0] != prompts[1]


@pytest.mark.parametrize(
    "client",
    [ChatFake(content="not json"), ChatFake(content=None), ChatFake(choices=[])],
    ids=["not json", "no content", "no choices"],
)
def test_an_answer_that_is_not_usable_json_is_refused(client):
    with pytest.raises(GradingError):
        AzureGradingModel(client, "q", "g").grade(task())


def test_what_azure_answers_still_goes_through_the_graders_checks():
    assert grade(AzureGradingModel(ChatFake(), "q", "g"), task()) == OUTPUT
    other = grader_output({"p1": 1, "p2": 1, "p3": 0, "p4": 0}, {"someone_elses_q1": 2})
    with pytest.raises(GradingError, match="other propositions or items"):
        grade(AzureGradingModel(ChatFake(content=json.dumps(other)), "q", "g"), task())


def test_the_grading_model_is_built_from_the_quick_and_grader_deployments():
    client = ChatFake()
    azure_model(client, azure()).grade(task(QUICK_MODEL))
    assert client.calls[0]["model"] == "gpt-4.1-mini"


def test_a_failed_azure_call_is_an_upstream_error_to_retry():
    request = SimpleNamespace(method="POST", url="https://aloai.openai.azure.com")
    assert issubclass(openai.APITimeoutError, UpstreamErrors)
    assert isinstance(openai.APIConnectionError(request=request), UpstreamErrors)
    from azure.core.exceptions import ServiceRequestError

    assert isinstance(ServiceRequestError("Cosmos DB is unavailable"), UpstreamErrors)


# ---- response-track transcripts


def flac(samples, rate=16_000) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, rate, format="FLAC")
    return buffer.getvalue()


AUDIO = "az://audio/3f2b9c1e/RETELL/a1b2c3d4.flac"


def transcriber(words, heard=None):
    blobs = MemoryBlobs({AUDIO: flac((0.1 * np.ones(1_600)).astype(np.float32))})

    def recognize(pcm, phrases):
        if heard is not None:
            heard.append((len(pcm), tuple(phrases)))
        return words

    return AzureSpeechTranscriber(blobs, recognize)


def test_a_response_is_read_as_pcm_and_recognised_with_no_hints():
    heard = []
    words = [("ada", 0.9), ("ran", 0.3)]
    assert transcriber(words, heard).words(AUDIO) == words
    assert heard == [(2 * 1_600, ())]


def test_a_transcript_with_no_confidence_at_all_leaves_every_word_unmarked():
    assert transcriber([("ada", 0.0), ("ran", 0.0)]).words(AUDIO) == [("ada", None), ("ran", None)]
    assert transcriber([("ada", None)]).words(AUDIO) == [("ada", None)]
    assert transcriber([]).words(AUDIO) == []


def test_a_response_that_is_not_in_storage_is_a_lookup_error_for_the_handler_to_park():
    blobs = MemoryBlobs()
    with pytest.raises(BlobNotFound):
        AzureSpeechTranscriber(blobs, lambda pcm, phrases: []).words(AUDIO)


# ---- embedding


class EmbeddingsFake:
    def __init__(self):
        self.calls = []
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=(0.5, -0.5))])


def test_interests_are_embedded_at_the_catalogues_768_dimensions():
    client = EmbeddingsFake()
    assert AzureEmbedder(client, "embed-small").embed("animals, food") == [0.5, -0.5]
    assert client.calls == [{"model": "embed-small", "input": "animals, food", "dimensions": 768}]


# ---- book search


class BooksFake:
    def __init__(self, rows):
        self.rows, self.queries = rows, []

    def query_items(self, query, parameters, enable_cross_partition_query):
        self.queries.append((query, {p["name"]: p["value"] for p in parameters}))
        assert enable_cross_partition_query is True
        return iter(self.rows)


def test_the_nearest_books_come_back_as_candidates_with_their_cosmos_similarity():
    rows = [
        {"id": "books|book_demo_001", "arl": 3, "west_african_setting": True, "similarity": 0.91},
        {"id": "books|book_demo_002", "arl": 4, "west_african_setting": None, "similarity": 0.5},
    ]
    books = BooksFake(rows)
    found = CosmosBookSearch(books).nearest([0.1, 0.2], [3, 4], 5)
    assert [(b.book_id, b.arl, b.similarity, b.west_african) for b in found] == [
        ("book_demo_001", 3, 0.91, True),
        ("book_demo_002", 4, 0.5, False),
    ]
    [(query, parameters)] = books.queries
    assert query == NEAREST
    assert parameters == {"@limit": 5, "@vector": [0.1, 0.2], "@levels": [3, 4]}


def test_the_query_leaves_out_books_held_for_review_and_other_levels_and_orders_nearest_first():
    assert "c.d.held_for_review = false" in NEAREST
    assert "ARRAY_CONTAINS(@levels, c.d.arl)" in NEAREST
    assert NEAREST.endswith("ORDER BY VectorDistance(c.d.embedding, @vector)")
    assert "DESC" not in NEAREST


# ---- the report names the models used


def test_the_report_records_the_azure_models_when_they_are_the_ones_called():
    settings = azure(AZURE_SPEECH_LOCALE="en-NG")
    store, publisher = seeded_store(), MemoryPublisher()
    handle = handler(store, publisher)
    handle(event("session.done", session_done()))
    add_telemetry(store)
    assembler(store, publisher, versions=versions(settings)).assemble(SESSION_ID)
    report = store.get(paths.report(SESSION_ID))
    assert report["versions"] == {
        "scoring_module": report["versions"]["scoring_module"],
        "quick_model": "azure-openai/gpt-4.1-mini",
        "grader_model": "azure-openai/gpt-4.1",
        "grader_prompt": report["versions"]["grader_prompt"],
        "response_asr": "azure-speech/en-NG",
    }
    assert not any("gemini" in value or "chirp" in value for value in report["versions"].values())


def test_without_azure_versions_the_report_keeps_the_google_ones():
    store, publisher = seeded_store(), MemoryPublisher()
    handler(store, publisher)(event("session.done", session_done()))
    add_telemetry(store)
    assembler(store, publisher).assemble(SESSION_ID)
    versions_ = store.get(paths.report(SESSION_ID))["versions"]
    assert (versions_["quick_model"], versions_["grader_model"]) == (QUICK_MODEL, GRADER_MODEL)


def test_the_azure_versions_name_every_role_the_google_ones_do():
    assert set(versions(azure())) == set(
        ["scoring_module", "quick_model", "grader_model", "grader_prompt", "response_asr"]
    )


def test_core_records_azure_versions_only_for_a_live_azure_run():
    assert main._versions(azure(AI_MODE="live"))["grader_model"] == "azure-openai/gpt-4.1"
    assert main._versions(azure(AI_MODE="fixtures")) is None
    assert main._versions(aloai_env.load({"AI_MODE": "live"})) is None


# ---- the Coach


def test_the_coach_model_is_an_azure_deployment_with_a_fresh_credential_for_each_run():
    tokens = iter(["first", "second"])
    model_for = azure_coach_model(azure(), token=lambda config: next(tokens))
    first, second = model_for("sess_a"), model_for("sess_b")
    assert first.model == "openai/gpt-4.1-coach"
    assert first._additional_args == {
        "api_base": "https://aloai.openai.azure.com/openai/v1/",
        "api_key": "first",
    }
    assert second._additional_args["api_key"] == "second"


def test_the_coach_needs_a_coach_deployment():
    with pytest.raises(aloai_env.ConfigError, match="'coach'"):
        azure_coach_model(azure(AZURE_OPENAI_DEPLOYMENTS='{"grader": "g"}'))


def test_the_summary_is_spoken_and_saved_beside_the_sessions_audio():
    blobs, asked = MemoryBlobs(), []

    def synthesize(ssml):
        asked.append(ssml)
        return b"mp3"

    speaker = AzureSpeaker(blobs, synthesize, "audio", "en-NG-EzinneNeural")
    uri = speaker.speak("Chidi read well today.", "sess_demo_001")
    assert uri == "az://audio/sess_demo_001/summary/summary.mp3"
    assert blobs.read(uri) == b"mp3"
    assert blobs.content_types[uri] == "audio/mpeg"
    [ssml] = asked
    assert 'xml:lang="en-NG"' in ssml and 'name="en-NG-EzinneNeural"' in ssml
    assert '<prosody rate="-10%">Chidi read well today.</prosody>' in ssml
