"""Core's push subscription on aloai.session-events (SDD 11).

session.done starts final grading, phase1.scored retries report assembly, report.ready
starts the Reading Coach, plan.ready pre-generates the child's next story, and other
types are ignored. Pub/Sub redelivers anything that
is not acknowledged, so a push that is not a valid event (a type the envelope doesn't
know included) is logged and acknowledged, and an event that can never be handled (an
answer turn with no item, a missing document, a value aloai_scoring refuses, a report
that fails its schema) is parked
in sessions/{session_id}/errors/{type} and acknowledged. Any other failure returns 500,
so Pub/Sub retries it and then sends it to the dead-letter topic. A push without the
push service account's signed ID token is refused with 403 (aloai_events.pushed_by).
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from aloai_events import PushCheck, park, pushed_event
from aloai_store import Store
from fastapi import APIRouter, Body, Header
from fastapi.responses import Response
from jsonschema import ValidationError

from .coach.run import ReadingCoach
from .generator_requests import NextStories
from .grader.assembly import ReportAssembler
from .grader.final import FinalGrader

log = logging.getLogger(__name__)
PERMANENT = (LookupError, ValueError, ValidationError)


def events_router(
    final: FinalGrader,
    assembler: ReportAssembler,
    coach: ReadingCoach,
    store: Store,
    from_pubsub: PushCheck,
    next_stories: NextStories | None = None,
) -> APIRouter:
    routes = APIRouter()

    @routes.post("/pubsub/session-events")
    def session_events(
        body: Annotated[Any, Body()], authorization: Annotated[str | None, Header()] = None
    ) -> Response:
        if not from_pubsub(authorization):
            log.warning("refused a push not signed by the push service account")
            return Response(status_code=403)
        event = pushed_event(body)
        if event is None:
            log.warning("acknowledged a push that is not a valid event")
            return Response(status_code=204)
        try:
            match event["type"]:
                case "session.done":
                    final.handle(event["data"])
                case "phase1.scored":
                    assembler.assemble(event["session_id"])
                case "report.ready":
                    coach.handle(event["data"])
                case "plan.ready" if next_stories is not None:
                    next_stories.handle(event["session_id"])
        except PERMANENT as error:
            path = park(store, event, error, datetime.now(UTC))
            log.error("parked %s at %s: %s", event["type"], path, type(error).__name__)
        return Response(status_code=204)

    return routes
