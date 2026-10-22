"""A guardian's two-week plan (PRD 8, 10.4, 12). The Coach writes plans/plan_{session_id} with
the guardian's id on it; this service only reads it, and only for that guardian, and trims it
to what the plan screen shows (schemas/guardian_plan.schema.json): no guardian id, no audio
path, no internal flags. The books are looked up by id; a missing one, or one held for
review, is left out. Someone else's plan looks exactly like one that does not exist (404).
No entitlement check yet: Paystack is later work, so every consented guardian sees the plan.
It makes no number. Every read writes an audit_log entry."""

import re
from collections.abc import Callable
from typing import Annotated, Any

from aloai_store import Store
from fastapi import APIRouter, Depends

from .access import Clock, NewId, audit, not_found, utc_now
from .auth import Principal
from .children import default_id

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
SCHEMA_VERSION = 1
# A book is shown with its licence and the attribution its licence requires (PRD 9.1).
BOOK_FIELDS = ("book_id", "title", "author", "licence", "attribution", "arl")


def router(
    store: Store,
    guardian: Callable[..., Principal],
    now: Clock = utc_now,
    new_id: NewId = default_id,
) -> APIRouter:
    routes = APIRouter()
    current = Depends(guardian)

    @routes.get("/v1/plans/{session_id}")
    def get_plan(session_id: str, principal: Annotated[Principal, current]) -> dict[str, Any]:
        if not _ID.fullmatch(session_id):
            raise not_found()
        plan = store.get(f"plans/plan_{session_id}")
        if plan is None or plan.get("guardian_id") != principal.guardian_id:
            raise not_found()
        found = store.get_many([f"books/{book_id}" for book_id in plan["book_ids"]])
        books = [
            {key: book[key] for key in BOOK_FIELDS}
            for book in found
            if book is not None and not book.get("held_for_review")
        ]
        audit(store, principal, "plan.read", {"session_id": session_id}, now, new_id)
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan["plan_id"],
            "session_id": plan["session_id"],
            "child_id": plan["child_id"],
            "activities": plan["activities"],
            "books": books,
            "next_session_at": plan["next_session_at"],
        }

    return routes
