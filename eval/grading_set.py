"""The grading evaluation (PRD 13.1, 13.4): the Grader's final scores for the mini-study
sessions against a person's hand scores, reported as early trial readings (n = 3 to 5),
never as an accuracy claim. Target: weighted kappa of at least 0.60 on item points.

The hand scores are real children's results, so their file must live outside the
repository. The Grader's scores are read from Firestore, and only totals are printed.

From the repository root, with libs/aloai on the path:

    python -m eval.grading_set /outside/the/repo/hand_scores.json

The hand scores give, for each session, the points a person gave each item in the order
asked and the weighted retell credit, for the read passage and, when it ran, the
listening passage:

    {"sessions": [{"session_id": "...",
                   "read": {"item_points": [2, 1], "weighted_credit": 4.5},
                   "listen": null}]}
"""

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import aloai_env
from aloai_store import FirestoreStore, Store, require
from google.cloud import firestore
from services.core.grader import paths

from .models import ROOT

RESULTS = ROOT / "results" / "grading.json"
POINTS = (0, 1, 2)
KAPPA_TARGET = 0.60


def weighted_kappa(a: Sequence[int], b: Sequence[int]) -> float | None:
    """Cohen's kappa with quadratic weights over item points 0, 1 and 2. None when it is
    undefined: every point the same in both lists."""
    if not a or len(a) != len(b):
        raise ValueError("kappa needs two equally long lists of points")
    n, last = len(a), len(POINTS) - 1
    pairs = list(zip(a, b, strict=True))
    weight = [[(i - j) ** 2 / last**2 for j in POINTS] for i in POINTS]
    observed = sum(weight[x][y] for x, y in pairs) / n
    expected = sum(weight[i][j] * a.count(i) * b.count(j) for i in POINTS for j in POINTS) / n**2
    return None if expected == 0 else round(1 - observed / expected, 2)


def agreement(a: Sequence[int], b: Sequence[int]) -> float:
    return round(sum(x == y for x, y in zip(a, b, strict=True)) / len(a), 2)


@dataclass(frozen=True)
class GradingReading:
    sessions: int
    items: int
    kappa: float | None
    item_agreement: float
    quick_vs_final: float | None
    retell_mean_difference: float


def compare(hand: Mapping, store: Store) -> GradingReading:
    hand_points, final_points, quick_pairs, retell_differences = [], [], [], []
    for session in hand["sessions"]:
        session_id = session["session_id"]
        grading = require(store, paths.grading(session_id))
        for part in ("read", "listen"):
            scored, graded = session.get(part), grading.get(part)
            if scored is None or graded is None:
                continue
            if len(scored["item_points"]) != len(graded["item_points"]):
                raise ValueError(f"{session_id} {part}: hand and Grader score different items")
            hand_points += scored["item_points"]
            final_points += graded["item_points"]
            retell_differences.append(abs(scored["weighted_credit"] - graded["weighted_credit"]))
        quick = store.get(paths.quick_result(session_id))
        if quick is not None and grading.get("read") is not None:
            quick_pairs += zip(quick["item_points"], grading["read"]["item_points"], strict=True)
    if not hand_points:
        raise ValueError("no session has both hand scores and the Grader's scores")
    return GradingReading(
        sessions=len(hand["sessions"]),
        items=len(hand_points),
        kappa=weighted_kappa(hand_points, final_points),
        item_agreement=agreement(hand_points, final_points),
        quick_vs_final=agreement(*zip(*quick_pairs, strict=True)) if quick_pairs else None,
        retell_mean_difference=round(sum(retell_differences) / len(retell_differences), 2),
    )


def markdown(reading: GradingReading) -> str:
    kappa = "undefined" if reading.kappa is None else f"{reading.kappa:.2f}"
    quick = "none" if reading.quick_vs_final is None else f"{reading.quick_vs_final:.0%}"
    sample = f"n = {reading.sessions} sessions, {reading.items} items"
    return "\n".join(
        [
            f"Grading, early trial readings ({sample}); not an accuracy claim",
            "",
            "| Measure | Reading | Target |",
            "|---|---|---|",
            f"| Weighted kappa, final vs hand | {kappa} | at least {KAPPA_TARGET:.2f} |",
            f"| Item agreement, final vs hand | {reading.item_agreement:.0%} | reported |",
            f"| Quick vs final item agreement | {quick} | reported |",
            f"| Retell credit, mean difference | {reading.retell_mean_difference} | reported |",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.grading_set")
    parser.add_argument("hand_scores", type=Path, help="JSON file outside the repository")
    options = parser.parse_args(argv)
    if options.hand_scores.resolve().is_relative_to(ROOT.parent):
        print("Keep the hand scores outside the repository: they are real children's results.")
        return 2
    settings = aloai_env.load(os.environ)
    store = FirestoreStore(firestore.Client(project=settings.project))
    reading = compare(json.loads(options.hand_scores.read_text()), store)
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(asdict(reading), indent=2) + "\n")
    print(markdown(reading))
    return 0


if __name__ == "__main__":
    sys.exit(main())
