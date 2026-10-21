"""The KPI table: each W3 row from its saved results, or "not run yet"."""

import json

from eval import kpi


def save(directory, name, results):
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(results))


def test_without_results_every_measured_row_says_not_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kpi, "RESULTS", tmp_path / "results")
    assert kpi.main([]) == 0
    table = capsys.readouterr().out
    assert table.count("not run yet") == 5
    assert "enforced in code by aloai_guardrails" in table


def test_each_row_comes_from_its_results(tmp_path, monkeypatch):
    results = tmp_path / "results"
    monkeypatch.setattr(kpi, "RESULTS", results)
    save(results, "redteam", [{"failed": []}] * 19 + [{"failed": ["absent_text"]}])
    coach = {"tool_sequence": True, "library_only": True, "validator_first_try": True}
    save(results, "coach", [coach] * 9 + [coach | {"validator_first_try": False}])
    save(results, "golden", [{"within": True}, {"within": False}])
    save(
        results,
        "grading",
        {"sessions": 4, "items": 12, "kappa": 0.71, "item_agreement": 0.75, "quick_vs_final": 0.83},
    )
    table = kpi.table()
    assert "| 19 of 20 passed |" in table
    assert "tool sequence 10/10, library only 10/10, validator first try 9/10: met" in table
    assert "| 1 of 2 recordings within |" in table
    assert "| 83% |" in table
    assert "weighted κ 0.71 on 12 items, n = 4 sessions" in table


def test_the_coach_row_says_when_a_threshold_is_missed():
    coach = {"tool_sequence": True, "library_only": False, "validator_first_try": True}
    assert kpi.coach_row([coach] * 10).endswith(
        "library only 0/10, validator first try 10/10: not met"
    )


def test_without_quick_scores_the_item_agreement_is_shown():
    reading = {
        "sessions": 3,
        "items": 9,
        "kappa": None,
        "item_agreement": 0.67,
        "quick_vs_final": None,
    }
    assert kpi.grading_rows(reading) == (
        "67% of 9 items",
        "weighted κ undefined on 9 items, n = 3 sessions",
    )
