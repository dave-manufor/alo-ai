"""Embedding the catalogue (PRD 9.1, 9.3).

A book's embedding is of one text, book_text(): its description and its topic tags. The
Grader embeds a child's interests with the same model and searches for the nearest books, so
a book and a query must be embedded by the same model, and moving the system to another
cloud (a different embedding model: book.schema.json lists them) means embedding every book
again. reembed_books does that for the books still on another model. The book ingestion job
must embed a new book with book_text() too, so the catalogue never holds two kinds of text.

Vectors are not comparable between models, so a catalogue is never half-moved for long: run
this on the whole catalogue before the Grader searches it on the new model.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import aloai_contracts
from aloai_store import Store

from ..grader.books import Embedder, interests_text

COLLECTION = "books"
DIMENSIONS = 768  # book.schema.json
KNOWN_MODELS = tuple(
    aloai_contracts.load("book.schema.json")["properties"]["embedding_model"]["enum"]
)
_BOOK = aloai_contracts.validator("book.schema.json")


def book_text(book: dict) -> str:
    """The text a book is embedded from: its description, then its topic tags the way a
    child's interests are written (grader/books.interests_text)."""
    return f"{book['description']}\n{interests_text(book['topic_tags'])}"


@dataclass
class ReembedReport:
    done: list[str] = field(default_factory=list)
    already: int = 0  # books already on the model
    failed: dict[str, str] = field(default_factory=dict)  # book_id -> why


def _on_other_models(store: Store, model: str) -> list[dict]:
    return [
        book
        for old in KNOWN_MODELS
        if old != model
        for book in store.where(COLLECTION, "embedding_model", old)
    ]


def reembed_books(
    store: Store,
    embedder: Embedder,
    model: str,
    *,
    dry_run: bool = False,
    only: Sequence[str] | None = None,
) -> ReembedReport:
    """Embed every book that is on another model with `model`, and store the vector with the
    model's name. A book whose new vector is the wrong size, or whose document would no longer
    match the book schema, is reported and left as it was. `only` limits it to those book ids."""
    if model not in KNOWN_MODELS:
        raise ValueError(f"{model!r} is not an embedding model book.schema.json allows")
    report = ReembedReport(already=len(store.where(COLLECTION, "embedding_model", model)))
    for book in _on_other_models(store, model):
        book_id = book["book_id"]
        if only is not None and book_id not in only:
            continue
        try:
            vector = embedder.embed(book_text(book))
            if len(vector) != DIMENSIONS:
                raise ValueError(f"the vector has {len(vector)} numbers, not {DIMENSIONS}")
            _BOOK.validate(book | {"embedding": vector, "embedding_model": model})
        except Exception as error:  # noqa: BLE001 - one bad book must not stop the run
            report.failed[book_id] = str(error)[:300]
            continue
        if not dry_run:
            store.merge(f"{COLLECTION}/{book_id}", {"embedding": vector, "embedding_model": model})
        report.done.append(book_id)
    return report
