"""Core's push subscription on aloai.session-events (SDD 11).

session.done starts final grading, phase1.scored retries report assembly, report.ready
starts the Reading Coach, and other types are ignored. A failure while handling an event
returns 500, so Pub/Sub retries.
"""

from typing import Annotated, Any

from aloai_events import pushed_event
from fastapi import APIRouter, Body
from fastapi.responses import Response

from .coach.run import ReadingCoach
from .grader.assembly import ReportAssembler
from .grader.final import FinalGrader


def events_router(final: FinalGrader, assembler: ReportAssembler, coach: ReadingCoach) -> APIRouter:
    routes = APIRouter()

    @routes.post("/pubsub/session-events")
    def session_events(body: Annotated[Any, Body()]) -> Response:
        event = pushed_event(body)
        if event is None:
            return Response(status_code=400)
        match event["type"]:
            case "session.done":
                final.handle(event["data"])
            case "phase1.scored":
                assembler.assemble(event["session_id"])
            case "report.ready":
                coach.handle(event["data"])
        return Response(status_code=204)

    return routes
