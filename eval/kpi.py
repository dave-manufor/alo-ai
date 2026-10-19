"""The KPI table (PRD 1.3, day 5) for what W3 measures, from the saved results of the
evaluation runs in eval/results/. A row whose run has not happened says so; nothing is
filled in by hand.

    python -m eval.kpi
"""

import json
import sys
from collections.abc import Sequence

from .coach_set import THRESHOLDS
from .golden import ACCURACY_TOLERANCE, WCPM_TOLERANCE
from .models import ROOT

RESULTS = ROOT / "results"
NOT_RUN = "not run yet"


def _load(name: str):
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def redteam_row(results: list | None) -> str:
    if results is None:
        return NOT_RUN
    passed = sum(not result["failed"] for result in results)
    return f"{passed} of {len(results)} passed"


def coach_row(results: list | None) -> str:
    if results is None:
        return NOT_RUN
    counts = {metric: sum(r[metric] for r in results) for metric in THRESHOLDS}
    verdict = all(counts[m] >= t for m, t in THRESHOLDS.items())
    shown = ", ".join(
        f"{metric.replace('_', ' ')} {count}/{len(results)}" for metric, count in counts.items()
    )
    return f"{shown}: {'met' if verdict else 'not met'}"


def golden_row(results: list | None) -> str:
    if results is None:
        return NOT_RUN
    within = sum(result["within"] for result in results)
    return f"{within} of {len(results)} recordings within"


def grading_rows(reading: dict | None) -> tuple[str, str]:
    if reading is None:
        return NOT_RUN, NOT_RUN
    kappa = "undefined" if reading["kappa"] is None else f"{reading['kappa']:.2f}"
    quick = reading["quick_vs_final"]
    return (
        f"{reading['item_agreement']:.0%} of {reading['items']} items"
        if quick is None
        else f"{quick:.0%}",
        f"weighted κ {kappa} on {reading['items']} items, n = {reading['sessions']} sessions",
    )


def table() -> str:
    quick, kappa = grading_rows(_load("grading"))
    rows = [
        ("Agent red-team set (3.1)", "100% of 20 cases", redteam_row(_load("redteam"))),
        (
            "Reading Coach evaluation set (13.4)",
            "every metric at its threshold",
            coach_row(_load("coach")),
        ),
        (
            "Golden-recording test (Reading Scorer)",
            f"WCPM within ±{WCPM_TOLERANCE}, accuracy within ±{ACCURACY_TOLERANCE}",
            golden_row(_load("golden")),
        ),
        ("Quick vs final item scores agree", "reported from the mini-study", quick),
        ("Answer scoring vs a human", "early trial readings; target κ ≥ 0.60", kappa),
        (
            "Numbers in a Coach summary traceable to a tool result",
            "100% (automatic check)",
            "enforced in code by aloai_guardrails before anything is saved",
        ),
    ]
    lines = ["| Metric | Sprint target | Result |", "|---|---|---|"]
    lines += [f"| {metric} | {target} | {result} |" for metric, target, result in rows]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    print(table())
    return 0


if __name__ == "__main__":
    sys.exit(main())
