"""The Critic's three calls and its two gate checks (PRD 4.5 G4)."""

import threading

import pytest
from services.core.generator import critic
from services.core.generator.models import ModelError

from .fakes import ScriptedModel, demo

STORY = demo("writer/1")


def scores(a1=2, a2=2, b1=0, b2=0):
    return {
        "scores": [
            {"answer_set": "A", "item_id": "q1", "points": a1},
            {"answer_set": "A", "item_id": "q2", "points": a2},
            {"answer_set": "B", "item_id": "q1", "points": b1},
            {"answer_set": "B", "item_id": "q2", "points": b2},
        ]
    }


def responses(**changes):
    return {
        "critic_a/1": demo("critic_a/1"),
        "critic_b/1": demo("critic_b/1"),
        "critic_c/1": demo("critic_c/1"),
        **changes,
    }


def review(model, attempt=1, timeout=lambda: 4.0):
    return critic.review(model, STORY, "sess_demo_001", attempt, timeout)


def test_a_good_story_passes_both_checks():
    model = ScriptedModel(responses())
    checks = review(model)
    assert [(c.name, c.passed) for c in checks] == [
        ("items_answerable", True),
        ("items_not_guessable", True),
    ]
    assert sorted(model.keys()[:2]) == ["critic_a/1", "critic_b/1"]
    assert model.keys()[2] == "critic_c/1"
    assert all(call.timeout_s == 4.0 and call.model == critic.MODEL for call in model.calls)


def test_critic_b_never_sees_the_story():
    model = ScriptedModel(responses())
    review(model)
    blind, reader = model.prompt("critic_b/1"), model.prompt("critic_a/1")
    for sentence in STORY["sentences"]:
        assert sentence not in blind
        assert sentence in reader
    for item in STORY["items"]:
        assert item["prompt_text"] in blind
        assert item["rubric"]["2"] not in blind
    assert "Title: The Lost Goat" in blind


def test_critic_c_scores_both_answer_sets_against_the_rubrics():
    model = ScriptedModel(responses())
    review(model)
    prompt = model.prompt("critic_c/1")
    assert "Answer A: It was eating the green beans." in prompt
    assert "Answer B: Grass." in prompt
    assert "2 points: The green beans, or beans." in prompt
    assert "(2) Na beans the goat dey chop." in prompt


def test_a_and_b_run_at_the_same_time():
    both = threading.Barrier(2, timeout=5)

    class Parallel(ScriptedModel):
        def call(self, call):
            if call.key in ("critic_a/1", "critic_b/1"):
                both.wait()  # breaks, and fails the test, if the calls run one after the other
            return super().call(call)

    review(Parallel(responses()))


def test_an_item_the_reader_cannot_fully_answer_fails():
    (answerable, _) = review(ScriptedModel(responses(**{"critic_c/1": scores(a2=1)})))
    assert not answerable.passed
    assert answerable.reason == "a reader of the story could not fully answer q2"


def test_literal_questions_guessed_without_the_story_fail():
    (_, guessable) = review(ScriptedModel(responses(**{"critic_c/1": scores(b1=2)})))
    assert not guessable.passed
    assert "2 points from the title and questions alone; at most 1" in guessable.reason


def test_one_guessed_point_and_a_guessed_inference_are_allowed():
    (_, guessable) = review(ScriptedModel(responses(**{"critic_c/1": scores(b1=1, b2=2)})))
    assert guessable.passed


def test_each_attempt_has_its_own_keys():
    model = ScriptedModel({f"{k[:-1]}2": v for k, v in responses().items()})
    review(model, attempt=2)
    assert sorted(model.keys()) == ["critic_a/2", "critic_b/2", "critic_c/2"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"critic_a/1": {"answers": [{"item_id": "q1", "answer": "Beans."}]}},
            "critic_a/1 answered",
        ),
        ({"critic_b/1": {"answers": "Grass"}}, "critic_b/1 broke its output schema"),
        ({"critic_c/1": {"scores": scores()["scores"][:3]}}, "critic_c/1 scored other answers"),
        (
            {"critic_c/1": {"scores": scores()["scores"] + scores()["scores"][:1]}},
            "critic_c/1 scored other answers",
        ),
        ({"critic_c/1": scores(a1=3)}, "critic_c/1 broke its output schema"),
    ],
)
def test_an_unusable_answer_is_refused(changes, message):
    with pytest.raises(ModelError, match=message):
        review(ScriptedModel(responses(**changes)))
