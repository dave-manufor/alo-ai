import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from services.core.generator import artifact
from services.core.generator.names import NameList

from .sample import NAMES, SENTENCES, STORY

ROOT = Path(__file__).resolve().parents[4]
SCHEMA = json.loads((ROOT / "schemas" / "passage.schema.json").read_text())
BANK = json.loads((ROOT / "fixtures" / "contracts" / "passage.bank_p3_market_day.json").read_text())


def clip_uri(word, ipa):
    return f"gs://clips/vp/v1/words/{word}{'~' + ipa if ipa else ''}.mp3"


@pytest.fixture(scope="module")
def tokens(nlp):
    return artifact.build_tokens(SENTENCES, nlp, NAMES, clip_uri)


def test_one_token_per_whitespace_word_with_its_punctuation(tokens):
    assert [t["text"] for t in tokens] == " ".join(SENTENCES).split()
    assert [t["token_index"] for t in tokens] == list(range(len(tokens)))
    assert tokens[8]["text"] == "Mama." and tokens[8]["clean_text"] == "mama"


def test_sentence_indices_and_terminals(tokens):
    assert [t["sentence_index"] for t in tokens] == [
        i for i, s in enumerate(SENTENCES) for _ in s.split()
    ]
    ends = [t for t in tokens if t["syntactic_boundary_after"] == "TERMINAL"]
    assert [t["token_index"] for t in ends] == [
        sum(len(s.split()) for s in SENTENCES[: i + 1]) - 1 for i in range(len(SENTENCES))
    ]


def test_names_carry_their_ipa_and_clip_and_other_words_do_not(tokens):
    ada = tokens[0]
    assert (ada["clean_text"], ada["name_ipa"]) == ("ada", "ˈɑːdɑ")
    assert ada["word_clip_gcs_uri"] == "gs://clips/vp/v1/words/ada~ˈɑːdɑ.mp3"
    market = tokens[6]
    assert market["name_ipa"] is None
    assert market["word_clip_gcs_uri"] == "gs://clips/vp/v1/words/market.mp3"


def test_content_words(tokens):
    flags = {t["clean_text"]: t["is_content_word"] for t in tokens}
    assert flags["market"] and flags["bought"] and flags["tall"] and flags["ada"]
    assert not flags["the"] and not flags["and"] and not flags["was"] and not flags["he"]


def test_tokens_match_the_passage_schema(tokens):
    Draft202012Validator(SCHEMA["properties"]["tokens"]).validate(tokens)


def test_the_same_words_as_the_bank_passage_get_the_same_tokens(nlp):
    sentences = [s for s in BANK["text_content"].replace(". ", ".\n").split("\n")]
    built = artifact.build_tokens(sentences, nlp, NameList(), clip_uri)
    for mine, theirs in zip(built, BANK["tokens"], strict=True):
        for key in ("token_index", "sentence_index", "text", "clean_text"):
            assert mine[key] == theirs[key]
    terminals = [t["token_index"] for t in built if t["syntactic_boundary_after"] == "TERMINAL"]
    assert terminals == [
        t["token_index"] for t in BANK["tokens"] if t["syntactic_boundary_after"] == "TERMINAL"
    ]


def test_text_content_joins_sentences_with_single_spaces():
    assert artifact.text_content(["Ada  ran.", " Tunde sat. "]) == "Ada ran. Tunde sat."


def test_items_lose_the_exemplar_variety_and_gain_max_points():
    before = copy.deepcopy(STORY["items"])
    items = artifact.artifact_items(STORY["items"])
    assert STORY["items"] == before  # not changed in place
    assert all(item["max_points"] == 2 for item in items)
    assert all(set(e) == {"answer", "points"} for i in items for e in i["exemplars"])
    assert items[0]["exemplars"][1] == {"answer": "Na ball he see.", "points": 2}


def test_a_whole_generated_passage_validates_against_the_schema(tokens):
    passage = {
        "schema_version": 4,
        "passage_id": "gen_sess_demo_001",
        "title": STORY["title"],
        "mode": "READ",
        "source": "GENERATED",
        "topic_tags": ["market"],
        "generation": {
            "model": "gemini-2.5-flash",
            "prompt_version": "gen-v1",
            "target_arl": 3,
            "estimated_arl": 3.03,
            "attempts": 1,
            "gate_results": {"blueprint": True, "difficulty": True},
            "created_at": "2026-10-20T09:00:00Z",
        },
        "genre": "NARRATIVE",
        "arl_level": 3,
        "word_count": len(tokens),
        "text_content": artifact.text_content(SENTENCES),
        "voice_profile_id": "vp_google_v1",
        "length_profile": "DEMO",
        "tokens": tokens,
        "propositions": STORY["propositions"],
        "items": artifact.artifact_items(STORY["items"]),
        "paired_listening_passage_id": "bank_l3_rain",
    }
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(passage)
    assert " ".join(t["text"] for t in tokens) == passage["text_content"]
