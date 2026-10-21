"""The grading evaluation: weighted kappa, agreement and the reading against hand scores."""

import json

import pytest
from aloai_store import MemoryStore
from eval import grading_set
from eval.grading_set import GradingReading, agreement, compare, markdown, weighted_kappa
from services.core.grader import paths


@pytest.mark.parametrize(
    "a, b, kappa",
    [
        ([0, 1, 2, 2], [0, 1, 2, 2], 1.0),
        ([0, 0, 2, 2], [2, 2, 0, 0], -1.0),
        ([2, 1, 0, 2, 1, 0], [2, 1, 1, 2, 0, 0], 0.75),
        ([2, 2, 2], [2, 2, 2], None),
    ],
)
def test_weighted_kappa_uses_quadratic_weights(a, b, kappa):
    assert weighted_kappa(a, b) == kappa


@pytest.mark.parametrize("a, b", [([], []), ([1], [1, 2])])
def test_kappa_needs_two_equally_long_lists(a, b):
    with pytest.raises(ValueError):
        weighted_kappa(a, b)


def test_agreement_is_the_share_of_equal_points():
    assert agreement([2, 1, 0, 2], [2, 1, 1, 0]) == 0.5


def graded(store, session_id, read, listen=None, quick=None):
    store.set(paths.grading(session_id), {"read": read, "listen": listen})
    if quick is not None:
        store.set(paths.quick_result(session_id), {"item_points": quick})


def test_the_reading_compares_both_passages_and_the_quick_scores():
    store = MemoryStore()
    graded(
        store,
        "s1",
        {"item_points": [2, 1], "weighted_credit": 5.0},
        {"item_points": [2], "weighted_credit": 3.0},
        quick=[2, 0],
    )
    graded(store, "s2", {"item_points": [0, 1], "weighted_credit": 2.0}, quick=[0, 1])
    hand = {
        "sessions": [
            {
                "session_id": "s1",
                "read": {"item_points": [2, 1], "weighted_credit": 4.0},
                "listen": {"item_points": [1], "weighted_credit": 3.0},
            },
            {"session_id": "s2", "read": {"item_points": [0, 2], "weighted_credit": 2.5}},
        ]
    }
    assert compare(hand, store) == GradingReading(
        sessions=2,
        items=5,
        kappa=0.64,
        item_agreement=0.6,
        quick_vs_final=0.75,
        retell_mean_difference=0.5,
    )


def test_hand_scores_for_other_items_are_refused():
    store = MemoryStore()
    graded(store, "s1", {"item_points": [2, 1], "weighted_credit": 5.0})
    hand = {"sessions": [{"session_id": "s1", "read": {"item_points": [2], "weighted_credit": 5}}]}
    with pytest.raises(ValueError, match="different items"):
        compare(hand, store)


def test_nothing_to_compare_is_refused():
    store = MemoryStore()
    graded(store, "s1", {"item_points": [2], "weighted_credit": 5.0})
    with pytest.raises(ValueError, match="no session"):
        compare({"sessions": [{"session_id": "s1", "read": None}]}, store)


def test_the_reading_is_reported_as_an_early_trial_reading():
    text = markdown(GradingReading(4, 12, None, 0.75, None, 0.25))
    assert text.startswith("Grading, early trial readings (n = 4 sessions, 12 items)")
    assert "| Weighted kappa, final vs hand | undefined | at least 0.60 |" in text
    assert "| Quick vs final item agreement | none | reported |" in text
    assert "75%" in markdown(GradingReading(4, 12, 0.7, 0.75, 0.75, 0.25))


def test_hand_scores_inside_the_repository_are_refused(capsys):
    inside = grading_set.ROOT / "hand_scores.json"
    assert grading_set.main([str(inside)]) == 2
    assert "outside the repository" in capsys.readouterr().out


def test_the_reading_is_saved_without_session_ids(tmp_path, monkeypatch, capsys):
    store = MemoryStore()
    graded(store, "s1", {"item_points": [2, 1], "weighted_credit": 5.0}, quick=[2, 1])
    hand = tmp_path / "hand.json"
    hand.write_text(
        json.dumps(
            {
                "sessions": [
                    {"session_id": "s1", "read": {"item_points": [2, 0], "weighted_credit": 5.0}}
                ]
            }
        )
    )
    monkeypatch.setattr(grading_set, "RESULTS", tmp_path / "results" / "grading.json")
    monkeypatch.setattr(grading_set, "FirestoreStore", lambda client: store)
    monkeypatch.setattr(grading_set.firestore, "Client", lambda project: None)
    assert grading_set.main([str(hand)]) == 0
    saved = (tmp_path / "results" / "grading.json").read_text()
    assert "s1" not in saved
    assert json.loads(saved)["items"] == 2
    assert "early trial readings" in capsys.readouterr().out
