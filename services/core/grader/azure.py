"""The grader's Azure counterparts to Gemini, Chirp and Firestore vector search
(CLOUD=azure; the Google ones are in models.py, asr.py and books.py).

AzureGradingModel asks an Azure OpenAI deployment for a GraderOutput; the quick call and
the final grading use the deployments for the roles "quick" and "grader", picked by the
task's model name, which stays QUICK_MODEL or GRADER_MODEL as the role. AzureSpeechTranscriber
transcribes a response with Azure AI Speech. AzureEmbedder embeds the child's interest tags
with the same model the catalogue is embedded with, at 768 dimensions (book.schema.json).
CosmosBookSearch is the nearest-books query over the `books` container. The model never
computes a score: every answer still goes through grade() in models.py, which checks it.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import aloai_scoring as scoring
from aloai_azure import Word, deployment, pcm16
from aloai_blobs import Blobs
from aloai_env import Config

from .asr import without_unset_confidence
from .models import (
    GRADER_TIMEOUT_S,
    QUICK_MODEL,
    QUICK_TIMEOUT_S,
    GradingModel,
    GradingTask,
    _parse,
    _RESPONSE_SCHEMA,
)
from .prompts import PROMPT_VERSION, build_prompt

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 768  # book.schema.json: the same 768 numbers as on Google Cloud
FORMAT = {
    "type": "json_schema",
    # Not strict: the schema has more than strict structured output takes, and grade() checks
    # the answer against it anyway.
    "json_schema": {"name": "grader_output", "schema": _RESPONSE_SCHEMA, "strict": False},
}


class AzureGradingModel:
    def __init__(self, client, quick: str, grader: str) -> None:
        """client is an openai.OpenAI on the Azure OpenAI v1 API; quick and grader are the
        deployment names for the two roles."""
        self._client = client
        self._quick = quick
        self._grader = grader

    def grade(self, task: GradingTask) -> dict:
        quick = task.model == QUICK_MODEL
        prompt = build_prompt(
            passage=task.passage,
            retell=task.retell,
            answers=task.answers,
            primary_class=task.primary_class,
            pass_number=task.pass_number,
        )
        response = self._client.chat.completions.create(
            model=self._quick if quick else self._grader,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format=FORMAT,
            timeout=QUICK_TIMEOUT_S if quick else GRADER_TIMEOUT_S,
        )
        choices = response.choices
        return _parse(choices[0].message.content if choices else None)


class AzureSpeechTranscriber:
    """Response-track transcripts (PRD 5.2): the audio is read through Blobs, as 16 kHz
    FLAC, and recognised by `recognize(pcm, phrases)` (aloai_azure.recognize_words)."""

    def __init__(
        self, blobs: Blobs, recognize: Callable[[bytes, Sequence[str]], list[Word]]
    ) -> None:
        self._blobs = blobs
        self._recognize = recognize

    def words(self, audio_uri: str) -> list[Word]:
        return without_unset_confidence(self._recognize(pcm16(self._blobs.read(audio_uri)), ()))


@dataclass(frozen=True)
class AzureEmbedder:
    client: object  # an openai.OpenAI on the Azure OpenAI v1 API
    deployment: str

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.deployment, input=text, dimensions=EMBEDDING_DIMENSIONS
        )
        return list(response.data[0].embedding)


# Cosmos DB's VectorDistance on a cosine index is the similarity itself (higher is nearer),
# and ORDER BY puts the nearest first. The item id of a book is "books|{book_id}"
# (aloai_store.CosmosStore).
NEAREST = (
    "SELECT TOP @limit c.id AS id, c.d.arl AS arl, "
    "c.d.west_african_setting AS west_african_setting, "
    "VectorDistance(c.d.embedding, @vector) AS similarity "
    "FROM c WHERE ARRAY_CONTAINS(@levels, c.d.arl) AND c.d.held_for_review = false "
    "ORDER BY VectorDistance(c.d.embedding, @vector)"
)


@dataclass(frozen=True)
class CosmosBookSearch:
    container: object  # the `books` azure.cosmos ContainerProxy

    def nearest(
        self, vector: Sequence[float], levels: Sequence[int], limit: int
    ) -> list[scoring.BookCandidate]:
        rows = self.container.query_items(
            query=NEAREST,
            parameters=[
                {"name": "@limit", "value": limit},
                {"name": "@vector", "value": list(vector)},
                {"name": "@levels", "value": list(levels)},
            ],
            enable_cross_partition_query=True,
        )
        return [
            scoring.BookCandidate(
                book_id=row["id"].partition("|")[2],
                arl=row["arl"],
                similarity=row["similarity"],
                west_african=row.get("west_african_setting") or False,
            )
            for row in rows
        ]


def azure_model(client, config: Config) -> GradingModel:
    return AzureGradingModel(client, deployment(config, "quick"), deployment(config, "grader"))


def versions(config: Config) -> dict[str, str]:
    """What the report records as the models used (reading_report `versions`): the Azure
    deployments and the speech locale, not the Gemini names."""
    return {
        "scoring_module": scoring.SCORING_MODULE,
        "quick_model": f"azure-openai/{deployment(config, 'quick')}",
        "grader_model": f"azure-openai/{deployment(config, 'grader')}",
        "grader_prompt": PROMPT_VERSION,
        "response_asr": f"azure-speech/{config.speech_locale}",
    }
