"""The Reading Coach evaluation set (PRD 13.4): 10 reports across the main profiles, with
provisional, LC_MISSED and missing-field cases, in eval/coach/cases.json. Each case runs
the real Coach and is scored on three metrics, each with its threshold:

- tool sequence: the PRD 3.1 steps in order (tools in one step in any order, save_plan
  once more for a rewrite) and no other tool
- library only: every activity in the plan comes from the library for the report
- validator first try: the Coach's first summary passed the guardrail

    python -m eval.coach_set                  replay eval/recorded/coach/ (free; CI)
    python -m eval.coach_set --live           Gemini on Vertex AI (spends the shared budget)
    python -m eval.coach_set --live --record  also save the turns for the replay
"""

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import aloai_env
from google.adk.models import BaseLlm
from services.core.coach import library
from services.core.coach.agent import COACH_MODEL, PROMPT_VERSION

from .harness import CoachRun, run_case
from .models import ROOT, RecordingModel, live_coach_model, recorded_model, recording_path

SET = "coach"
CASES = ROOT / "coach" / "cases.json"
RESULTS = ROOT / "results" / "coach.json"
STEPS = (
    {"get_report", "get_history"},
    {"get_activity_library", "search_books"},
    {"queue_story", "schedule_session"},
    {"save_plan"},
    {"send_parent_email"},
)
THRESHOLDS = {"tool_sequence": 9, "library_only": 10, "validator_first_try": 9}


def cases() -> list[dict]:
    return json.loads(CASES.read_text())["cases"]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    tool_sequence: bool
    library_only: bool
    validator_first_try: bool
    tools: list[str]


def tool_sequence_ok(tools: Sequence[str]) -> bool:
    calls = [t for i, t in enumerate(tools) if not (t == "save_plan" and tools[i - 1 : i] == [t])]
    step_of = {tool: number for number, step in enumerate(STEPS) for tool in step}
    if any(tool not in step_of for tool in calls):
        return False
    order = [step_of[tool] for tool in calls]
    return order == sorted(order) and sorted(calls) == sorted(t for step in STEPS for t in step)


def library_only(run: CoachRun) -> bool:
    if run.plan is None:
        return False
    profile, arl = run.report["profile"]["code"], run.report["level"]["reported_arl"]
    allowed = {activity["activity_id"] for activity in library.activities_for(profile, arl)}
    return all(activity["activity_id"] in allowed for activity in run.plan["activities"])


def validator_first_try(run: CoachRun) -> bool:
    saves = [entry for entry in run.audit if entry["tool"] == "save_plan" and entry["allowed"]]
    return run.plan is not None and not run.plan["template_used"] and len(saves) == 1


def score(case_id: str, run: CoachRun) -> CaseResult:
    tools = [entry["tool"] for entry in run.audit]
    return CaseResult(
        case_id=case_id,
        tool_sequence=tool_sequence_ok(tools),
        library_only=library_only(run),
        validator_first_try=validator_first_try(run),
        tools=tools,
    )


def totals(results: Sequence[CaseResult]) -> dict[str, int]:
    return {metric: sum(getattr(result, metric) for result in results) for metric in THRESHOLDS}


def passed(results: Sequence[CaseResult]) -> bool:
    return all(count >= THRESHOLDS[metric] for metric, count in totals(results).items())


def evaluate(model_for: Callable[[Mapping[str, Any]], BaseLlm]) -> list[CaseResult]:
    return [score(case["case_id"], run_case(case, model_for(case))) for case in cases()]


def markdown(results: Sequence[CaseResult], mode: str) -> str:
    counts = totals(results)
    verdict = "PASS" if passed(results) else "FAIL"
    lines = [
        f"Reading Coach set, {mode}, {COACH_MODEL}, prompt {PROMPT_VERSION}: {verdict}",
        "",
        "| Metric | Result | Threshold |",
        "|---|---|---|",
        *(f"| {m} | {counts[m]} of {len(results)} | {t} |" for m, t in THRESHOLDS.items()),
    ]
    failures = [r for r in results if not all(getattr(r, m) for m in THRESHOLDS)]
    lines += [f"- {r.case_id}: {', '.join(r.tools)}" for r in failures]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    options = _options(argv)
    if not options.live:
        missing = [c["case_id"] for c in cases() if not recording_path(SET, c["case_id"]).exists()]
        if missing:
            print(f"No recorded run for {', '.join(missing)}: run with --live --record first.")
            return 2
        results = evaluate(lambda case: recorded_model(SET, case["case_id"]))
        print(markdown(results, "recorded"))
        return 0 if passed(results) else 1
    settings = aloai_env.load(os.environ)
    recorders: dict[str, RecordingModel] = {}

    def live(case: Mapping[str, Any]) -> BaseLlm:
        model = live_coach_model(settings.project, settings.location)
        if not options.record:
            return model
        recorders[case["case_id"]] = RecordingModel(model=model.model, inner=model)
        return recorders[case["case_id"]]

    results = evaluate(live)
    for case_id, recorder in recorders.items():
        recorder.save(recording_path(SET, case_id))
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps([asdict(r) for r in results], indent=2) + "\n")
    print(markdown(results, "live"))
    return 0 if passed(results) else 1


def _options(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m eval.coach_set")
    parser.add_argument("--live", action="store_true", help="call Gemini (spends budget)")
    parser.add_argument("--record", action="store_true", help="save the turns for replay")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
