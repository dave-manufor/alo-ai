"""Tests for aloai_scoring (PRD 6). The library must stay at 100% line coverage.

Chidi's worked session (docs/Chidis_AloAI_Session.pdf) is the acceptance example:
every number it shows must come out of these functions unchanged. Expected values
are written out from the PRD rather than read from the module's constants, so a
[CAL] change has to change a test too.
"""

from datetime import date
from itertools import product

import aloai_scoring as scoring
import pytest
from aloai_scoring import ListeningOutcome, Profile, ReportedLevel

PROFILE_CODES = {
    "ON_TRACK",
    "UNDERSTANDS_BUILDING_WORD_READING",
    "DECODING_LIMITED",
    "FLUENT_NEEDS_LANGUAGE_SUPPORT",
    "NEEDS_SUPPORT_IN_BOTH",
    "COMPREHENSION_STRATEGY_GAP",
    "INSUFFICIENT_EVIDENCE",
}


def reading(**counts):
    values = {
        "words_attempted": 100,
        "reading_seconds": 60.0,
        "substitutions": 0,
        "omissions": 0,
        "told": 0,
        "told_waits": 0,
        "mispronunciations": 0,
        "self_corrections": 0,
        "uncertain": 0,
    }
    return scoring.fluency(**(values | counts))


def shown(value, digits=1):
    """A number as the report shows it; the library itself keeps it exact."""
    return None if value is None else round(value, digits)


def profile(d_ok=True, rc=None, lc=None, *, flags=(), stopped=False):
    return scoring.assign_profile(
        flags=flags, reading_stopped_early=stopped, d_ok=d_ok, rc=rc, lc=lc
    )


# ---- Chidi's worked session


def test_chidi_fluency_matches_the_worked_session():
    # The worked session timed 80 s under the old 3 s wait. Chidi's told word is token 35,
    # mid-passage, so under today's 5 s wait the same reading measures 82 s, and WCPM
    # takes the extra 2 s off again: 60 x 125 / 80 s.
    f = reading(
        words_attempted=128,
        reading_seconds=82.0,
        substitutions=1,
        omissions=1,
        told=1,
        told_waits=1,
        self_corrections=1,
    )
    assert (f.words_correct, shown(f.accuracy_pct), shown(f.wcpm)) == (125, 97.7, 93.8)
    assert (shown(f.self_correction_ratio, 2), f.reading_seconds) == (0.33, 82.0)
    assert f.flags == ()


def test_chidi_profile_and_levels_match_the_worked_session():
    d_ok = scoring.word_reading_ok(97.7, 93.8, 3)
    rc = scoring.comprehension_score(
        scoring.retell_coverage(6.5, 15), scoring.item_score([1, 2, 0])
    )
    lc = scoring.comprehension_score(scoring.retell_coverage(4.0, 12), scoring.item_score([2, 0]))
    assert (d_ok, shown(rc), shown(lc)) == (True, 58.9, 52.2)
    assert scoring.run_listening_module(rc)
    assert scoring.listening_outcome(True, rc) == ListeningOutcome(lc_used=True, flag=None)
    assert profile(d_ok, rc, lc) == Profile("FLUENT_NEEDS_LANGUAGE_SUPPORT", provisional=False)

    band = scoring.performance_band(97.7, rc)
    assert band == "SUPPORTED"
    assert scoring.reported_level(5, band) == ReportedLevel(arl=4, at_least=False)
    assert scoring.next_passage_level(5, band) == 4
    assert scoring.approx_primary_class(4) == 2
    assert scoring.start_arl(3, date(2026, 10, 14)) == 5


# ---- 6.1 fluency


def test_scores_divide_by_words_attempted_not_passage_length():
    # PRD 0, v1.1 row 1: 30 of 100 words reached, 2 errors, 60 s.
    f = reading(words_attempted=30, substitutions=2)
    assert (shown(f.accuracy_pct), f.wcpm) == (93.3, 28.0)


def test_every_error_type_counts_against_the_child():
    f = reading(substitutions=1, omissions=2, told=3, mispronunciations=4)
    assert (f.words_correct, f.accuracy_pct, f.wcpm) == (90, 90.0, 90.0)


def test_uncertain_words_count_neither_for_nor_against():
    f = reading(substitutions=5, uncertain=5)
    assert (f.words_correct, shown(f.accuracy_pct), f.wcpm) == (90, 94.7, 90.0)


def test_reading_time_is_capped_at_90_seconds():
    f = reading(reading_seconds=120.0)
    assert (f.reading_seconds, shown(f.wcpm)) == (90, 66.7)


def test_wcpm_leaves_out_the_told_wait_beyond_the_norms_3_seconds():
    # PRD 4.1 waits 5 s before "That word is X."; the WCPM_CUT norms waited 3 s.
    f = reading(reading_seconds=64.0, told=2, told_waits=2)
    assert (f.reading_seconds, f.wcpm) == (64.0, 98.0)


def test_a_told_first_word_has_no_wait_inside_the_reading():
    f = reading(reading_seconds=64.0, told=1, told_waits=0)
    assert f.wcpm == 60 * 99 / 64


def test_told_waits_that_cannot_fit_in_the_reading_are_refused():
    with pytest.raises(ValueError, match="cannot fit"):
        reading(reading_seconds=9.9, told=2, told_waits=2)
    assert reading(reading_seconds=10.0, told=2, told_waits=2).wcpm == 60 * 98 / 6


def test_the_cuts_compare_the_exact_number_not_the_one_shown():
    # 949 of 999 words is 94.995%: shown as 95.0, still below the 95% cut.
    f = reading(words_attempted=999, substitutions=50, reading_seconds=600.0)
    assert shown(f.accuracy_pct) == 95.0
    assert scoring.word_reading_ok(f.accuracy_pct, f.wcpm, 1) is False
    assert scoring.run_listening_module(77.96) is True


def test_told_words_are_left_out_of_the_self_correction_ratio():
    f = reading(substitutions=1, told=3, self_corrections=1)
    assert f.self_correction_ratio == 0.5


def test_no_misreads_and_no_self_corrections_has_no_ratio():
    assert reading(told=2).self_correction_ratio is None


@pytest.mark.parametrize("seconds, flagged", [(59.9, True), (60.0, False)])
def test_a_reading_under_60_seconds_is_short(seconds, flagged):
    assert ("SHORT_READING" in reading(reading_seconds=seconds).flags) is flagged


@pytest.mark.parametrize("uncertain, flagged", [(5, False), (6, True)])
def test_more_than_5_percent_uncertain_words_is_flagged(uncertain, flagged):
    assert ("HIGH_UNCERTAINTY" in reading(uncertain=uncertain).flags) is flagged


@pytest.mark.parametrize("attempted, uncertain", [(0, 0), (3, 3)])
def test_no_scored_words_gives_no_accuracy_or_wcpm(attempted, uncertain):
    f = reading(words_attempted=attempted, uncertain=uncertain)
    assert (f.words_correct, f.accuracy_pct, f.wcpm) == (0, None, None)


def test_no_reading_time_gives_no_wcpm():
    f = reading(reading_seconds=0.0)
    assert (f.accuracy_pct, f.wcpm) == (100.0, None)


@pytest.mark.parametrize(
    "counts",
    [
        {"words_attempted": -1},
        {"omissions": -1},
        {"reading_seconds": -0.5},
        {"words_attempted": 5, "substitutions": 4, "uncertain": 2},
        {"told": 1, "told_waits": 2},
        {"told_waits": -1},
    ],
)
def test_impossible_counts_are_refused(counts):
    with pytest.raises(ValueError):
        reading(**counts)


# ---- 6.2 word reading


@pytest.mark.parametrize(
    "primary_class, cut", [(1, 34), (2, 59), (3, 79), (4, 95), (5, 109), (6, 109)]
)
def test_word_reading_needs_the_class_wcpm_cut(primary_class, cut):
    assert scoring.word_reading_ok(95.0, cut, primary_class) is True
    assert scoring.word_reading_ok(95.0, cut - 0.1, primary_class) is False


def test_word_reading_needs_95_percent_accuracy():
    assert scoring.word_reading_ok(94.9, 200.0, 3) is False


@pytest.mark.parametrize("accuracy, wcpm", [(None, 80.0), (97.0, None)])
def test_word_reading_is_unknown_without_fluency(accuracy, wcpm):
    assert scoring.word_reading_ok(accuracy, wcpm, 3) is None


@pytest.mark.parametrize("primary_class", [0, 7])
def test_primary_class_must_be_1_to_6(primary_class):
    with pytest.raises(ValueError):
        scoring.word_reading_ok(97.0, 80.0, primary_class)


# ---- 6.3 comprehension


def test_weighted_credit_sums_weight_times_credit():
    assert scoring.weighted_credit([(2, 1), (1, 0.5), (2, 0), (1, 1)]) == 3.5


@pytest.mark.parametrize("pair", [(3, 1), (0, 1), (1, 0.25), (2, 2)])
def test_weights_and_credits_outside_the_rubric_are_refused(pair):
    with pytest.raises(ValueError):
        scoring.weighted_credit([pair])


@pytest.mark.parametrize("credit, coverage", [(9, 1.0), (12, 1.0), (4.5, 0.5), (0, 0.0)])
def test_full_retell_credit_at_60_percent_coverage(credit, coverage):
    assert scoring.retell_coverage(credit, 15) == coverage


@pytest.mark.parametrize("credit, total", [(1, 0), (16, 15), (-1, 15)])
def test_retell_credit_must_fit_the_total_weight(credit, total):
    with pytest.raises(ValueError):
        scoring.retell_coverage(credit, total)


@pytest.mark.parametrize("points, score", [([1, 2, 0], 0.5), ([2, 2], 1.0), ([1], 0.5)])
def test_item_score_works_for_any_number_of_items(points, score):
    assert scoring.item_score(points) == score


@pytest.mark.parametrize("points", [[], [3], [-1], [2, 1, 5]])
def test_item_points_outside_0_to_2_are_refused(points):
    with pytest.raises(ValueError):
        scoring.item_score(points)


@pytest.mark.parametrize(
    "coverage, items, score", [(1, 1, 100.0), (0, 0, 0.0), (1, 0, 40.0), (0, 1, 60.0)]
)
def test_comprehension_weighs_retell_40_and_items_60(coverage, items, score):
    assert scoring.comprehension_score(coverage, items) == score


@pytest.mark.parametrize("coverage, items", [(1.1, 0.5), (0.5, -0.1)])
def test_comprehension_inputs_must_be_shares(coverage, items):
    with pytest.raises(ValueError):
        scoring.comprehension_score(coverage, items)


# ---- 6.5 listening module


@pytest.mark.parametrize("quick_rc, runs", [(77.9, True), (78.0, False), (95.0, False)])
def test_the_listening_module_runs_below_78(quick_rc, runs):
    assert scoring.run_listening_module(quick_rc) is runs


@pytest.mark.parametrize(
    "ran, final_rc, outcome",
    [
        (True, 60.0, ListeningOutcome(lc_used=True, flag=None)),
        (True, 78.0, ListeningOutcome(lc_used=False, flag="LC_NOT_USED")),
        (False, 69.9, ListeningOutcome(lc_used=False, flag="LC_MISSED")),
        (False, 70.0, ListeningOutcome(lc_used=False, flag=None)),
        (False, 77.9, ListeningOutcome(lc_used=False, flag=None)),
        (True, None, ListeningOutcome(lc_used=True, flag=None)),
        (False, None, ListeningOutcome(lc_used=False, flag=None)),
    ],
)
def test_quick_and_final_rc_are_reconciled(ran, final_rc, outcome):
    assert scoring.listening_outcome(ran, final_rc) == outcome


# ---- 6.6 reader profile


@pytest.mark.parametrize(
    "d_ok, rc, lc, code",
    [
        (True, 80.0, None, "ON_TRACK"),
        (False, 80.0, None, "UNDERSTANDS_BUILDING_WORD_READING"),
        (True, 60.0, 75.0, "COMPREHENSION_STRATEGY_GAP"),
        (False, 60.0, 75.0, "DECODING_LIMITED"),
        (True, 60.0, 60.0, "FLUENT_NEEDS_LANGUAGE_SUPPORT"),
        (False, 60.0, 60.0, "NEEDS_SUPPORT_IN_BOTH"),
        (True, 60.0, None, "INSUFFICIENT_EVIDENCE"),
        (None, 80.0, None, "INSUFFICIENT_EVIDENCE"),
        (True, None, None, "INSUFFICIENT_EVIDENCE"),
    ],
)
def test_profile_decision_tree(d_ok, rc, lc, code):
    assert profile(d_ok, rc, lc).code == code


@pytest.mark.parametrize(
    "lc, code",
    [(75.0, "DECODING_LIMITED"), (60.0, "NEEDS_SUPPORT_IN_BOTH"), (None, "INSUFFICIENT_EVIDENCE")],
)
def test_a_reading_stopped_early_is_profiled_from_listening_alone(lc, code):
    assert profile(None, None, lc, stopped=True).code == code
    assert profile(True, 95.0, lc, stopped=True).code == code


@pytest.mark.parametrize("flag", ["LOW_AUDIO", "OFF_TASK"])
def test_a_blocking_flag_means_insufficient_evidence(flag):
    assert profile(True, 95.0, None, flags=[flag]) == Profile("INSUFFICIENT_EVIDENCE", True)


def test_every_combination_maps_to_one_profile_and_rc_above_the_cut_ignores_lc():
    scores = (None, 49.9, 69.9, 70.0, 90.0)
    for d_ok, rc, stopped, flags in product(
        (True, False, None), scores, (True, False), ((), ("LOW_AUDIO",))
    ):
        codes = {profile(d_ok, rc, lc, flags=flags, stopped=stopped).code for lc in scores}
        assert codes <= PROFILE_CODES
        if not stopped and not flags and d_ok is not None and rc is not None and rc >= 70:
            assert len(codes) == 1


@pytest.mark.parametrize(
    "rc, lc, provisional",
    [
        (75.0, None, True),
        (62.1, None, True),
        (78.0, None, False),
        (62.0, None, False),
        (50.0, 65.0, True),
        (50.0, 50.0, False),
    ],
)
def test_provisional_within_8_points_of_the_cut(rc, lc, provisional):
    assert profile(True, rc, lc).provisional is provisional


@pytest.mark.parametrize(
    "flags, provisional",
    [
        (["SHORT_READING"], True),
        (["HIGH_UNCERTAINTY", "DEMO_PROFILE"], True),
        (["DEMO_PROFILE", "LIVE_FALLBACK", "FALLBACK_PASSAGE"], False),
    ],
)
def test_any_flag_that_is_not_informational_makes_it_provisional(flags, provisional):
    assert profile(True, 95.0, None, flags=flags).provisional is provisional


# ---- 6.7 Alo Reading Level


@pytest.mark.parametrize(
    "accuracy, band",
    [
        (98.0, "INDEPENDENT"),
        (97.9, "INSTRUCTIONAL"),
        (95.0, "INSTRUCTIONAL"),
        (94.9, "SUPPORTED"),
        (90.0, "SUPPORTED"),
        (89.9, "FRUSTRATION"),
    ],
)
def test_accuracy_bands(accuracy, band):
    assert scoring.performance_band(accuracy, 100.0) == band


@pytest.mark.parametrize(
    "rc, band",
    [
        (90.0, "INDEPENDENT"),
        (89.9, "INSTRUCTIONAL"),
        (70.0, "INSTRUCTIONAL"),
        (69.9, "SUPPORTED"),
        (50.0, "SUPPORTED"),
        (49.9, "FRUSTRATION"),
    ],
)
def test_comprehension_bands(rc, band):
    assert scoring.performance_band(100.0, rc) == band


@pytest.mark.parametrize(
    "accuracy, rc, band",
    [(99.0, 60.0, "SUPPORTED"), (96.0, 95.0, "INSTRUCTIONAL"), (89.9, 95.0, "FRUSTRATION")],
)
def test_the_band_is_the_lower_of_the_two(accuracy, rc, band):
    assert scoring.performance_band(accuracy, rc) == band


def test_a_reading_stopped_early_is_frustration_and_moves_two_levels_down():
    band = scoring.performance_band(None, None, reading_stopped_early=True)
    assert band == "FRUSTRATION"
    assert scoring.next_passage_level(5, band) == 3


@pytest.mark.parametrize("accuracy, rc", [(None, 80.0), (97.0, None)])
def test_no_band_without_both_measures(accuracy, rc):
    assert scoring.performance_band(accuracy, rc) is None


@pytest.mark.parametrize(
    "band, level, next_arl",
    [
        ("INDEPENDENT", ReportedLevel(arl=5, at_least=True), 6),
        ("INSTRUCTIONAL", ReportedLevel(arl=5, at_least=False), 5),
        ("SUPPORTED", ReportedLevel(arl=4, at_least=False), 4),
        ("FRUSTRATION", ReportedLevel(arl=3, at_least=False), 3),
    ],
)
def test_reported_and_next_levels_follow_the_band(band, level, next_arl):
    assert scoring.reported_level(5, band) == level
    assert scoring.next_passage_level(5, band) == next_arl


@pytest.mark.parametrize(
    "passage_arl, band, reported, next_arl",
    [(1, "FRUSTRATION", 1, 1), (2, "FRUSTRATION", 1, 1), (12, "INDEPENDENT", 12, 12)],
)
def test_levels_stay_within_1_to_12(passage_arl, band, reported, next_arl):
    assert scoring.reported_level(passage_arl, band).arl == reported
    assert scoring.next_passage_level(passage_arl, band) == next_arl


def test_without_a_band_there_is_no_reported_level_and_the_next_session_retests():
    assert scoring.reported_level(5, None) is None
    assert scoring.next_passage_level(5, None) == 5


@pytest.mark.parametrize("arl", [0, 13])
def test_arl_must_be_1_to_12(arl):
    with pytest.raises(ValueError):
        scoring.reported_level(arl, "INSTRUCTIONAL")
    with pytest.raises(ValueError):
        scoring.next_passage_level(arl, None)
    with pytest.raises(ValueError):
        scoring.approx_primary_class(arl)


@pytest.mark.parametrize(
    "previous, current, confirmed", [(None, 4, False), (4, 4, True), (4, 5, True), (4, 6, False)]
)
def test_a_level_is_confirmed_when_two_sessions_agree_within_one(previous, current, confirmed):
    assert scoring.level_confirmed(previous, current) is confirmed


@pytest.mark.parametrize("arl, primary_class", [(1, 1), (2, 1), (3, 2), (4, 2), (11, 6), (12, 6)])
def test_two_levels_per_primary_class(arl, primary_class):
    assert scoring.approx_primary_class(arl) == primary_class


@pytest.mark.parametrize(
    "primary_class, on, arl",
    [
        (3, date(2026, 9, 1), 5),
        (3, date(2026, 12, 31), 5),
        (3, date(2027, 1, 5), 6),
        (3, date(2027, 8, 31), 6),
        (1, date(2026, 10, 1), 1),
        (6, date(2027, 2, 1), 12),
    ],
)
def test_a_first_session_starts_from_class_and_term(primary_class, on, arl):
    assert scoring.start_arl(primary_class, on) == arl


def test_a_returning_child_starts_at_their_next_passage_level():
    assert scoring.start_arl(3, date(2026, 10, 1), previous_next_arl=7) == 7


@pytest.mark.parametrize("primary_class, previous", [(0, None), (7, None), (3, 13)])
def test_start_level_inputs_are_checked(primary_class, previous):
    with pytest.raises(ValueError):
        scoring.start_arl(primary_class, date(2026, 10, 1), previous_next_arl=previous)
