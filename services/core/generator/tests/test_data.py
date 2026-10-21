import json
from pathlib import Path

import pytest
from services.core.generator import data, gate
from services.core.generator.names import Blocklist, NameList
from services.core.generator.text import HOMOGRAPHS, clean_word

from . import sample

ROOT = Path(__file__).resolve().parents[4]
CONTRACTS = ROOT / "fixtures" / "contracts"


def test_the_taxonomy_is_the_topic_tag_schema():
    schema = json.loads((ROOT / "schemas" / "topic_tag.schema.json").read_text())
    assert data.taxonomy().tags == tuple(schema["enum"])
    assert all(topic.description for topic in data.taxonomy().topics)


@pytest.mark.parametrize(
    ("tags", "hint", "genre"),
    [
        (["space"], None, "EXPOSITORY"),
        (["animals", "weather"], None, "EXPOSITORY"),
        (["animals", "adventure"], None, "NARRATIVE"),  # one story tag makes it a story
        (["football"], None, "NARRATIVE"),
        ([], None, "NARRATIVE"),  # the child said nothing
        (["space"], "NARRATIVE", "NARRATIVE"),
        (["market"], "EXPOSITORY", "EXPOSITORY"),
    ],
)
def test_the_genre_is_narrative_unless_every_tag_is_factual(tags, hint, genre):
    assert data.taxonomy().genre(tags, hint) == genre


def test_an_unknown_tag_or_genre_is_refused():
    with pytest.raises(KeyError):
        data.taxonomy().genre(["cars"])
    with pytest.raises(ValueError):
        data.taxonomy().genre(["space"], "POETRY")


def test_every_name_has_its_ipa_and_appears_once():
    entries = data.names().entries
    assert len(entries) >= 30
    words = [clean_word(name.text) for name in entries]
    assert len(set(words)) == len(words)
    assert {name.kind for name in entries} == {"PERSON", "KIN", "PLACE"}
    for name in entries:
        assert name.text[0].isupper(), name
        assert name.ipa.strip() == name.ipa and " " not in name.ipa, name


def test_no_name_is_blocked_or_a_homograph():
    blocked = data.blocklist()
    for name in data.names().entries:
        assert not blocked.hits(name.text), name
        assert clean_word(name.text) not in HOMOGRAPHS, name


@pytest.mark.parametrize(
    "fixture",
    [
        "passage.bank_p3_market_day.json",
        "passage.bank_l3_rain.json",
    ],
)
def test_names_already_in_bank_passages_keep_their_ipa(fixture):
    """A name's IPA is part of its clip key, so the list must give the IPA the bank used."""
    passage = json.loads((CONTRACTS / fixture).read_text(encoding="utf-8"))
    for token in passage["tokens"]:
        if token["name_ipa"] is not None:
            assert data.names().get(token["clean_text"]).ipa == token["name_ipa"], token


@pytest.mark.parametrize(
    "word",
    ["gun", "ghost", "church", "mosque", "president", "kiss", "beer", "stupid", "milo", "messi"],
)
def test_the_blocklist_covers_each_story_rule(word):
    """PRD 4.5: no violence, frightening content, religion, politics, romance, alcohol,
    unkind words, brands or real people."""
    assert data.blocklist().hits(f"Ada saw the {word.capitalize()}.") == [word]


@pytest.mark.parametrize("word", ["shot", "attack", "party", "love", "smoky", "fight"])
def test_the_blocklist_leaves_ordinary_story_words(word):
    assert data.blocklist().hits(word) == []


def test_a_blocklist_entry_must_be_one_clean_word(tmp_path):
    path = tmp_path / "blocklist.txt"
    path.write_text("# comment\n\ngun\nBad Word\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Bad Word"):
        data.blocklist(path)


def test_the_loaders_return_the_types_the_gate_reads():
    assert isinstance(data.names(), NameList)
    assert isinstance(data.blocklist(), Blocklist)


def test_the_sample_story_passes_the_gate_with_the_real_lists(nlp):
    checks = gate.run(sample.STORY, gate.Request(3, "DEMO"), nlp, data.names(), data.blocklist())
    assert gate.passed(checks), gate.feedback(checks)
