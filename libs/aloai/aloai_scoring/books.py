"""Book ranking (PRD 9.3). Vector search finds the candidates; their order is computed
here, from how well each book's level fits the profile's band, how close it is to the
child's interests, and whether it is set in Nigeria or West Africa."""

from collections.abc import Sequence
from dataclasses import dataclass

from .constants import (
    BOOK_CANDIDATE_MARGIN,
    BOOKS_RECOMMENDED,
    RANK_CULTURE_WEIGHT,
    RANK_FIT_WEIGHT,
    RANK_SIM_WEIGHT,
    check_arl,
    clamp_arl,
)


@dataclass(frozen=True)
class BookCandidate:
    """similarity: cosine similarity between the book's and the interests' embeddings."""

    book_id: str
    arl: int
    similarity: float
    west_african: bool


def candidate_levels(band: tuple[int, int]) -> list[int]:
    """The levels vector search may return: the band and one level either side."""
    low, high = band
    return list(
        range(clamp_arl(low - BOOK_CANDIDATE_MARGIN), clamp_arl(high + BOOK_CANDIDATE_MARGIN) + 1)
    )


def book_fit(arl: int, band: tuple[int, int]) -> float:
    """1 inside the band, falling by 1 for each level outside it."""
    check_arl(arl)
    low, high = band
    return max(0.0, 1.0 - max(low - arl, arl - high, 0))


def rank_score(book: BookCandidate, band: tuple[int, int]) -> float:
    similarity = min(1.0, max(0.0, book.similarity))
    return (
        RANK_FIT_WEIGHT * book_fit(book.arl, band)
        + RANK_SIM_WEIGHT * similarity
        + RANK_CULTURE_WEIGHT * book.west_african
    )


def rank_books(candidates: Sequence[BookCandidate], band: tuple[int, int]) -> list[str]:
    """The ids of the books to recommend, best first. Ties go to the closer interest
    match, then to the book id, so the order never depends on the search's."""
    ranked = sorted(
        candidates, key=lambda book: (-rank_score(book, band), -book.similarity, book.book_id)
    )
    return [book.book_id for book in ranked[:BOOKS_RECOMMENDED]]
