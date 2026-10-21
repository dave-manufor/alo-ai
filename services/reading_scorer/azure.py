"""The two independent transcripts of a reading on Azure (PRD 5.2; CLOUD=azure; the Google
ones are in transcribers.py).

AzureSpeechReading runs Azure AI Speech on the reading, with the passage's names as phrase
hints and each word's confidence when the service gives one. OpenAIReading asks an Azure
OpenAI transcription deployment for a verbatim transcript. Both read the audio through
Blobs, as 16 kHz FLAC, so neither depends on where it is stored.

Two things to check against the real services before relying on these (the day-1 check, PRD
5.2): that Speech returns a usable confidence for each word (a transcript without any leaves
every word unmarked, as a transcript of all 0.0 does on Google), and that the transcription
model writes what the child said, mistakes included, instead of correcting it to the passage,
which would hide a misreading from the agreement rule (PRD 5.3).
"""

from collections.abc import Callable, Mapping, Sequence

from aloai_azure import Word, pcm16
from aloai_blobs import Blobs

from .transcribers import VERBATIM
from .words import Heard

TRANSCRIBE_TIMEOUT_S = 60


def names(passage: Mapping) -> list[str]:
    """The passage's names, as hints for recognition (the words that carry an IPA)."""
    return sorted({token["clean_text"] for token in passage["tokens"] if token.get("name_ipa")})


class AzureSpeechReading:
    def __init__(
        self, blobs: Blobs, recognize: Callable[[bytes, Sequence[str]], list[Word]]
    ) -> None:
        """recognize is aloai_azure.recognize_words with the settings bound."""
        self._blobs = blobs
        self._recognize = recognize

    def heard(self, audio_uri: str, passage: Mapping) -> list[Heard]:
        words = self._recognize(pcm16(self._blobs.read(audio_uri)), names(passage))
        # 0.0 everywhere means no confidence was computed: no word is unsure.
        unset = bool(words) and all(confidence == 0.0 for _, confidence in words)
        return [Heard(word, None if unset else confidence) for word, confidence in words]


class OpenAIReading:
    def __init__(self, client, deployment: str, blobs: Blobs) -> None:
        """client is an openai.OpenAI on the Azure OpenAI v1 API; deployment is the
        transcription deployment (role "transcribe")."""
        self._client = client
        self._deployment = deployment
        self._blobs = blobs

    def heard(self, audio_uri: str, passage: Mapping) -> list[Heard]:
        response = self._client.audio.transcriptions.create(
            model=self._deployment,
            file=("reading.flac", self._blobs.read(audio_uri), "audio/flac"),
            prompt=VERBATIM,
            temperature=0,
            response_format="json",
            timeout=TRANSCRIBE_TIMEOUT_S,
        )
        return [Heard(word) for word in (response.text or "").split()]
