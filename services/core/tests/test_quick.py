"""Quick scoring (PRD 7.4): one Flash pass per turn, stored, then the listening decision."""

import pytest
from services.core import contracts
from services.core.grader import paths
from services.core.grader.models import GradingError
from services.core.grader.quick import PassageNotFound, QuickGrader, UnknownItem
from services.core.tests.support import (
    SESSION_ID,
    RecordedModel,
    ScriptedModel,
    grader_output,
    quick_request,
    seeded_store,
)

RESPONSE = contracts.validator("grade_quick_response.schema.json")
PENDING = {"schema_version": 1, "complete": False, "run_listening_module": None}
RETELL = "ada and her mama went to the market"


def quick_grader(model=None):
    store = seeded_store()
    return QuickGrader(store, model or RecordedModel()), store


def test_a_retell_is_graded_once_and_stored():
    quick, store = quick_grader()
    request = quick_request("RETELL", 0, RETELL)
    assert quick.grade(request) == PENDING
    assert quick.grade(request) == PENDING
    assert quick.model.keys == ["quick/RETELL_0"]
    assert store.get(paths.quick(SESSION_ID, "RETELL", 0)) == {"weighted_credit": 5.0}


def test_an_unanswered_item_scores_zero_without_a_model_call():
    quick, store = quick_grader()
    quick.grade(quick_request("QUESTION", 1, "  "))
    assert quick.model.keys == []
    assert store.get(paths.quick(SESSION_ID, "QUESTION", 1)) == {
        "item_id": "bank_p3_market_day_q2",
        "points": 0,
    }


def test_an_empty_retell_credits_nothing():
    quick, store = quick_grader()
    quick.grade(quick_request("RETELL", 0, ""))
    assert quick.model.keys == []
    assert store.get(paths.quick(SESSION_ID, "RETELL", 0)) == {"weighted_credit": 0}


@pytest.mark.parametrize(
    "order",
    [
        [("RETELL", 0, RETELL), ("QUESTION", 0, "it was red"), ("QUESTION", 1, "")],
        [("QUESTION", 1, ""), ("QUESTION", 0, "it was red"), ("RETELL", 0, RETELL)],
    ],
)
def test_the_last_turn_in_completes_the_decision(order):
    quick, store = quick_grader()
    responses = [quick.grade(quick_request(*turn)) for turn in order]
    assert responses[:2] == [PENDING, PENDING]
    assert responses[2] == {"schema_version": 1, "complete": True, "run_listening_module": True}
    assert store.get(paths.quick_result(SESSION_ID)) == {
        "quick_rc": 70.0,
        "item_points": [2, 0],
        "run_listening_module": True,
    }
    for response in responses:
        RESPONSE.validate(response)


def test_a_quick_rc_of_78_or_more_skips_the_listening_module():
    model = ScriptedModel(
        {
            "quick/RETELL_0": grader_output({"p1": 1, "p2": 1, "p3": 1, "p4": 1}, {}),
            "quick/QUESTION_0": grader_output({}, {"bank_p3_market_day_q1": 2}),
            "quick/QUESTION_1": grader_output({}, {"bank_p3_market_day_q2": 2}),
        }
    )
    quick, store = quick_grader(model)
    quick.grade(quick_request("RETELL", 0, RETELL))
    quick.grade(quick_request("QUESTION", 0, "red"))
    response = quick.grade(quick_request("QUESTION", 1, "it cost too much"))
    assert response["run_listening_module"] is False
    assert store.get(paths.quick_result(SESSION_ID))["quick_rc"] == 100.0


def test_the_model_is_told_only_the_turn_it_grades():
    model = ScriptedModel({"quick/QUESTION_0": grader_output({}, {"bank_p3_market_day_q1": 1})})
    quick, _ = quick_grader(model)
    quick.grade(quick_request("QUESTION", 0, "a hat"))
    [task] = model.tasks
    assert (task.retell, dict(task.answers)) == (None, {"bank_p3_market_day_q1": "a hat"})
    assert task.model == "gemini-2.5-flash"


def test_an_unknown_passage_is_refused():
    quick, _ = quick_grader()
    with pytest.raises(PassageNotFound):
        quick.grade(quick_request("RETELL", 0, RETELL) | {"passage_id": "nope"})


def test_an_index_past_the_last_item_is_refused():
    quick, _ = quick_grader()
    with pytest.raises(UnknownItem):
        quick.grade(quick_request("QUESTION", 2, "something"))


def test_an_answer_that_is_not_a_grader_output_is_refused():
    model = ScriptedModel({"quick/QUESTION_0": {"points": 2}})
    quick, _ = quick_grader(model)
    with pytest.raises(GradingError):
        quick.grade(quick_request("QUESTION", 0, "red"))


def test_an_answer_that_grades_another_item_is_refused():
    model = ScriptedModel({"quick/QUESTION_0": grader_output({}, {"bank_p3_market_day_q2": 2})})
    quick, store = quick_grader(model)
    with pytest.raises(GradingError):
        quick.grade(quick_request("QUESTION", 0, "red"))
    assert store.get(paths.quick(SESSION_ID, "QUESTION", 0)) is None
