"""The Reading Scorer's two transcripts on Azure, against fake clients: no test reaches
Azure. These do not replace the day-1 check on real recordings (PRD 5.2)."""

import io
import json
from types import SimpleNamespace

import aloai_env
import numpy as np
import pytest
import soundfile
from aloai_blobs import BlobNotFound, MemoryBlobs
from services.reading_scorer import main
from services.reading_scorer.azure import AzureSpeechReading, OpenAIReading, names
from services.reading_scorer.transcribers import VERBATIM
from services.reading_scorer.words import Heard

from .support import passage

AUDIO = "az://audio/3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10/READING/a1b2c3d4.flac"


def flac(samples, rate=16_000) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, rate, format="FLAC")
    return buffer.getvalue()


AUDIO_BYTES = flac((0.1 * np.ones(3_200)).astype(np.float32))


def blobs() -> MemoryBlobs:
    return MemoryBlobs({AUDIO: AUDIO_BYTES})


# ---- Azure AI Speech


def speech(words):
    heard = []

    def recognize(pcm, phrases):
        heard.append((len(pcm), tuple(phrases)))
        return words

    return AzureSpeechReading(blobs(), recognize), heard


def test_the_reading_is_recognised_with_the_passages_names_as_hints():
    reading, heard = speech([("ada", 0.9), ("ran", 0.3)])
    assert reading.heard(AUDIO, passage()) == [Heard("ada", 0.9), Heard("ran", 0.3)]
    [(size, phrases)] = heard
    assert size == 2 * 3_200
    assert phrases == tuple(names(passage())) != ()


def test_the_names_are_the_words_that_carry_an_ipa_once_each_and_sorted():
    market = {
        "tokens": [
            {"clean_text": "tunde", "name_ipa": "ˈtundɛ"},
            {"clean_text": "ada", "name_ipa": "ˈɑːdɑ"},
            {"clean_text": "ran", "name_ipa": None},
            {"clean_text": "tunde", "name_ipa": "ˈtundɛ"},
            {"clean_text": "the"},
        ]
    }
    assert names(market) == ["ada", "tunde"]
    assert names({"tokens": [{"clean_text": "ran"}]}) == []


def test_a_transcript_with_no_confidence_at_all_leaves_every_word_unmarked():
    for words in ([("ada", 0.0), ("ran", 0.0)], [("ada", None), ("ran", None)]):
        reading, _ = speech(words)
        assert reading.heard(AUDIO, passage()) == [Heard("ada"), Heard("ran")]


def test_one_real_zero_among_other_confidences_is_kept():
    reading, _ = speech([("ada", 0.0), ("ran", 0.8)])
    assert reading.heard(AUDIO, passage()) == [Heard("ada", 0.0), Heard("ran", 0.8)]


def test_nothing_heard_is_an_empty_transcript():
    reading, _ = speech([])
    assert reading.heard(AUDIO, passage()) == []


def test_a_reading_that_is_not_in_storage_is_a_lookup_error_for_the_handler_to_park():
    reading = AzureSpeechReading(MemoryBlobs(), lambda pcm, phrases: [])
    with pytest.raises(BlobNotFound):
        reading.heard(AUDIO, passage())


# ---- Azure OpenAI transcription


class TranscriptionsFake:
    def __init__(self, text):
        self.calls = []
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._create))
        self._text = text

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self._text)


def test_the_reading_is_sent_for_a_verbatim_transcript_at_temperature_zero():
    client = TranscriptionsFake("ada ran to to the market")
    reading = OpenAIReading(client, "gpt-4o-transcribe", blobs())
    assert reading.heard(AUDIO, passage()) == [
        Heard("ada"),
        Heard("ran"),
        Heard("to"),
        Heard("to"),
        Heard("the"),
        Heard("market"),
    ]
    [call] = client.calls
    assert call["model"] == "gpt-4o-transcribe"
    assert call["file"] == ("reading.flac", AUDIO_BYTES, "audio/flac")
    assert call["prompt"] == VERBATIM
    assert call["temperature"] == 0
    assert call["response_format"] == "json"
    assert call["timeout"] == 60


@pytest.mark.parametrize("text", ["", None, "   "])
def test_a_transcript_with_no_words_is_empty(text):
    reading = OpenAIReading(TranscriptionsFake(text), "gpt-4o-transcribe", blobs())
    assert reading.heard(AUDIO, passage()) == []


def test_a_reading_that_is_not_in_storage_is_not_sent():
    client = TranscriptionsFake("ada")
    with pytest.raises(BlobNotFound):
        OpenAIReading(client, "gpt-4o-transcribe", MemoryBlobs()).heard(AUDIO, passage())
    assert client.calls == []


# ---- the Scorer's wiring


def azure(**more) -> aloai_env.Config:
    env = {
        "ALO_ENV": "local",
        "CLOUD": "azure",
        "AI_MODE": "live",
        "AZURE_OPENAI_ENDPOINT": "https://aloai.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENTS": json.dumps({"transcribe": "gpt-4o-transcribe"}),
    }
    return aloai_env.load(env | more)


def test_live_azure_uses_azure_speech_and_the_transcription_deployment(monkeypatch):
    monkeypatch.setattr(main, "open_openai", lambda config: SimpleNamespace(client="openai"))
    first, second = main._transcribers(azure(), blobs())
    assert isinstance(first, AzureSpeechReading)
    assert isinstance(second, OpenAIReading)
    assert second._deployment == "gpt-4o-transcribe"


def test_with_one_transcript_no_second_transcriber_or_openai_client_is_built(monkeypatch):
    def refuse(config):
        raise AssertionError("an OpenAI client was built")

    monkeypatch.setattr(main, "open_openai", refuse)
    first, second = main._transcribers(azure(AZURE_OPENAI_DEPLOYMENTS="{}"), blobs(), second=False)
    assert isinstance(first, AzureSpeechReading)
    assert second is None


def test_recorded_transcripts_can_be_single_too():
    first, second = main._transcribers(azure(AI_MODE="fixtures"), MemoryBlobs(), second=False)
    assert type(first).__name__ == "FixtureReading"
    assert second is None


@pytest.mark.parametrize(("value", "expected"), [(None, True), ("on", True), ("off", False)])
def test_the_second_transcript_setting_defaults_to_on(value, expected):
    env = {} if value is None else {"SECOND_TRANSCRIPT": value}
    assert main._second_transcript(env) is expected


def test_the_second_transcript_setting_must_be_on_or_off():
    with pytest.raises(aloai_env.ConfigError, match="SECOND_TRANSCRIPT"):
        main._second_transcript({"SECOND_TRANSCRIPT": "maybe"})


def test_live_azure_needs_a_transcription_deployment(monkeypatch):
    monkeypatch.setattr(main, "open_openai", lambda config: SimpleNamespace(client="openai"))
    with pytest.raises(aloai_env.ConfigError, match="'transcribe'"):
        main._transcribers(azure(AZURE_OPENAI_DEPLOYMENTS='{"grader": "g"}'), blobs())


def test_recorded_transcripts_need_no_azure():
    first, second = main._transcribers(azure(AI_MODE="fixtures"), MemoryBlobs())
    assert type(first).__name__ == type(second).__name__ == "FixtureReading"
