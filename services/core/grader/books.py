"""Book recommendations for the report (PRD 9.3, SDD 7 step 5).

The child's interest tags are embedded with the same pinned Vertex AI model the book
ingestion job uses (W2), Firestore vector search returns the nearest catalogue books
within the profile's band and one level either side, and aloai_scoring ranks them.

Fields read from books/{book_id} (schemas/book.schema.json): arl, embedding (a vector
field), west_african_setting and held_for_review. Only catalogue books can be returned,
and never one held for a person to check its level.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import aloai_scoring as scoring
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from google.genai import types

EMBEDDING_MODEL = "text-embedding-005"
DISTANCE_FIELD = "vector_distance"


def interests_text(tags: Sequence[str]) -> str:
    return ", ".join(sorted(tags))


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class VertexEmbedder:
    client: genai.Client

    def embed(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return list(response.embeddings[0].values)


@dataclass(frozen=True)
class FixtureEmbedder:
    """The vectors in fixtures/ai/embeddings.json, by interests text."""

    path: Path

    def embed(self, text: str) -> list[float]:
        vectors = json.loads(self.path.read_text())["vectors"]
        if text not in vectors:
            raise LookupError(f"no recorded embedding for {text!r}")
        return vectors[text]


class BookSearch(Protocol):
    def nearest(
        self, vector: Sequence[float], levels: Sequence[int], limit: int
    ) -> list[scoring.BookCandidate]: ...


@dataclass(frozen=True)
class FirestoreBookSearch:
    client: firestore.Client

    def nearest(
        self, vector: Sequence[float], levels: Sequence[int], limit: int
    ) -> list[scoring.BookCandidate]:
        query = (
            self.client.collection("books")
            .where(filter=FieldFilter("arl", "in", list(levels)))
            .where(filter=FieldFilter("held_for_review", "==", False))
            .find_nearest(
                vector_field="embedding",
                query_vector=Vector(list(vector)),
                distance_measure=DistanceMeasure.COSINE,
                limit=limit,
                distance_result_field=DISTANCE_FIELD,
            )
        )
        return [_candidate(snapshot.id, snapshot.to_dict()) for snapshot in query.stream()]


def _candidate(book_id: str, book: dict) -> scoring.BookCandidate:
    """Firestore's cosine distance is 1 minus the cosine similarity."""
    return scoring.BookCandidate(
        book_id=book_id,
        arl=book["arl"],
        similarity=1 - book[DISTANCE_FIELD],
        west_african=book.get("west_african_setting", False),
    )


@dataclass(frozen=True)
class BookRecommender:
    search: BookSearch
    embedder: Embedder

    def recommend(self, tags: Sequence[str], band: tuple[int, int]) -> list[str]:
        if not tags:
            return []
        vector = self.embedder.embed(interests_text(tags))
        candidates = self.search.nearest(
            vector, scoring.candidate_levels(band), scoring.BOOK_CANDIDATES
        )
        return scoring.rank_books(candidates, band)
