"""The two independent transcripts of a reading (PRD 5.2).

ChirpReading runs Chirp 3 batch recognition in the EU, with the passage's names as
speech adaptation and a confidence for every word. GeminiReading asks Gemini 2.5 Flash
for a verbatim transcript. FixtureReading answers from the recorded transcripts in
fixtures/ai/reading/ (AI_MODE=fixtures), named by the audio object's UUID.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from google import genai
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from google.genai import types

from .words import Heard

CHIRP_MODEL = "chirp_3"
CHIRP_LANGUAGE = "en-GB"  # PRD 5.2: the day-1 transcript check confirms or changes it
CHIRP_LOCATION = "eu"
CHIRP_TIMEOUT_S = 120
NAME_BOOST = 10

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TIMEOUT_S = 60
PROMPT_VERSION = "transcribe_v1"
VERBATIM = (
    "Write exactly what the child said, including mistakes, repeats and unfinished words. "
    "Write only the words, with no punctuation, notes or corrections."
)


class Transcriber(Protocol):
    def heard(self, audio_uri: str, passage: Mapping) -> list[Heard]: ...


class ChirpReading:
    def __init__(self, client: speech_v2.SpeechClient, project: str) -> None:
        self._client = client
        self._recognizer = f"projects/{project}/locations/{CHIRP_LOCATION}/recognizers/_"

    def heard(self, audio_uri: str, passage: Mapping) -> list[Heard]:
        request = cloud_speech.BatchRecognizeRequest(
            recognizer=self._recognizer,
            config=cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                model=CHIRP_MODEL,
                language_codes=[CHIRP_LANGUAGE],
                features=cloud_speech.RecognitionFeatures(enable_word_confidence=True),
                adaptation=_names(passage),
            ),
            files=[cloud_speech.BatchRecognizeFileMetadata(uri=audio_uri)],
            recognition_output_config=cloud_speech.RecognitionOutputConfig(
                inline_response_config=cloud_speech.InlineOutputConfig()
            ),
        )
        response = self._client.batch_recognize(request=request).result(timeout=CHIRP_TIMEOUT_S)
        words = [
            word
            for result in response.results[audio_uri].transcript.results
            if result.alternatives
            for word in result.alternatives[0].words
        ]
        # 0.0 everywhere means Speech-to-Text computed no confidence: no word is unsure.
        unset = bool(words) and all(word.confidence == 0.0 for word in words)
        return [Heard(word.word, None if unset else word.confidence) for word in words]


def _names(passage: Mapping) -> cloud_speech.SpeechAdaptation | None:
    names = sorted({token["clean_text"] for token in passage["tokens"] if token.get("name_ipa")})
    if not names:
        return None
    phrases = cloud_speech.PhraseSet(
        phrases=[cloud_speech.PhraseSet.Phrase(value=name, boost=NAME_BOOST) for name in names]
    )
    return cloud_speech.SpeechAdaptation(
        phrase_sets=[cloud_speech.SpeechAdaptation.AdaptationPhraseSet(inline_phrase_set=phrases)]
    )


class GeminiReading:
    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def heard(self, audio_uri: str, passage: Mapping) -> list[Heard]:
        response = self._client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Part.from_uri(file_uri=audio_uri, mime_type="audio/flac"), VERBATIM],
            config=types.GenerateContentConfig(
                temperature=0, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_S * 1000)
            ),
        )
        return [Heard(word) for word in (response.text or "").split()]


class FixtureReading:
    def __init__(self, root: Path, engine: str) -> None:
        self._root = root
        self._engine = engine

    def heard(self, audio_uri: str, passage: Mapping) -> list[Heard]:
        name = f"{Path(urlparse(audio_uri).path).stem}.{self._engine}.json"
        recorded = json.loads((self._root / name).read_text())
        return [Heard(word, confidence) for word, confidence in recorded["words"]]
