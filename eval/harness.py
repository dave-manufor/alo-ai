"""The real Reading Coach run on one evaluation case (PRD 13.4).

A case is the fictional demo session, sess_demo_001, with its report changed as the case
says: the profile (its texts and book band follow from it), flags, and any field named
by its dotted path, plus the child's name, interests, history and consent. The Coach runs
through ReadingCoach.handle on an in-memory store that logs every document it reads, so
a check can show that no other child's data was touched.
"""

import copy
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aloai_contracts
import aloai_scoring as scoring
from aloai_events import MemoryPublisher
from aloai_store import MemoryStore
from google.adk.models import BaseLlm
from services.core.coach.clients import SilentSpeaker, StoryRequests
from services.core.coach.plan import plan_path
from services.core.coach.run import ReadingCoach
from services.core.grader import paths
from services.core.grader.report import PROFILE_TEXT

SESSION_ID = "sess_demo_001"
CHILD_ID = "child_demo_001"
GUARDIAN_ID = "guardian_demo_001"
NOW = datetime(2026, 1, 15, 9, 9, 20, tzinfo=UTC)
CONTRACTS = Path(__file__).resolve().parents[1] / "fixtures" / "contracts"
CATALOGUE = {
    f"book_demo_00{n}": {"title": f"Demo Book {n}", "licence": "CC BY", "arl": arl}
    for n, arl in ((1, 2), (2, 1), (3, 2))
}


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text())


class ReadLog(MemoryStore):
    """A MemoryStore that remembers every path and query it answered."""

    def __init__(self, docs: dict[str, dict]) -> None:
        super().__init__(docs)
        self.reads: list[str] = []

    def get(self, path: str) -> dict | None:
        self.reads.append(path)
        return super().get(path)

    def where(self, collection: str, field: str, value: Any) -> list[dict]:
        self.reads.append(f"{collection}?{field}={value}")
        return super().where(collection, field, value)


class Notifications:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def notify(self, **request: str) -> str:
        self.sent.append(request)
        return f"delivery_{len(self.sent)}"


@dataclass(frozen=True)
class CoachRun:
    report: dict
    plan: dict | None
    audit: list[dict]
    reads: list[str]
    emails: list[dict]
    events: list[dict]
    story_requests: list[dict]


def case_report(case: Mapping[str, Any]) -> dict:
    report = contract("reading_report.sess_demo_001.json")
    for path, value in case.get("report", {}).items():
        *parents, name = path.split(".")
        target = report
        for parent in parents:
            target = target[parent]
        target[name] = value
    code = case.get("profile", report["profile"]["code"])
    need, focus = PROFILE_TEXT[code]
    report["profile"] |= {
        "code": code,
        "provisional": case.get("provisional", report["profile"]["provisional"]),
        "primary_need": need,
        "instructional_focus": focus,
    }
    report["flags"] = case.get("flags", report["flags"])
    band = scoring.book_band(code, report["level"]["reported_arl"])
    report["recommendations"] = {
        "arl_min": band[0] if band else None,
        "arl_max": band[1] if band else None,
        "book_ids": report["recommendations"]["book_ids"] if band else [],
    }
    aloai_contracts.READING_REPORT.validate(report)
    return report


def case_store(case: Mapping[str, Any]) -> ReadLog:
    report = case_report(case)
    docs = {
        paths.report(SESSION_ID): report,
        paths.child(CHILD_ID): {
            "guardian_id": GUARDIAN_ID,
            "first_name": case.get("first_name", "Chidi"),
            "saved_tags": case.get("saved_tags", ["food"]),
        },
        **{f"books/{book_id}": book for book_id, book in CATALOGUE.items()},
    }
    if case.get("consent", True):
        docs["consents/consent_demo_001"] = {"guardian_id": GUARDIAN_ID, "child_id": CHILD_ID}
    if case.get("returning"):
        docs |= _history(report)
    return ReadLog(docs)


def _history(report: dict) -> dict[str, dict]:
    earlier = copy.deepcopy(report) | {
        "session_id": "sess_demo_000",
        "timestamp_iso": "2026-01-01T09:00:00Z",
    }
    plan = contract("plan.sess_demo_001.json") | {
        "plan_id": "plan_sess_demo_000",
        "session_id": "sess_demo_000",
        "created_at": "2026-01-01T09:09:20Z",
    }
    return {paths.report("sess_demo_000"): earlier, "plans/plan_sess_demo_000": plan}


def run_case(case: Mapping[str, Any], model: BaseLlm) -> CoachRun:
    store = case_store(case)
    publisher, notifications = MemoryPublisher(), Notifications()
    coach = ReadingCoach(
        store=store,
        publisher=publisher,
        stories=StoryRequests(store),
        notifier=notifications,
        speaker=SilentSpeaker(),
        model_for=_always(model),
        clock=lambda: NOW,
    )
    coach.handle(contract("event.report_ready.json")["data"])
    return CoachRun(
        report=store.docs[paths.report(SESSION_ID)],
        plan=store.docs.get(plan_path(SESSION_ID)),
        audit=[doc for path, doc in store.docs.items() if path.startswith("audit_log/")],
        reads=store.reads,
        emails=notifications.sent,
        events=publisher.events,
        story_requests=[d for p, d in store.docs.items() if p.startswith("story_requests/")],
    )


def _always(model: BaseLlm) -> Callable[[str], BaseLlm]:
    return lambda session_id: model
