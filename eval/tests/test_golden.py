"""The golden-recording check: hand counts through aloai_scoring against the scorer's telemetry."""

import json

import pytest
from aloai_store import MemoryStore
from eval import golden
from eval.golden import GoldenResult, check, hand_fluency, markdown
from services.core.grader import paths

DEMO_HAND = {"words_attempted": 23, "errors": 3, "told": 1, "reading_seconds": 19.65}


def test_the_hand_count_follows_the_scoring_rules():
    hand = hand_fluency(DEMO_HAND)
    assert (hand.wcpm, hand.accuracy_pct) == (60 * 20 / 20.15, 100 * 20 / 23)  # the 2.5 s wait is 0.5 s under the norms' 3 s


def test_a_told_first_word_has_no_wait_to_take_off():
    assert hand_fluency(DEMO_HAND | {"told_waits": 0}).wcpm == 60 * 20 / 19.65


def scored(store, session_id, wcpm, accuracy):
    store.set(paths.telemetry(session_id), {"wcpm": wcpm, "accuracy_pct": accuracy})


@pytest.mark.parametrize(
    "wcpm, accuracy, within",
    [(59.6, 87.0, True), (64.5, 89.9, True), (64.7, 87.0, False), (59.6, 83.9, False)],
)
def test_the_scorer_must_land_within_five_wcpm_and_three_points(wcpm, accuracy, within):
    store = MemoryStore()
    scored(store, "s1", wcpm, accuracy)
    [result] = check([{"recording_id": "g1", "session_id": "s1", "hand": DEMO_HAND}], store)
    assert result.within is within


@pytest.mark.parametrize("scorer, within", [(None, False), (68.0, True)])
def test_a_missing_number_matches_only_a_missing_number(scorer, within):
    result = GoldenResult("g1", 68.0, scorer, 87.0, 87.0)
    assert result.within is within
    assert GoldenResult("g1", None, None, None, None).within


def test_the_table_reports_each_recording():
    text = markdown([GoldenResult("g1", 68.0, 70.5, 87.0, 86.0)])
    assert text.startswith("Golden recordings: 1 of 1 within ±5 WCPM and ±3 accuracy points")
    assert "| g1 | 68.0 | 70.5 | 87.0 | 86.0 | yes |" in text


def test_the_index_is_empty_until_there_are_recordings(capsys):
    assert json.loads(golden.INDEX.read_text())["recordings"] == []
    assert golden.main([]) == 2
    assert "No golden recordings yet" in capsys.readouterr().out


def test_the_check_runs_the_index_against_the_telemetry(tmp_path, monkeypatch, capsys):
    store = MemoryStore()
    scored(store, "s1", 60.0, 88.0)
    index = tmp_path / "index.json"
    recording = {"recording_id": "g1", "session_id": "s1", "hand": DEMO_HAND}
    index.write_text(json.dumps({"recordings": [recording]}))
    monkeypatch.setattr(golden, "INDEX", index)
    monkeypatch.setattr(golden, "RESULTS", tmp_path / "results" / "golden.json")
    monkeypatch.setattr(golden, "open_store", lambda settings: store)
    assert golden.main([]) == 0
    assert json.loads((tmp_path / "results" / "golden.json").read_text())[0]["within"] is True
    assert "1 of 1 within" in capsys.readouterr().out
