import pytest
from services.core.generator import textlevel
from services.core.generator.blueprint import ROWS
from services.core.generator.names import NameList

from .sample import NAMES, SENTENCES

EASY = ["Ada had a red hat.", "Ada sat on a mat.", "Tunde ran to Ada.", "They had fun."]
HARD = [
    "The villagers assembled beneath the enormous mango tree to discuss the unusual drought.",
    "Several elderly farmers remembered a similar season that devastated their harvest earlier.",
    "Consequently, the community decided to construct a reservoir before the rainy season.",
]


def estimate(sentences, names=NAMES):
    return textlevel.estimate_arl(textlevel.features(sentences, names))


def test_a_harder_text_gets_a_higher_level():
    assert estimate(EASY) < estimate(SENTENCES) < estimate(HARD)


def test_the_sample_story_is_about_level_3():
    assert estimate(SENTENCES) == pytest.approx(3.0, abs=0.5)


def test_features_count_names_as_words_but_not_in_the_word_shares():
    found = textlevel.features(["Ada ran to Tunde."], NAMES)
    assert found.words == 4
    assert found.mean_sentence_length == 4
    # "ran" and "to" are the only words judged for frequency and syllables.
    assert found.common_shares == (1.0,) * len(ROWS)
    assert found.long_share == 0


def test_a_text_of_only_names_is_judged_on_all_its_words():
    found = textlevel.features(["Ada Tunde."], NAMES)
    assert found.words == 2 and found.long_share == 0


@pytest.mark.parametrize("sentences", [[], ["   "], ["— !"]])
def test_no_text_has_no_level(sentences):
    with pytest.raises(ValueError):
        textlevel.features(sentences, NameList())


def test_the_estimate_stays_between_1_and_12():
    hardest = textlevel.Features(100, 40.0, (0.0,) * 6, 0.5)
    easiest = textlevel.Features(100, 1.0, (1.0,) * 6, 0.0)
    assert textlevel.estimate_arl(hardest) == 12.0
    assert textlevel.estimate_arl(easiest) == 1.0


def test_interpolation_continues_the_end_segments():
    assert textlevel._interpolate(5, [0, 10], [0, 100]) == 50
    assert textlevel._interpolate(20, [0, 10], [0, 100]) == 200
    assert textlevel._interpolate(-10, [0, 10], [0, 100]) == -100
    assert textlevel._interpolate(7, [0, 5, 10], [0, 10, 40]) == 22


def test_a_text_on_a_rows_sentence_length_limit_is_the_rows_top_level():
    for row in ROWS:
        found = textlevel.Features(100, row.max_mean_sentence, (1.0,) * 6, row.max_long_share)
        assert textlevel.estimate_arl(found) == pytest.approx(row.arls[1], abs=0.01)


def test_common_word_shares_exactly_on_a_rows_requirement_put_the_text_at_its_top():
    on_row_3 = [0.0, 0.0, ROWS[2].zipf_share, 1.0, 1.0, 1.0]
    assert textlevel._common_words_arl(on_row_3) == pytest.approx(6.0)
    on_row_1 = [ROWS[0].zipf_share, 1.0, 1.0, 1.0, 1.0, 1.0]
    assert textlevel._common_words_arl(on_row_1) == pytest.approx(2.0)


def test_common_word_shares_between_two_rows_are_between_their_levels():
    shares = [0.90, 0.92 + 0.03, 1.0, 1.0, 1.0, 1.0]  # row 1 missed by .05, row 2 met by .03
    assert 2.0 < textlevel._common_words_arl(shares) < 4.0


def test_shares_easier_than_row_1_go_below_level_2_and_harder_than_row_6_above_12():
    assert textlevel._common_words_arl([1.0] * 6) < 2.0
    assert textlevel._common_words_arl([0.0] * 6) > 12.0
