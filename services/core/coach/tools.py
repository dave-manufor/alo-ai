"""The Reading Coach's tools (PRD 3.1, 12.1; SDD 8 and 11).

Each call has already passed authorize() (agent.py), so a session or child argument is
this run's. The hard limits live here, not in the prompt: the tools read only this run's
report and child, offer only library activities and catalogue books, and save_plan
refuses a plan whose activities, books or text fail the checks. After a second refusal
it saves the template plan (COACH_TEMPLATE_USED).

get_activity_library and search_books take no arguments: the profile, level and ranked
books (PRD 9.3) are already in the report, so the model cannot ask for others.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

import aloai_contracts
from aloai_guardrails import validate_parent_summary
from aloai_store import Store

from ..grader import paths
from . import library
from .clients import REPORT_READY, Notifier, StoryRequests
from .plan import save_next_check, write_plan, write_template_plan
from .template import UNNAMED_CHILD, next_check_days

ACTIVITIES_PER_PLAN = 3
BOOKS_PER_PLAN = 3
MAX_TAGS = 2
HIDDEN_REPORT_FIELDS = ("guardian_id", "versions")
FIRST_NAME = re.compile(r"[^\W\d_]+(?:[ '-][^\W\d_]+){0,2}")
MAX_NAME_LENGTH = 30


def topic_tags(tags: Sequence[str]) -> list[str]:
    """The tags in the topic taxonomy (schemas/topic_tag.schema.json), each once. Anything
    else, such as free text that reached a tag field, is dropped."""
    return [tag for tag in dict.fromkeys(tags) if tag in aloai_contracts.TOPIC_TAGS]


def first_name(store: Store, report: dict) -> str:
    """The name the parent gave, or "Your child" when it does not look like a first name
    (one to three words of letters), so text typed into the name can't steer the Coach."""
    child = store.get(paths.child(report["child_id"])) or {}
    name = (child.get("first_name") or "").strip()
    if len(name) <= MAX_NAME_LENGTH and FIRST_NAME.fullmatch(name):
        return name
    return UNNAMED_CHILD


def catalogue_books(store: Store, report: dict) -> list[dict]:
    """The report's ranked books that are in the catalogue."""
    books = []
    for book_id in report["recommendations"]["book_ids"]:
        book = store.get(f"books/{book_id}")
        if book is not None:
            books.append(
                {"book_id": book_id, "title": book["title"], "licence": book.get("licence")}
            )
    return books


@dataclass
class CoachTools:
    store: Store
    report: dict
    stories: StoryRequests
    notifier: Notifier
    now: datetime
    failed_saves: int = 0
    plan: dict | None = None
    delivery_id: str | None = None

    def functions(self) -> list[Callable]:
        return [
            self.get_report,
            self.get_history,
            self.get_activity_library,
            self.search_books,
            self.queue_story,
            self.schedule_session,
            self.save_plan,
            self.send_parent_email,
        ]

    def get_report(self, session_id: str) -> dict:
        """This session's reading report: fluency, comprehension, level, profile, the
        recommended book band and flags.

        Args:
            session_id: the session the plan is for.
        """
        return {key: value for key, value in self.report.items() if key not in HIDDEN_REPORT_FIELDS}

    def get_history(self, child_id: str) -> dict:
        """The child's first name, saved interest tags, earlier checks and last plan.

        Args:
            child_id: the child the plan is for.
        """
        child = self.store.get(paths.child(child_id)) or {}
        return {
            "first_name": first_name(self.store, self.report),
            "saved_tags": topic_tags(child.get("saved_tags", [])),
            "earlier_checks": [
                {
                    "timestamp_iso": report["timestamp_iso"],
                    "profile": report["profile"]["code"],
                    "reported_arl": report["level"]["reported_arl"],
                }
                for report in self._earlier("reports", child_id, "timestamp_iso")
            ],
            "last_plan": self._last_plan(child_id),
        }

    def get_activity_library(self) -> dict:
        """The home activities this plan may use: the library's activities for the report's
        profile and level. Choose three."""
        return {
            "library": library.VERSION,
            "activities": [
                {key: activity[key] for key in ("activity_id", "title", "text")}
                for activity in self._activities()
            ],
        }

    def search_books(self) -> dict:
        """The catalogue books ranked for this child. The plan may name only these."""
        return {"books": catalogue_books(self.store, self.report)}

    def queue_story(self, child_id: str, arl: int, tags: list[str]) -> dict:
        """Queue the child's next story, at the report's next_passage_arl, on one of the
        child's saved tags plus one new topic.

        Args:
            child_id: the child the plan is for.
            arl: the report's next_passage_arl.
            tags: one or two different tags from the topic list, such as animals.
        """
        expected = self.report["level"]["next_passage_arl"]
        if arl != expected:
            return {"error": f"the next story is at level {expected}"}
        if not 1 <= len(tags) <= MAX_TAGS or topic_tags(tags) != list(tags):
            allowed = ", ".join(aloai_contracts.TOPIC_TAGS)
            return {"error": f"give one or two different tags from: {allowed}"}
        request_id = self.stories.queue(
            session_id=self.report["session_id"], child_id=child_id, arl=arl, tags=tags
        )
        return {"request_id": request_id}

    def schedule_session(self, child_id: str, days: int) -> dict:
        """Set the child's next check: in 14 days, or in 7 when the profile is provisional
        or INSUFFICIENT_EVIDENCE.

        Args:
            child_id: the child the plan is for.
            days: 7 or 14.
        """
        expected = next_check_days(self.report)
        if days != expected:
            return {"error": f"the next check for this report is in {expected} days"}
        return {"next_session_at": save_next_check(self.store, self.report, self.now)}

    def save_plan(
        self,
        child_id: str,
        activity_ids: list[str],
        book_ids: list[str],
        summary: str,
        home_practice: str,
    ) -> dict:
        """Save the two-week plan and the parent's text. Both are checked before saving;
        if problems come back, fix every one and call save_plan once more.

        Args:
            child_id: the child the plan is for.
            activity_ids: three activity ids from get_activity_library.
            book_ids: up to three book ids from search_books.
            summary: the spoken parent summary, at most 90 words.
            home_practice: one or two sentences on what to practise at home.
        """
        if self.plan is not None:
            return {"error": "the plan is already saved"}
        problems = self._problems(activity_ids, book_ids, summary, home_practice)
        if not problems:
            self.plan = write_plan(
                self.store,
                self.report,
                activity_ids=activity_ids,
                book_ids=book_ids,
                summary=summary,
                home_practice=home_practice,
                template_used=False,
                now=self.now,
            )
        elif self.failed_saves == 0:
            self.failed_saves += 1
            return {"saved": False, "problems": problems}
        else:
            self.plan = write_template_plan(
                self.store,
                self.report,
                first_name=first_name(self.store, self.report),
                book_ids=[book["book_id"] for book in catalogue_books(self.store, self.report)],
                now=self.now,
            )
        return {
            "saved": True,
            "plan_id": self.plan["plan_id"],
            "template_used": self.plan["template_used"],
        }

    def send_parent_email(self, child_id: str, template_id: str) -> dict:
        """Email the parent that the report is ready. The email is a fixed template and
        carries no scores. Send it after save_plan.

        Args:
            child_id: the child the plan is for.
            template_id: report_ready.
        """
        if template_id != REPORT_READY:
            return {"error": f"the only template is {REPORT_READY}"}
        if self.plan is None:
            return {"error": "save the plan first"}
        self.delivery_id = self.notifier.notify(
            template_id=REPORT_READY,
            guardian_id=self.report["guardian_id"],
            child_id=child_id,
            session_id=self.report["session_id"],
        )
        return {"delivery_id": self.delivery_id}

    def _activities(self) -> list[dict]:
        return library.activities_for(
            self.report["profile"]["code"], self.report["level"]["reported_arl"]
        )

    def _problems(
        self, activity_ids: Sequence[str], book_ids: Sequence[str], summary: str, home_practice: str
    ) -> list[str]:
        allowed = {activity["activity_id"] for activity in self._activities()}
        wanted = min(ACTIVITIES_PER_PLAN, len(allowed))
        offered = {book["book_id"] for book in catalogue_books(self.store, self.report)}
        problems = []
        if len(set(activity_ids)) != wanted or len(activity_ids) != wanted:
            problems.append(f"choose {wanted} different activities")
        problems += [
            f"{a} is not in the library for this report" for a in activity_ids if a not in allowed
        ]
        if len(set(book_ids)) != len(book_ids) or len(book_ids) > BOOKS_PER_PLAN:
            problems.append(f"choose up to {BOOKS_PER_PLAN} different books")
        problems += [
            f"{b} is not a book search_books offered" for b in book_ids if b not in offered
        ]
        numbers = (next_check_days(self.report), wanted, len(book_ids))
        for name, text in (("summary", summary), ("home practice", home_practice)):
            if not text.strip():
                problems.append(f"{name} is empty")
            problems += [
                f"{name}: {p}" for p in validate_parent_summary(text, self.report, numbers)
            ]
        return problems

    def _earlier(self, collection: str, child_id: str, order_by: str) -> list[dict]:
        documents = self.store.where(collection, "child_id", child_id)
        earlier = [d for d in documents if d["session_id"] != self.report["session_id"]]
        return sorted(earlier, key=lambda document: document[order_by])

    def _last_plan(self, child_id: str) -> dict | None:
        plans = self._earlier("plans", child_id, "created_at")
        if not plans:
            return None
        last = plans[-1]
        return {
            "activity_ids": [activity["activity_id"] for activity in last["activities"]],
            "book_ids": last["book_ids"],
            "created_at": last["created_at"],
        }
