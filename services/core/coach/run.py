"""The Reading Coach run (PRD 3.1, 12.1; SDD 8), triggered by report.ready.

The run context comes from the report and the consent records, never from the model.
With no consent on file the Coach reads nothing and makes no plan. With the Coach turned
off (COACH_ON), or when its run ends without a saved plan, the template plan is saved.
The plan is made once per session; a redelivered report.ready only finishes what is
left: the spoken summary, the email (sent once per session by the notifier), and
plan.ready.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from aloai_authz import RunContext
from aloai_events import Publisher, envelope
from aloai_store import Store, require
from google.adk.models import BaseLlm

from ..grader import paths
from .agent import Guard, coach_agent, run_coach
from .clients import REPORT_READY, Notifier, Speaker, StoryRequests
from .plan import plan_path, write_template_plan
from .tools import CoachTools, catalogue_books, first_name

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class ReadingCoach:
    store: Store
    publisher: Publisher
    stories: StoryRequests
    notifier: Notifier
    speaker: Speaker
    model_for: Callable[[str], BaseLlm | str]
    enabled: bool = True
    clock: Callable[[], datetime] = _now
    new_id: Callable[[], str] = _new_id

    def handle(self, data: dict) -> None:
        report = require(self.store, paths.report(data["session_id"]))
        ctx = self._context(report)
        if not ctx.consent_on_file:
            logger.warning("no consent on file for session %s; no plan made", ctx.session_id)
            return
        plan = self.store.get(plan_path(ctx.session_id))
        emailed = False
        if plan is None:
            plan, emailed = self._new_plan(report, ctx)
        self._speak(plan)
        if not emailed:
            self.notifier.notify(
                template_id=REPORT_READY,
                guardian_id=report["guardian_id"],
                child_id=report["child_id"],
                session_id=ctx.session_id,
            )
        self._publish(plan)

    def _context(self, report: dict) -> RunContext:
        consents = self.store.where("consents", "child_id", report["child_id"])
        return RunContext(
            agent="reading_coach",
            principal_id=report["guardian_id"],
            session_id=report["session_id"],
            child_id=report["child_id"],
            consent_on_file=any(c.get("guardian_id") == report["guardian_id"] for c in consents),
        )

    def _new_plan(self, report: dict, ctx: RunContext) -> tuple[dict, bool]:
        """The saved plan, and whether the Coach already sent the email."""
        tools = CoachTools(self.store, report, self.stories, self.notifier, self.clock())
        if self.enabled:
            self._run_agent(tools, ctx)
        if tools.plan is None:
            tools.plan = write_template_plan(
                self.store,
                report,
                first_name=first_name(self.store, report),
                book_ids=[book["book_id"] for book in catalogue_books(self.store, report)],
                now=tools.now,
            )
        return tools.plan, tools.delivery_id is not None

    def _run_agent(self, tools: CoachTools, ctx: RunContext) -> None:
        guard = Guard(ctx, self.store, self.clock, self.new_id)
        try:
            asyncio.run(run_coach(coach_agent(self.model_for(ctx.session_id), tools, guard), ctx))
        except Exception:
            logger.exception("the Reading Coach failed for session %s", ctx.session_id)

    def _speak(self, plan: dict) -> None:
        if plan["summary_audio_uri"] is not None:
            return
        report = require(self.store, paths.report(plan["session_id"]))
        uri = self.speaker.speak(report["parent_reporting"]["summary_script"], plan["session_id"])
        if uri is not None:
            self.store.merge(plan_path(plan["session_id"]), {"summary_audio_uri": uri})

    def _publish(self, plan: dict) -> None:
        data = {
            "session_id": plan["session_id"],
            "plan_ref": plan_path(plan["session_id"]),
            "template_used": plan["template_used"],
        }
        self.publisher.publish(envelope("plan.ready", plan["session_id"], data, now=self.clock()))
