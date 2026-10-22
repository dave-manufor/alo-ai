import json
from pathlib import Path

import pytest
from services.core.generator import bank_builder, data, gate

CONTRACTS = Path(__file__).resolve().parents[4] / "fixtures" / "contracts"
# The bank passages the builder made, one for each class's level and the listening stories.
BUILT = [
    "bank_p1_ada_and_the_dog",
    "bank_p2_lost_ball",
    "bank_p4_night_bus",
    "bank_p5_music_contest",
    "bank_p6_river_crossing",
    "bank_l3_market",
    "bank_l9_rocket",
]
READ = [name for name in BUILT if name.startswith("bank_p")]
LISTEN = [name for name in BUILT if name.startswith("bank_l")]


def fixture(passage_id: str) -> dict:
    return json.loads((CONTRACTS / f"passage.{passage_id}.json").read_text())


def spec_from(passage: dict) -> dict:
    """The story as a person writes it, recovered from a built passage. Exemplars get a
    variety, as the Writer's do and the gate asks."""
    sentences: dict[int, list[str]] = {}
    for token in passage["tokens"]:
        sentences.setdefault(token["sentence_index"], []).append(token["text"])
    items = []
    for item in passage["items"]:
        kept = {k: v for k, v in item.items() if k not in ("item_id", "order", "max_points")}
        kept.pop("prompt_audio_gcs_uri", None)
        kept["exemplars"] = [
            {**e, "variety": "PIDGIN" if i == 0 else "STANDARD"}
            for i, e in enumerate(item["exemplars"])
        ]
        items.append(kept)
    spec = {
        key: passage[key]
        for key in ("passage_id", "title", "mode", "arl_level", "genre", "topic_tags")
        + ("length_profile", "propositions")
    }
    spec |= {"sentences": [" ".join(w) for _, w in sorted(sentences.items())], "items": items}
    if "paired_listening_passage_id" in passage:
        spec["paired_listening_passage_id"] = passage["paired_listening_passage_id"]
    return spec


@pytest.fixture(scope="module")
def names():
    return data.names()


@pytest.fixture(scope="module")
def blocklist():
    return data.blocklist()


@pytest.mark.parametrize("passage_id", BUILT)
def test_a_built_fixture_is_what_the_builder_makes_from_its_story(passage_id, nlp, names):
    passage = fixture(passage_id)
    assert bank_builder.build(spec_from(passage), nlp, names) == passage


@pytest.mark.parametrize("passage_id", BUILT)
def test_a_built_fixture_still_passes_the_code_gate(passage_id, nlp, names, blocklist):
    checks = bank_builder.check(spec_from(fixture(passage_id)), nlp, names, blocklist)
    assert [c for c in checks if not c.passed] == []


@pytest.mark.parametrize("passage_id", READ)
def test_a_read_fixture_names_a_listening_story_in_the_bank(passage_id):
    listening = fixture(fixture(passage_id)["paired_listening_passage_id"])
    assert listening["mode"] == "LISTEN" and listening["length_profile"] == "STANDARD"


@pytest.mark.parametrize("passage_id", LISTEN)
def test_a_listen_fixture_has_story_and_question_audio(passage_id):
    passage = fixture(passage_id)
    assert passage["audio_gcs_uri"].endswith(f"/listening/{passage_id}.mp3")
    assert all(i["prompt_audio_gcs_uri"].endswith(f"/{i['item_id']}.mp3") for i in passage["items"])
    assert "paired_listening_passage_id" not in passage


def test_items_get_an_id_and_an_order_from_their_place():
    spec = {"passage_id": "bank_x", "items": [{"type": "LITERAL"}, {"type": "INFERENTIAL"}]}
    items = bank_builder.with_ids(spec)["items"]
    assert [(i["item_id"], i["order"]) for i in items] == [("bank_x_q1", 1), ("bank_x_q2", 2)]
    assert "item_id" not in spec["items"][0]


def test_a_listening_story_that_is_too_short_or_too_long_fails(nlp, names, blocklist):
    spec = spec_from(fixture("bank_l9_rocket"))
    for sentences in (spec["sentences"][:3], spec["sentences"] * 2):
        checks = bank_builder.check({**spec, "sentences": sentences}, nlp, names, blocklist)
        failed = {c.name for c in checks if not c.passed}
        assert "listening_length" in failed


def test_a_read_story_with_a_name_off_the_list_fails_the_gate(nlp, names, blocklist):
    spec = spec_from(fixture("bank_p1_ada_and_the_dog"))
    spec["sentences"] = [s.replace("Ada", "Zorblax") for s in spec["sentences"]]
    checks = bank_builder.check(spec, nlp, names, blocklist)
    assert "names" in {c.name for c in checks if not c.passed}
    assert isinstance(checks[0], gate.Check)
