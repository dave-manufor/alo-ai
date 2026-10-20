import pytest
from services.core.generator import blueprint


def test_the_rows_cover_arl_1_to_12_once():
    covered = [arl for row in blueprint.ROWS for arl in range(row.arls[0], row.arls[1] + 1)]
    assert covered == list(range(1, 13))


def test_every_limit_gets_easier_to_harder_down_the_rows():
    rows = blueprint.ROWS
    for easier, harder in zip(rows, rows[1:], strict=False):
        assert easier.words[1] <= harder.words[1]
        assert easier.max_mean_sentence < harder.max_mean_sentence
        assert easier.max_long_share < harder.max_long_share
        assert easier.zipf_threshold >= harder.zipf_threshold
        assert easier.zipf_share > harder.zipf_share


@pytest.mark.parametrize(("arl", "row"), [(1, 0), (2, 0), (3, 1), (6, 2), (12, 5)])
def test_row_for(arl, row):
    assert blueprint.row_for(arl) is blueprint.ROWS[row]


@pytest.mark.parametrize("arl", [0, 13, -1])
def test_row_for_refuses_a_level_outside_1_to_12(arl):
    with pytest.raises(ValueError, match="1 to 12"):
        blueprint.row_for(arl)


def test_the_demo_profile_is_75_words_give_or_take_five_whatever_the_level():
    assert blueprint.word_range(3, "DEMO") == blueprint.word_range(9, "DEMO") == (70, 80)


def test_the_standard_profile_takes_the_rows_range():
    assert blueprint.word_range(3, "STANDARD") == (100, 120)
    assert blueprint.word_range(12, "STANDARD") == (190, 220)


def test_demo_asks_less_than_standard():
    standard, demo = blueprint.STANDARD, blueprint.DEMO
    assert (standard.literal_items, standard.inferential_items) == (2, 1)
    assert (demo.literal_items, demo.inferential_items) == (1, 1)
    assert standard.propositions == (6, 14) and standard.core_min == 3
    assert demo.propositions == (4, 8) and demo.core_min == 2


def test_an_unknown_length_profile_is_refused():
    with pytest.raises(ValueError, match="STANDARD or DEMO"):
        blueprint.rules_for("LONG")
