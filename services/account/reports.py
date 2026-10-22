"""A guardian's reading reports (PRD 10.4, 12; SDD 13). The Grader writes reports/{session_id}
with the guardian's id on it, and the Coach adds its text; this service only reads them, and
only for the guardian they belong to. A report that is someone else's looks exactly like one
that does not exist (404). It makes no number and changes none: the report is returned as
stored. Every read writes an audit_log entry (the report itself is never put in the log)."""

import re
from collections.abc import Callable
from typing import Annotated, Any

from aloai_store import Store
from fastapi import APIRouter, Depends

from .access import Clock, NewId, audit, not_found, utc_now
from .auth import Principal
from .children import default_id

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def router(
    store: Store,
    guardian: Callable[..., Principal],
    now: Clock = utc_now,
    new_id: NewId = default_id,
) -> APIRouter:
    routes = APIRouter()
    current = Depends(guardian)

    @routes.get("/v1/reports")
    def list_reports(principal: Annotated[Principal, current]) -> dict[str, Any]:
        mine = store.where("reports", "guardian_id", principal.guardian_id)
        newest_first = sorted(mine, key=lambda report: report["timestamp_iso"], reverse=True)
        audit(store, principal, "report.list", {}, now, new_id)
        return {"reports": newest_first}

    @routes.get("/v1/reports/{session_id}")
    def get_report(session_id: str, principal: Annotated[Principal, current]) -> dict[str, Any]:
        if not _ID.fullmatch(session_id):
            raise not_found()
        report = store.get(f"reports/{session_id}")
        if report is None or report.get("guardian_id") != principal.guardian_id:
            raise not_found()
        audit(store, principal, "report.read", {"session_id": session_id}, now, new_id)
        return report

    return routes
