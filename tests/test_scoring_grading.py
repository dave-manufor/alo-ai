"""Tests for the parts of aloai_scoring that final grading uses (PRD 6.3, 7.2, 7.4, 8).

Kept apart from test_scoring.py so each file stays small; together they keep the
library at 100% line coverage.
"""

import aloai_scoring as scoring
import pytest
from aloai_scoring import CombinedItems, CombinedRetell, Comprehension

# ---- 6.3 the comprehension numbers the report shows


def test_chidi_comprehension_shows_coverage_and_item_score_as_the_report_does():
    assert scoring.comprehension(6.5, 15, [1, 2, 0]) == Comprehension(
        score=58.9, retell_coverage=0.72, item_score=0.5
    )


@pytest.mark.parametrize(
    "quick, final, agreement", [([1, 2, 0], [1, 2, 0], 1.0), ([1, 2, 0], [1, 1, 0], 0.67)]
)
def test_quick_and_final_item_agreement(quick, final, agreement):
    assert scoring.item_agreement(quick, final) == agreement


@pytest.mark.parametrize("quick, final", [([], []), ([1, 2], [1, 2, 0])])
def test_agreement_needs_the_same_items(quick, final):
    with pytest.raises(ValueError):
        scoring.item_agreement(quick, final)


# ---- 7.2 retell passes


@pytest.mark.parametrize("a, b, credit", [(6.5, 7.5, 7.0), (6.5, 6.5, 6.5), (4.0, 5.0, 4.5)])
def test_retell_passes_within_one_point_take_the_mean(a, b, credit):
    assert not scoring.retell_needs_third_pass(a, b)
    assert scoring.combine_retell_passes(a, b) == CombinedRetell(credit=credit, disagreement=False)


def test_retell_passes_further_apart_need_a_third_pass():
    assert scoring.retell_needs_third_pass(4.0, 5.5)
    with pytest.raises(ValueError):
        scoring.combine_retell_passes(4.0, 5.5)


@pytest.mark.parametrize(
    "a, b, c, combined",
    [
        (4.0, 6.0, 5.0, CombinedRetell(credit=5.0, disagreement=False)),
        (2.0, 6.0, 4.5, CombinedRetell(credit=4.5, disagreement=True)),
        (6.0, 3.5, 6.0, CombinedRetell(credit=6.0, disagreement=True)),
    ],
)
def test_three_retell_passes_take_the_median_and_flag_a_wide_spread(a, b, c, combined):
    assert scoring.combine_retell_passes(a, b, c) == combined


# ---- 7.2 item passes


def test_item_passes_that_agree_stand():
    assert not scoring.items_need_third_pass([2, 1, 0], [2, 1, 0])
    assert scoring.combine_item_passes([2, 1, 0], [2, 1, 0]) == CombinedItems((2, 1, 0), False)


def test_item_passes_that_differ_need_a_third_pass():
    assert scoring.items_need_third_pass([2, 1, 0], [2, 2, 0])
    with pytest.raises(ValueError):
        scoring.combine_item_passes([2, 1, 0], [2, 2, 0])


def test_a_third_item_pass_settles_each_item_by_majority():
    combined = scoring.combine_item_passes([2, 1, 0], [2, 2, 0], [2, 1, 1])
    assert combined == CombinedItems(points=(2, 1, 0), disagreement=False)


def test_an_item_all_three_passes_score_differently_is_a_disagreement():
    combined = scoring.combine_item_passes([2, 0], [2, 1], [2, 2])
    assert combined == CombinedItems(points=(2, 1), disagreement=True)


@pytest.mark.parametrize("b, c", [([2], [2, 1]), ([2, 1], [2])])
def test_passes_must_score_the_same_items(b, c):
    with pytest.raises(ValueError):
        scoring.combine_item_passes([2, 0], b, c)


# ---- 8 book band


@pytest.mark.parametrize(
    "profile, band",
    [
        ("ON_TRACK", (5, 6)),
        ("UNDERSTANDS_BUILDING_WORD_READING", (4, 5)),
        ("DECODING_LIMITED", (3, 4)),
        ("FLUENT_NEEDS_LANGUAGE_SUPPORT", (4, 5)),
        ("NEEDS_SUPPORT_IN_BOTH", (3, 4)),
        ("COMPREHENSION_STRATEGY_GAP", (5, 5)),
    ],
)
def test_book_band_follows_the_profile(profile, band):
    assert scoring.book_band(profile, 5) == band


def test_chidi_book_band_matches_the_worked_session():
    assert scoring.book_band("FLUENT_NEEDS_LANGUAGE_SUPPORT", 4) == (3, 4)


@pytest.mark.parametrize(
    "profile, arl, band", [("DECODING_LIMITED", 1, (1, 1)), ("ON_TRACK", 12, (12, 12))]
)
def test_book_band_stays_within_1_to_12(profile, arl, band):
    assert scoring.book_band(profile, arl) == band


@pytest.mark.parametrize("profile, arl", [("INSUFFICIENT_EVIDENCE", 5), ("ON_TRACK", None)])
def test_no_book_band_without_evidence_or_a_level(profile, arl):
    assert scoring.book_band(profile, arl) is None


def test_book_band_checks_the_level():
    with pytest.raises(ValueError):
        scoring.book_band("ON_TRACK", 13)
