"""Word clip URIs agree with the bank passages and the Session Agent's key rule."""

import json

import pytest
from services.core.generator import clips, data
from services.session_agent.clips.keys import word_key as session_word_key

from .fakes import CONTRACTS

BANK_URI = clips.word_clip_uri("aloai-dev-clips", "vp_google_v1", "v1")


@pytest.mark.parametrize(
    "fixture", ["passage.bank_p3_market_day.json", "passage.bank_l3_rain.json"]
)
def test_every_bank_token_gets_the_same_clip_uri(fixture):
    passage = json.loads((CONTRACTS / fixture).read_text(encoding="utf-8"))
    for token in passage["tokens"]:
        assert BANK_URI(token["clean_text"], token["name_ipa"]) == token["word_clip_gcs_uri"]


@pytest.mark.parametrize("word", ["goat", "we'll", "jàpá", "ọ̀rẹ́"])
def test_the_key_is_the_session_agents(word):
    assert clips.word_key(word, None) == session_word_key(word)


def test_a_name_key_carries_its_ipa_as_the_session_agent_does():
    for name in data.names().entries:
        clean = name.text.lower()
        assert clips.word_key(clean, name.ipa) == session_word_key(name.text, name.ipa)
