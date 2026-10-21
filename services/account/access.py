"""Who may touch which child. A guardian sees only their own children, and a child that is
someone else's looks exactly like a child that does not exist (404), so nothing leaks.
aloai_authz covers agent tool calls and has no guardian principal, so this is a plain check."""

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from aloai_contracts import GUARDIAN
from aloai_store import Store

from .auth import Principal
from .errors import AccountError

Clock = Callable[[], datetime]
NewId = Callable[[str], str]

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def utc_now() -> datetime:
    return datetime.now(UTC)


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def not_found() -> AccountError:
    return AccountError(404, "NOT_FOUND", "We could not find that.")


def owned_child(store: Store, principal: Principal, child_id: str) -> dict:
    """The child document, if this guardian owns it; 404 otherwise."""
    if not _ID.fullmatch(child_id):
        raise not_found()
    child = store.get(f"children/{child_id}")
    if child is None or child.get("guardian_id") != principal.guardian_id:
        raise not_found()
    return child


def ensure_guardian(store: Store, principal: Principal, now: Clock) -> dict:
    """guardians/{guardian_id}, made the first time this guardian calls."""
    path = f"guardians/{principal.guardian_id}"
    existing = store.get(path)
    if existing is not None:
        return existing
    if principal.email is None:
        raise AccountError(
            400, "EMAIL_MISSING", "Your sign-in did not share an email address.", retryable=False
        )
    document = {
        "schema_version": 1,
        "guardian_id": principal.guardian_id,
        "email": principal.email,
        "sign_in_method": principal.sign_in_method,
        "created_at": stamp(now()),
    }
    GUARDIAN.validate(document)
    store.create(path, document)
    return store.get(path) or document


def audit(
    store: Store,
    principal: Principal,
    action: str,
    args: Mapping[str, Any],
    now: Clock,
    new_id: NewId,
) -> None:
    """One audit_log document (SDD 13). The arguments are stored only as a hash."""
    canonical = json.dumps(args, sort_keys=True, default=str).encode()
    store.set(
        f"audit_log/{new_id('audit')}",
        {
            "actor": "account",
            "principal_id": principal.guardian_id,
            "action": action,
            "args_sha256": hashlib.sha256(canonical).hexdigest(),
            "allowed": True,
            "at": stamp(now()),
        },
    )
