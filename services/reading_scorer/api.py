"""The Reading Scorer's events from aloai.session-events (SDD 11): event_handler does the work
on either cloud; router is the Pub/Sub push route in front of it (GCP). On Azure the Service
Bus pump (aloai_events.QueuePump) calls the same handler, and the route is not mounted.

phase1.recorded (checked against its schema with the envelope) is scored; other event
types are acknowledged and ignored. Pub/Sub redelivers anything that is not
acknowledged, so a push that is not a valid event is logged and acknowledged, and an
event that can never be scored (a missing passage, counts aloai_scoring refuses,
telemetry that fails its schema) is
parked in sessions/{session_id}/errors/{type} and acknowledged; the log names the error
only, never the transcripts. Any other failure returns 500, so Pub/Sub retries it and
then sends it to the dead-letter topic. A push without the push service account's signed
ID token is refused with 403 (aloai_events.pushed_by).
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from aloai_events import PushCheck, park, pushed_event
from fastapi import APIRouter, Body, Header
from fastapi.responses import Response
from jsonschema import ValidationError

from .scorer import Phase1Scorer

log = logging.getLogger(__name__)
PERMANENT = (LookupError, ValueError, ValidationError)


def event_handler(scorer: Phase1Scorer) -> Callable[[dict], None]:
    """What the Scorer does with one valid event, on either cloud. It returns when the event
    is done with (scored, ignored, or parked because it can never succeed) and raises for
    any other failure, which the Pub/Sub push route answers with 500 and the Service Bus
    pump answers by abandoning the message, so the event is delivered again."""

    def handle(event: dict) -> None:
        if event["type"] != "phase1.recorded":
            return
        try:
            scorer.handle(event["data"])
        except PERMANENT as error:
            path = park(scorer.store, event, error, datetime.now(UTC))
            log.error("parked %s at %s: %s", event["type"], path, type(error).__name__)

    return handle


def router(scorer: Phase1Scorer, from_pubsub: PushCheck) -> APIRouter:
    routes = APIRouter()
    handle = event_handler(scorer)

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
        handle(event)
        return Response(status_code=204)

    return routes
