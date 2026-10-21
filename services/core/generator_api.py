"""The Passage Generator's HTTP route (SDD 11): POST /v1/passages:generate, called by
the Session Agent when the interest chat ends.

It generates and gates a READ passage (generator/pipeline.py), pairs it with a bank
LISTEN passage, stores it at passages/gen_{session_id} and answers with its id. It never
returns a bank READ passage: a failed gate or a passed deadline is an error, and the
Session Agent then uses its bank passage and flags FALLBACK_PASSAGE (PRD 4.5). A repeated
request for the same session returns the stored passage, so a retry after a reconnect
costs nothing. Errors use the SDD 11 shape.
"""

import logging
from typing import Annotated, Any

import aloai_contracts
from aloai_store import Store
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from .generator.pipeline import (
    DeadlineExceeded,
    GateFailed,
    Generator,
    Request,
    choose_listening,
)
from .grader.models import UpstreamErrors

log = logging.getLogger(__name__)
SCHEMA_VERSION = 1


def passage_id_for(session_id: str) -> str:
    return f"gen_{session_id}"


def router(generator: Generator, store: Store) -> APIRouter:
    routes = APIRouter()

    @routes.post("/v1/passages:generate")
    def generate(body: Annotated[Any, Body()]) -> JSONResponse:
        problem = _first_error(aloai_contracts.PASSAGE_GENERATE_REQUEST, body)
        if problem is not None:
            return _error(400, "INVALID_REQUEST", problem, retryable=False)
        request = Request.from_contract(body)
        path = f"passages/{passage_id_for(request.session_id)}"
        try:
            stored = store.get(path)
            if stored is not None:
                return _response(stored)
            listening = choose_listening(
                store.where("passages", "mode", "LISTEN"),
                request.target_arl,
                request.length_profile,
            )
            generated = generator.generate(request, passage_id_for(request.session_id), listening)
        except GateFailed as error:
            log.info("gate failed for %s after %d attempts", path, error.attempts)
            return _error(422, "GATE_FAILED", str(error), retryable=False)
        except DeadlineExceeded as error:
            return _error(504, "DEADLINE", str(error), retryable=False)
        except LookupError as error:
            return _error(503, "NO_LISTENING_PASSAGE", str(error), retryable=False)
        except UpstreamErrors as error:
            return _error(503, "UPSTREAM_UNAVAILABLE", type(error).__name__, retryable=True)
        problem = _first_error(aloai_contracts.PASSAGE, generated.passage)
        if problem is not None:  # a bug in the generator, not the story: never store it
            log.error("generated passage %s breaks the passage schema: %s", path, problem)
            return _error(500, "INVALID_PASSAGE", problem, retryable=False)
        if not store.create(path, generated.passage):
            return _response(store.get(path))  # a repeated request got there first
        return _response(generated.passage)

    return routes


def _response(passage: dict) -> JSONResponse:
    body = {
        "schema_version": SCHEMA_VERSION,
        "passage_id": passage["passage_id"],
        "listening_passage_id": passage["paired_listening_passage_id"],
        "attempts": passage["generation"]["attempts"],
        "estimated_arl": passage["generation"]["estimated_arl"],
    }
    return JSONResponse(body)


def _first_error(validator, body: Any) -> str | None:
    error = next(iter(validator.iter_errors(body)), None)
    return None if error is None else error.message


def _error(status: int, code: str, message: str, *, retryable: bool) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        status_code=status,
    )
