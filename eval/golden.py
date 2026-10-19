"""The golden-recording check (PRD 13.5): the Reading Scorer's WCPM and accuracy on each
golden recording must land within 5 words per minute and 3 accuracy points of a
person's hand count. eval/golden/index.json lists each recording's session and its hand
count; the check reads the telemetry the deployed Reading Scorer wrote for that session.
The hand count goes through the same aloai_scoring rules, so both sides follow the
told-word wait the same way.

From the repository root, with libs/aloai on the path:

    python -m eval.golden
"""

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

import aloai_env
import aloai_scoring as scoring
from aloai_store import FirestoreStore, Store, require
from google.cloud import firestore
from services.core.grader import paths

from .models import ROOT

INDEX = ROOT / "golden" / "index.json"
RESULTS = ROOT / "results" / "golden.json"
WCPM_TOLERANCE = 5
ACCURACY_TOLERANCE = 3


def hand_fluency(hand: Mapping[str, float]) -> scoring.Fluency:
    told = hand["told"]
    return scoring.fluency(
        words_attempted=hand["words_attempted"],
        reading_seconds=hand["reading_seconds"],
        substitutions=hand["errors"] - told,
        omissions=0,
        told=told,
        told_waits=hand.get("told_waits", told),
        mispronunciations=0,
        self_corrections=0,
        uncertain=0,
    )


@dataclass(frozen=True)
class GoldenResult:
    recording_id: str
    hand_wcpm: float | None
    scorer_wcpm: float | None
    hand_accuracy: float | None
    scorer_accuracy: float | None

    @property
    def within(self) -> bool:
        return _close(self.hand_wcpm, self.scorer_wcpm, WCPM_TOLERANCE) and _close(
            self.hand_accuracy, self.scorer_accuracy, ACCURACY_TOLERANCE
        )


def _close(hand: float | None, scorer: float | None, tolerance: float) -> bool:
    if hand is None or scorer is None:
        return hand is scorer
    return abs(hand - scorer) <= tolerance


def check(recordings: Sequence[Mapping], store: Store) -> list[GoldenResult]:
    results = []
    for recording in recordings:
        hand = hand_fluency(recording["hand"])
        telemetry = require(store, paths.telemetry(recording["session_id"]))
        results.append(
            GoldenResult(
                recording_id=recording["recording_id"],
                hand_wcpm=hand.wcpm,
                scorer_wcpm=telemetry["wcpm"],
                hand_accuracy=hand.accuracy_pct,
                scorer_accuracy=telemetry["accuracy_pct"],
            )
        )
    return results


def markdown(results: Sequence[GoldenResult]) -> str:
    within = sum(result.within for result in results)
    tolerance = f"±{WCPM_TOLERANCE} WCPM and ±{ACCURACY_TOLERANCE} accuracy points"
    lines = [
        f"Golden recordings: {within} of {len(results)} within {tolerance} (early trial readings)",
        "",
        "| Recording | WCPM hand | WCPM scorer | Accuracy hand | Accuracy scorer | Within |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r.recording_id} | {r.hand_wcpm} | {r.scorer_wcpm} | {r.hand_accuracy} "
        f"| {r.scorer_accuracy} | {'yes' if r.within else 'no'} |"
        for r in results
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    recordings = json.loads(INDEX.read_text())["recordings"]
    if not recordings:
        print("No golden recordings yet: add them to eval/golden/index.json.")
        return 2
    settings = aloai_env.load(os.environ)
    results = check(recordings, FirestoreStore(firestore.Client(project=settings.project)))
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(
        json.dumps([asdict(r) | {"within": r.within} for r in results], indent=2) + "\n"
    )
    print(markdown(results))
    return 0 if all(result.within for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
