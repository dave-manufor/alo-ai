import pytest
from services.core.generator.syllables import count_syllables


@pytest.mark.parametrize(
    ("word", "syllables"),
    [
        ("a", 1),
        ("the", 1),
        ("school", 1),
        ("game", 1),
        ("games", 1),
        ("jumped", 1),
        ("kicked", 1),
        ("wanted", 2),
        ("boxes", 2),
        ("market", 2),
        ("table", 2),
        ("people", 2),
        ("happy", 2),
        ("Ada", 2),
        ("tomato", 3),
        ("beautiful", 3),
        ("elephant", 3),
        ("I", 1),
    ],
)
def test_count_syllables(word, syllables):
    assert count_syllables(word) == syllables


@pytest.mark.parametrize("text", ["", "123", "--"])
def test_no_letters_no_syllables(text):
    assert count_syllables(text) == 0
