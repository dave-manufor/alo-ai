import pytest
from services.core.generator.detail import safe_detail

from .sample import BLOCKLIST, NAMES


@pytest.mark.parametrize(
    ("detail", "kept"),
    [
        ("goat", "goat"),
        ("  Goat ", "goat"),
        ("red goat", "red goat"),
        ("rocket", "rocket"),
    ],
)
def test_a_common_noun_is_kept(nlp, detail, kept):
    assert safe_detail(detail, nlp, NAMES, BLOCKLIST) == kept


@pytest.mark.parametrize(
    "detail",
    [
        None,
        "",
        "ada",  # on the name list
        "knife",  # blocked
        "a very small goat",  # more than two words
        "goat2",  # not letters
        "my-goat",
        "g",  # too short
        "beautiful",  # an adjective, not a noun
        "xylophonist",  # too rare for the level
    ],
)
def test_anything_else_is_dropped(nlp, detail):
    assert safe_detail(detail, nlp, NAMES, BLOCKLIST) is None


def test_safe_details_keeps_each_safe_one_once_in_order_and_at_most_six(nlp):
    from services.core.generator.detail import MAX_DETAILS, safe_details

    asked = ["goat", "gun", "goat", "ball", "tree", "river", "house", "road", "hen"]
    kept = safe_details(asked, nlp, NAMES, BLOCKLIST)
    assert kept[:2] == ("goat", "ball")  # the unsafe one and the repeat are gone
    assert "gun" not in kept and len(kept) <= MAX_DETAILS
    assert safe_details([], nlp, NAMES, BLOCKLIST) == ()
