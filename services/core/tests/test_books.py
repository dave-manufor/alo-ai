"""Book recommendations (PRD 9.3): the embedding, the vector search and the report's books."""

import logging
from types import SimpleNamespace

import pytest
from aloai_events import MemoryPublisher
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from services.core.grader import paths
from services.core.grader.assembly import ReportAssembler
from services.core.grader.books import (
    EMBEDDING_MODEL,
    BookRecommender,
    FirestoreBookSearch,
    FixtureEmbedder,
    VertexEmbedder,
)
from services.core.tests.support import (
    RECORDED,
    SESSION_ID,
    MemoryBookSearch,
    add_telemetry,
    recommender,
    seeded_store,
)
from services.core.tests.test_assembly import graded_store


class FakeQuery:
    def __init__(self, snapshots) -> None:
        self.snapshots = snapshots
        self.calls = []

    def collection(self, name):
        self.calls.append(("collection", name))
        return self

    def where(self, *, filter):
        self.calls.append(("where", filter.field_path, filter.op_string, filter.value))
        return self

    def find_nearest(self, **kwargs):
        self.calls.append(("find_nearest", kwargs))
        return self

    def stream(self):
        return iter(self.snapshots)


def snapshot(book_id, **book):
    return SimpleNamespace(id=book_id, to_dict=lambda: book)


def test_firestore_finds_the_nearest_books_at_the_candidate_levels():
    client = FakeQuery(
        [
            snapshot("b1", arl=2, vector_distance=0.25, west_african_setting=True),
            snapshot("b2", arl=3, vector_distance=0.5),
        ]
    )
    found = FirestoreBookSearch(client).nearest([0.1, 0.2], [1, 2, 3], 15)
    assert [(b.book_id, b.arl, b.similarity, b.west_african) for b in found] == [
        ("b1", 2, 0.75, True),
        ("b2", 3, 0.5, False),
    ]
    collection, levels, ready, (_, nearest) = client.calls
    assert (collection, levels) == (("collection", "books"), ("where", "arl", "in", [1, 2, 3]))
    assert ready == ("where", "held_for_review", "==", False)
    assert nearest["vector_field"] == "embedding"
    assert list(nearest["query_vector"]) == [0.1, 0.2]
    assert (nearest["distance_measure"], nearest["limit"]) == (DistanceMeasure.COSINE, 15)


def test_vertex_embeds_the_interests_as_a_query():
    calls = []

    def embed_content(**request):
        calls.append(request)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=(0.1, 0.2))])

    client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    assert VertexEmbedder(client).embed("animals, food") == [0.1, 0.2]
    [request] = calls
    assert (request["model"], request["contents"]) == (EMBEDDING_MODEL, "animals, food")
    assert request["config"].task_type == "RETRIEVAL_QUERY"


def test_an_unrecorded_interest_has_no_embedding():
    with pytest.raises(LookupError):
        FixtureEmbedder(RECORDED / "embeddings.json").embed("space")


class CountingEmbedder:
    def __init__(self) -> None:
        self.texts = []

    def embed(self, text):
        self.texts.append(text)
        return [0.0, 1.0, 0.0, 0.0]


def test_the_interests_are_embedded_in_one_order():
    embedder = CountingEmbedder()
    BookRecommender(MemoryBookSearch(seeded_store()), embedder).recommend(
        ["food", "animals"], (1, 2)
    )
    assert embedder.texts == ["animals, food"]


def test_no_interests_means_no_search():
    embedder = CountingEmbedder()
    assert BookRecommender(MemoryBookSearch(seeded_store()), embedder).recommend([], (1, 2)) == []
    assert embedder.texts == []


def report_books(store, books=None) -> list[str]:
    add_telemetry(store)
    ReportAssembler(store, MemoryPublisher(), books or recommender(store)).assemble(SESSION_ID)
    return store.get(paths.report(SESSION_ID))["recommendations"]["book_ids"]


def test_the_report_recommends_the_top_three_for_the_passage_topic():
    assert report_books(graded_store()) == ["book_demo_001", "book_demo_002", "book_demo_003"]


def test_the_childs_saved_interests_come_before_the_passage_topic():
    store = graded_store()
    store.merge(paths.child("child_demo_001"), {"saved_tags": ["animals"]})
    assert report_books(store)[0] == "book_demo_002"


class BrokenSearch:
    def nearest(self, vector, levels, limit):
        raise ConnectionError("vector search is down")


def test_a_failed_search_leaves_the_report_without_books(caplog):
    store = graded_store()
    books = BookRecommender(BrokenSearch(), FixtureEmbedder(RECORDED / "embeddings.json"))
    with caplog.at_level(logging.ERROR):
        assert report_books(store, books) == []
    assert "no book recommendations for session sess_demo_001" in caplog.text


def test_a_report_without_a_book_band_searches_nothing():
    store = graded_store()
    store.merge(paths.grading(SESSION_ID), {"session_flags": ["LOW_AUDIO"]})
    embedder = CountingEmbedder()
    assert report_books(store, BookRecommender(BrokenSearch(), embedder)) == []
    assert embedder.texts == []
