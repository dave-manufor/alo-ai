"""The Reading Scorer's push subscription on aloai.session-events (SDD 11).

phase1.recorded (checked against its schema with the envelope) is scored; other event
types are acknowledged and ignored. Pub/Sub redelivers anything that is not
acknowledged, so a push that is not a valid event is logged and acknowledged, and an
event that can never be scored (a missing passage, counts aloai_scoring refuses,
telemetry that fails its schema) is
parked in sessions/{session_id}/errors/{type} and acknowledged; the log names the error
only, never the transcripts. Any other failure returns 500, so Pub/Sub retries it and
then sends it to the dead-letter topic.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from aloai_events import park, pushed_event
from fastapi import APIRouter, Body
from fastapi.responses import Response
from jsonschema import ValidationError

from .scorer import Phase1Scorer

log = logging.getLogger(__name__)
PERMANENT = (LookupError, ValueError, ValidationError)


def router(scorer: Phase1Scorer) -> APIRouter:
    routes = APIRouter()

    @routes.post("/pubsub/session-events")
    def session_events(body: Annotated[Any, Body()]) -> Response:
        event = pushed_event(body)
        if event is None:
            log.warning("acknowledged a push that is not a valid event")
            return Response(status_code=204)
        if event["type"] == "phase1.recorded":
            try:
                scorer.handle(event["data"])
            except PERMANENT as error:
                path = park(scorer.store, event, error, datetime.now(UTC))
                log.error("parked %s at %s: %s", event["type"], path, type(error).__name__)
        return Response(status_code=204)

    return routes
