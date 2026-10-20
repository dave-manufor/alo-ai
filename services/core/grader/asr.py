"""Response-track transcripts (PRD 5.2, 7.1): Chirp 3 on each retell and answer, with
low-confidence words written as [?word?] for the grader.

ChirpTranscriber calls Speech-to-Text in the EU. Speech-to-Text leaves a word's
confidence at 0.0 when it does not compute one, so a transcript in which every word is
0.0 has no confidence at all, and none of its words is marked. FixtureTranscriber
answers from the recorded words in fixtures/ai/asr/, named by the audio object's UUID.
"""

import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

LOW_CONFIDENCE = 0.5  # PRD 7.1 gives no value; this is the reading track's [CAL] 0.5 (5.3)
CHIRP_MODEL = "chirp_3"
CHIRP_LANGUAGE = "en-GB"  # PRD 5.2: the day-1 transcript check confirms or changes it
CHIRP_LOCATION = "eu"

Word = tuple[str, float | None]


class Transcriber(Protocol):
    def words(self, audio_uri: str) -> list[Word]: ...


def transcript(words: list[Word]) -> str:
    return " ".join(
        f"[?{word}?]" if confidence is not None and confidence < LOW_CONFIDENCE else word
        for word, confidence in words
    )


def without_unset_confidence(words: list[Word]) -> list[Word]:
    if words and all(confidence == 0.0 for _, confidence in words):
        return [(word, None) for word, _ in words]
    return words


class ChirpTranscriber:
    def __init__(self, client: speech_v2.SpeechClient, project: str) -> None:
        self._client = client
        self._recognizer = f"projects/{project}/locations/{CHIRP_LOCATION}/recognizers/_"
        self._config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            model=CHIRP_MODEL,
            language_codes=[CHIRP_LANGUAGE],
            features=cloud_speech.RecognitionFeatures(enable_word_confidence=True),
        )

    def words(self, audio_uri: str) -> list[Word]:
        request = cloud_speech.RecognizeRequest(
            recognizer=self._recognizer, config=self._config, uri=audio_uri
        )
        response = self._client.recognize(request=request)
        return without_unset_confidence(
            [
                (word.word, word.confidence)
                for result in response.results
                if result.alternatives
                for word in result.alternatives[0].words
            ]
        )


class FixtureTranscriber:
    def __init__(self, root: Path) -> None:
        self._root = root

    def words(self, audio_uri: str) -> list[Word]:
        recorded = json.loads(
            (self._root / f"{Path(urlparse(audio_uri).path).stem}.json").read_text()
        )
        return [(word, confidence) for word, confidence in recorded["words"]]
