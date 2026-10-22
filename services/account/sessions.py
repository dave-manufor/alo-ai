"""POST /v1/sessions (PRD 4.4, SDD 11): the one way a child's session starts. The guardian must
own the child and have consented for them; then the service makes the LiveKit room (its
metadata is what the Session Agent is dispatched with) and hands the browser a join token.
There is no entitlement check yet: Paystack is later work, so the mini-study is open to every
consented child. The browser chooses nothing but the child and, optionally, home or school;
VOICE_MODE and SESSION_PROFILE are server settings."""

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any, Literal

from aloai_contracts import SESSION_ROOM_METADATA, SESSION_START_RESPONSE
from aloai_store import Store
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from .access import Clock, NewId, audit, owned_child, utc_now
from .auth import Principal
from .children import default_id
from .errors import AccountError
from .rooms import Rooms

log = logging.getLogger("aloai.account.sessions")


class NewSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_id: str = Field(min_length=1, max_length=64)
    context: Literal["HOME", "SCHOOL"] = "HOME"


def unavailable() -> AccountError:
    return AccountError(
        503, "SESSION_UNAVAILABLE", "We could not start the session. Please try again.",
        retryable=True,
    )  # fmt: skip


def router(
    store: Store,
    guardian: Callable[..., Principal],
    rooms: Rooms | None,
    now: Clock = utc_now,
    new_id: NewId = default_id,
) -> APIRouter:
    routes = APIRouter()
    current = Depends(guardian)

    @routes.post("/v1/sessions", status_code=201)
    def start_session(body: NewSession, principal: Annotated[Principal, current]) -> dict[str, Any]:
        owned_child(store, principal, body.child_id)
        consents = store.where("consents", "child_id", body.child_id)
        if not any(c["guardian_id"] == principal.guardian_id for c in consents):
            raise AccountError(
                403, "CONSENT_REQUIRED", "Consent is needed before a session can start.",
                retryable=False,
            )  # fmt: skip
        if rooms is None:
            raise unavailable()
        session_id = new_id("sess")
        metadata = {
            "session_id": session_id,
            "child_id": body.child_id,
            "context": body.context,
            "capture_mode": "LIVE",
        }
        SESSION_ROOM_METADATA.validate(metadata)
        try:
            rooms.open(session_id, json.dumps(metadata))
            token = rooms.token(session_id, f"guardian:{principal.guardian_id}")
        except Exception as error:
            # The class only: a LiveKit error can echo the request, which carries a child id.
            log.error("could not open the session room: %s", type(error).__name__)
            raise unavailable() from None
        audit(
            store, principal, "session.start",
            {"child_id": body.child_id, "session_id": session_id}, now, new_id,
        )  # fmt: skip
        reply = {"session_id": session_id, "livekit_url": rooms.url, "token": token}
        SESSION_START_RESPONSE.validate(reply)
        return reply

    return routes
