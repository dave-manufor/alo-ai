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
