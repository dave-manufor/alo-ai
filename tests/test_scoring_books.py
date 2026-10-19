"""Book ranking (PRD 9.3): RankScore = 0.50 Fit + 0.30 Sim + 0.20 Culture, top 3."""

import pytest
from aloai_scoring import BookCandidate, book_fit, candidate_levels, rank_books, rank_score

BAND = (2, 3)


def book(book_id="b", arl=2, similarity=0.5, west_african=False) -> BookCandidate:
    return BookCandidate(book_id, arl, similarity, west_african)


@pytest.mark.parametrize(
    "band, levels", [((2, 3), [1, 2, 3, 4]), ((1, 1), [1, 2]), ((11, 12), [10, 11, 12])]
)
def test_candidates_come_from_the_band_and_one_level_either_side(band, levels):
    assert candidate_levels(band) == levels


@pytest.mark.parametrize("arl, fit", [(2, 1.0), (3, 1.0), (1, 0.0), (4, 0.0), (9, 0.0)])
def test_fit_is_full_inside_the_band_and_falls_a_level_at_a_time(arl, fit):
    assert book_fit(arl, BAND) == fit


def test_fit_refuses_a_level_outside_the_scale():
    with pytest.raises(ValueError):
        book_fit(13, BAND)


@pytest.mark.parametrize(
    "candidate, score",
    [
        (book(similarity=1.0, west_african=True), 1.0),
        (book(similarity=0.5), 0.65),
        (book(arl=4, similarity=0.5, west_african=True), 0.35),
        (book(similarity=1.4), 0.8),
        (book(similarity=-0.2), 0.5),
    ],
)
def test_rank_score_weighs_fit_similarity_and_setting(candidate, score):
    assert rank_score(candidate, BAND) == pytest.approx(score)


def test_the_top_three_are_recommended_best_first():
    candidates = [
        book("out_of_band", arl=4, similarity=0.9, west_african=True),
        book("close", similarity=0.9),
        book("nigerian", similarity=0.4, west_african=True),
        book("far", similarity=0.1),
        book("closest", similarity=0.95),
    ]
    assert rank_books(candidates, BAND) == ["nigerian", "closest", "close"]


def test_ties_go_to_the_closer_match_then_the_id():
    candidates = [
        book("b", similarity=0.5, west_african=True),
        book("a", similarity=0.5, west_african=True),
        book("c", arl=3, similarity=0.6),
    ]
    assert rank_books(candidates, BAND) == ["a", "b", "c"]


def test_no_candidates_means_no_books():
    assert rank_books([], BAND) == []
