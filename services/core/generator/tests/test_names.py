import pytest
from services.core.generator.names import Blocklist, Name, NameList

ADA = Name("Ada", "ˈɑːdɑ", "PERSON")


def test_a_name_is_found_by_its_cleaned_word():
    names = NameList((ADA, Name("Jàpá", "dʒɑˈpɑ", "PLACE")))
    assert names.get("ADA,").ipa == "ˈɑːdɑ"
    assert "ada" in names and "Japa" not in names  # accents matter
    assert names.get("Jàpá").kind == "PLACE"
    assert names.get("Tunde") is None


def test_an_empty_list_has_no_names():
    assert "Ada" not in NameList()


@pytest.mark.parametrize(
    "args",
    [("Ada", "ˈɑːdɑ", "ANIMAL"), ("Ada", "", "PERSON"), ("--", "ˈɑːdɑ", "PERSON")],
)
def test_a_name_needs_a_known_kind_its_text_and_its_ipa(args):
    with pytest.raises(ValueError):
        Name(*args)


def test_the_blocklist_reports_each_blocked_word_once_in_order():
    blocklist = Blocklist(frozenset({"knife", "blood"}))
    assert blocklist.hits("A Knife! Then blood, and the knife again.") == ["knife", "blood"]
    assert blocklist.hits("A kind sister.") == []


def test_the_blocklist_matches_whole_words_only():
    assert Blocklist(frozenset({"gun"})).hits("The gunny sack and a bun.") == []
