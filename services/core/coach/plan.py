"""The two-week plan (plans/{plan_id}, schemas/plan.schema.json) and the Coach's text on
the report. The Reading Coach writes only parent_reporting and, for a template plan, the
COACH_TEMPLATE_USED flag; every other field of the report was written by the Grader. The
report's text is written before the plan, so a saved plan always has its summary."""

from collections.abc import Sequence
from datetime import datetime, timedelta

import aloai_contracts
from aloai_events import iso_utc
from aloai_store import Store

from . import library
from .template import default_activities, next_check_days, template_home_practice, template_summary

SCHEMA_VERSION = 1
TEMPLATE_FLAG = "COACH_TEMPLATE_USED"


def plan_id(session_id: str) -> str:
    return f"plan_{session_id}"


def plan_path(session_id: str) -> str:
    return f"plans/{plan_id(session_id)}"


def next_session_at(report: dict, now: datetime) -> datetime:
    return now + timedelta(days=next_check_days(report))


def write_plan(
    store: Store,
    report: dict,
    *,
    activity_ids: Sequence[str],
    book_ids: Sequence[str],
    summary: str,
    home_practice: str,
    template_used: bool,
    now: datetime,
) -> dict:
    session_id = report["session_id"]
    plan = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id(session_id),
        "session_id": session_id,
        "child_id": report["child_id"],
        "guardian_id": report["guardian_id"],
        "activities": [
            {key: library.ACTIVITIES[activity_id][key] for key in ("activity_id", "title", "text")}
            for activity_id in activity_ids
        ],
        "book_ids": list(book_ids),
        "next_session_at": iso_utc(next_session_at(report, now)),
        "summary_audio_uri": None,
        "template_used": template_used,
        "activity_library": library.VERSION,
        "created_at": iso_utc(now),
    }
    aloai_contracts.PLAN.validate(plan)
    text = {"parent_reporting": {"summary_script": summary, "home_practice": home_practice}}
    if template_used and TEMPLATE_FLAG not in report["flags"]:
        text["flags"] = [*report["flags"], TEMPLATE_FLAG]
    store.merge(f"reports/{session_id}", text)
    store.set(plan_path(session_id), plan)
    return plan


def write_template_plan(
    store: Store, report: dict, *, first_name: str, book_ids: Sequence[str], now: datetime
) -> dict:
    """The default plan and template summary (COACH_TEMPLATE_USED)."""
    return write_plan(
        store,
        report,
        activity_ids=[activity["activity_id"] for activity in default_activities(report)],
        book_ids=book_ids,
        summary=template_summary(report, first_name),
        home_practice=template_home_practice(report),
        template_used=True,
        now=now,
    )
