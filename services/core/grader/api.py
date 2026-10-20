"""The Grader's HTTP route (SDD 11): POST /v1/grade:quick, called by the Session Agent.
Its errors use the SDD 11 shape; Vertex AI or Firestore not answering is a retryable
503 UPSTREAM_UNAVAILABLE."""

from typing import Annotated, Any

import aloai_contracts
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator

from .models import GradingError, UpstreamErrors
from .quick import PassageNotFound, QuickGrader, UnknownItem


def router(quick: QuickGrader) -> APIRouter:
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
        except UpstreamErrors as error:
            return _error(503, "UPSTREAM_UNAVAILABLE", type(error).__name__, retryable=True)

    return routes


def _first_error(validator: Draft202012Validator, body: Any) -> str | None:
    error = next(iter(validator.iter_errors(body)), None)
    return None if error is None else error.message


def _error(status: int, code: str, message: str, *, retryable: bool) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        status_code=status,
    )
