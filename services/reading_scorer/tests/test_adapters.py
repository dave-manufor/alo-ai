"""The scorer's adapters to Chirp 3, Gemini and Cloud Storage, against fake clients: no
test reaches a Google service."""

import io
import json
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile
from services.reading_scorer.audio import GcsAudio
from services.reading_scorer.tests.support import READING, RECORDED, passage
from services.reading_scorer.transcribers import (
    VERBATIM,
    ChirpReading,
    FixtureReading,
    GeminiReading,
)
from services.reading_scorer.words import Heard


def word(text, confidence):
    return SimpleNamespace(word=text, confidence=confidence)


def test_chirp_batch_recognition_boosts_the_passage_names_and_returns_word_confidence():
    results = [
        SimpleNamespace(alternatives=[SimpleNamespace(words=[word("ada", 0.9), word("and", 0.8)])]),
        SimpleNamespace(alternatives=[]),
    ]
    response = SimpleNamespace(
        results={READING: SimpleNamespace(transcript=SimpleNamespace(results=results))}
    )
    requests = []

    def batch_recognize(request):
        requests.append(request)
        return SimpleNamespace(result=lambda timeout: response)

    chirp = ChirpReading(SimpleNamespace(batch_recognize=batch_recognize), "aloai-dev")
    assert chirp.heard(READING, passage()) == [Heard("ada", 0.9), Heard("and", 0.8)]
    [request] = requests
    assert request.recognizer == "projects/aloai-dev/locations/eu/recognizers/_"
    assert request.files[0].uri == READING
    assert request.config.model == "chirp_3"
    assert request.config.features.enable_word_confidence
    phrases = request.config.adaptation.phrase_sets[0].inline_phrase_set.phrases
    assert [phrase.value for phrase in phrases] == ["ada"]


def test_a_passage_without_names_needs_no_adaptation():
    unnamed = passage()
    for token in unnamed["tokens"]:
        token["name_ipa"] = None
    response = SimpleNamespace(
        results={READING: SimpleNamespace(transcript=SimpleNamespace(results=[]))}
    )
    requests = []

    def batch_recognize(request):
        requests.append(request)
        return SimpleNamespace(result=lambda timeout: response)

    ChirpReading(SimpleNamespace(batch_recognize=batch_recognize), "aloai-dev").heard(
        READING, unnamed
    )
    assert not requests[0].config.adaptation.phrase_sets


def test_gemini_is_asked_for_a_verbatim_transcript_of_the_audio():
    calls = []

    def generate_content(*, model, contents, config):
        calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        return SimpleNamespace(text="ada and mummy went")

    gemini = GeminiReading(
        SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )
    assert gemini.heard(READING, passage()) == [Heard(w) for w in ("ada", "and", "mummy", "went")]
    [call] = calls
    audio, prompt = call.contents
    assert (audio.file_data.file_uri, audio.file_data.mime_type) == (READING, "audio/flac")
    assert prompt == VERBATIM
    assert (call.model, call.config.temperature) == ("gemini-2.5-flash", 0)
    assert call.config.http_options.timeout == 60_000


def test_gemini_returning_nothing_heard_nothing():
    gemini = GeminiReading(
        SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda **_: SimpleNamespace(text=None))
        )
    )
    assert gemini.heard(READING, passage()) == []


def test_recorded_transcripts_are_found_by_the_audio_object_name():
    heard = FixtureReading(RECORDED, "gemini").heard(READING, passage())
    assert heard[:3] == [Heard("ada"), Heard("and"), Heard("mummy")]


def flac(samples, rate) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, rate, format="FLAC")
    return buffer.getvalue()


def storage_with(data: bytes, requested: list):
    def blob(name):
        requested.append(name)
        return SimpleNamespace(download_as_bytes=lambda: data)

    return SimpleNamespace(bucket=lambda name: requested.append(name) or SimpleNamespace(blob=blob))


def test_the_reading_is_read_from_cloud_storage_as_16_khz_mono():
    requested = []
    tone = 0.1 * np.sin(np.linspace(0, 100, 16_000)).astype(np.float32)
    audio = GcsAudio(storage_with(flac(tone, 16_000), requested)).load(READING)
    assert requested == [
        "aloai-dev-audio",
        "3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10/READING/a1b2c3d4-0000-4000-8000-000000000001.flac",
    ]
    assert audio.samples.shape == (16_000,)
    assert np.allclose(audio.samples, tone, atol=1e-3)


def test_audio_at_another_sample_rate_is_refused():
    data = flac(np.zeros(8_000, dtype=np.float32), 8_000)
    with pytest.raises(ValueError):
        GcsAudio(storage_with(data, [])).load(READING)


def test_the_recorded_transcripts_are_valid_json():
    for path in RECORDED.glob("*.json"):
        assert "words" in json.loads(path.read_text())
