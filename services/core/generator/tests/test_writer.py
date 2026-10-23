"""The Story Writer's prompt and the check on what it returns (PRD 4.5 G2)."""

import pytest
from services.core.generator import data, writer
from services.core.generator.models import FLASH, ModelError

from . import sample
from .fakes import ScriptedModel, demo


def brief(**changes) -> writer.Brief:
    fields = {
        "session_id": "sess_demo_001",
        "target_arl": 4,
        "length_profile": "DEMO",
        "genre": "NARRATIVE",
        "topics": (data.taxonomy().topic("animals"), data.taxonomy().topic("adventure")),
        "details": ("goat",),
        "names": data.names(),
    }
    return writer.Brief(**{**fields, **changes})


def test_the_prompt_carries_the_level_length_and_item_rules():
    prompt = writer.build_prompt(brief())
    assert "70 to 80 words in all" in prompt  # DEMO: 75 +/- 5
    assert "9 words or fewer on average" in prompt  # the ARL 3-4 row
    assert "4 to 8 propositions" in prompt and "at least 2" in prompt
    assert "exactly 2, with order 1 to 2" in prompt
    assert "1 LITERAL" in prompt and "1 INFERENTIAL" in prompt
    assert "Nigerian English or Nigerian Pidgin" in prompt


def test_the_standard_profile_asks_for_the_blueprint_row_and_three_questions():
    prompt = writer.build_prompt(brief(target_arl=5, length_profile="STANDARD"))
    assert "120 to 150 words in all" in prompt
    assert "11 words or fewer on average" in prompt
    assert "6 to 14 propositions" in prompt and "at least 3" in prompt
    assert "exactly 3, with order 1 to 3" in prompt and "2 LITERAL" in prompt


def test_the_prompt_names_the_topics_the_detail_and_every_listed_name():
    prompt = writer.build_prompt(brief())
    assert "animals at home, on the farm or in the wild and exploring" in prompt
    assert "Include goat in the story." in prompt
    for name in data.names().entries:
        assert f"{name.text} ({name.kind.lower()})" in prompt
    assert "Text type: a story." in prompt


def test_no_detail_and_no_topic():
    assert "in the story." not in writer.build_prompt(brief(details=()))
    assert "any everyday topic" in writer.build_prompt(brief(topics=(), details=()))


def test_an_expository_text_gets_the_main_idea_plan():
    prompt = writer.build_prompt(brief(genre="EXPOSITORY"))
    assert "a short factual text" in prompt and "MAIN_IDEA and DETAIL" in prompt


def test_the_retry_prompt_carries_the_failed_checks():
    assert "failed these checks" not in writer.build_prompt(brief())
    prompt = writer.build_prompt(brief(attempt=2, feedback="- safety: uses gun"))
    assert prompt.endswith("Write a new story that passes them:\n- safety: uses gun")


def test_write_makes_one_flash_call_and_returns_the_story():
    model = ScriptedModel({"writer/2": demo("writer/1")})
    story = writer.write(model, brief(attempt=2), timeout_s=7.5)
    assert story["title"] == "The Lost Goat"
    (call,) = model.calls
    assert (call.key, call.model, call.timeout_s) == ("writer/2", FLASH, 7.5)
    assert call.temperature == writer.TEMPERATURE
    assert call.response_schema is writer.OUTPUT_SCHEMA


def test_the_output_schema_takes_the_story_the_gate_reads():
    model = ScriptedModel({"writer/1": sample.STORY})
    assert writer.write(model, brief(), timeout_s=1) == sample.STORY


@pytest.mark.parametrize(
    "broken",
    [
        {"title": "No items", "sentences": ["Ada ran."], "propositions": []},
        {**sample.STORY, "sentences": "Ada ran."},
        {**sample.STORY, "items": [{**sample.STORY["items"][0], "type": "VOCABULARY"}]},
    ],
)
def test_output_that_breaks_the_schema_is_refused(broken):
    with pytest.raises(ModelError, match="writer/1 broke the output schema"):
        writer.write(ScriptedModel({"writer/1": broken}), brief(), timeout_s=1)


def test_the_things_the_child_named_are_listed_in_the_prompt():
    assert "Include goat and ball in the story." in writer.build_prompt(
        brief(details=("goat", "ball"))
    )
    assert "Include goat, ball and red car in the story." in writer.build_prompt(
        brief(details=("goat", "ball", "red car"))
    )


def test_the_interests_are_used_even_when_no_topic_fits():
    prompt = writer.build_prompt(brief(topics=(), details=("dinosaur", "drum")))
    assert "any everyday topic" in prompt
    assert "Include dinosaur and drum in the story." in prompt
