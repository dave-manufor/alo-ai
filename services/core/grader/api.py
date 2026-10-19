"""The Grader's HTTP routes (SDD 11).

POST /v1/grade:quick is called by the Session Agent; its errors use the SDD 11 shape.
POST /pubsub/session-events is Core's push subscription on aloai.session-events:
session.done starts final grading, phase1.scored retries report assembly, and other
types are ignored. A failure while handling an event returns 500, so Pub/Sub retries.
"""

from typing import Annotated, Any

import aloai_contracts
from aloai_events import pushed_event
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, Response
from jsonschema import Draft202012Validator

from .assembly import ReportAssembler
from .final import FinalGrader
from .models import GradingError
from .quick import PassageNotFound, QuickGrader, UnknownItem


def router(quick: QuickGrader, final: FinalGrader, assembler: ReportAssembler) -> APIRouter:
    routes = APIRouter()

    @routes.post("/v1/grade:quick")
    def grade_quick(body: Annotated[Any, Body()]) -> JSONResponse:
        problem = _first_error(aloai_contracts.GRADE_QUICK_REQUEST, body)
        if problem is not None:
            return _error(400, "INVALID_REQUEST", problem, retryable=False)
        try:
            return JSONResponse(quick.grade(body))
        except PassageNotFound as error:
            return _error(404, "PASSAGE_NOT_FOUND", str(error), retryable=False)
        except UnknownItem as error:
            return _error(400, "UNKNOWN_ITEM", str(error), retryable=False)
        except GradingError as error:
            return _error(502, "GRADING_FAILED", str(error), retryable=True)

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
        return Response(status_code=204)

    return routes


def _first_error(validator: Draft202012Validator, body: Any) -> str | None:
    error = next(iter(validator.iter_errors(body)), None)
    return None if error is None else error.message


def _error(status: int, code: str, message: str, *, retryable: bool) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        status_code=status,
    )
