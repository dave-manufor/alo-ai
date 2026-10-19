"""The Reading Scorer's push subscription on aloai.session-events (SDD 11).

phase1.recorded is scored; other event types are acknowledged and ignored. A failure
while scoring returns 500, so Pub/Sub retries, then sends the event to the dead-letter
topic.
"""

from typing import Annotated, Any

from aloai_events import pushed_event
from fastapi import APIRouter, Body
from fastapi.responses import Response

from .scorer import Phase1Scorer


def router(scorer: Phase1Scorer) -> APIRouter:
    routes = APIRouter()

    @routes.post("/pubsub/session-events")
    def session_events(body: Annotated[Any, Body()]) -> Response:
        event = pushed_event(body)
        if event is None:
            return Response(status_code=400)
        if event["type"] == "phase1.recorded":
            scorer.handle(event["data"])
        return Response(status_code=204)

    return routes
