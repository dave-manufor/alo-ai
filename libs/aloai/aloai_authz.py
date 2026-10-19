"""Agent tool authorization (PRD 12.1, SDD 8).

Every agent tool call passes through authorize() before the tool runs. The run
context is built by the server from the verified token and the trigger, never by
the model; the model supplies only business arguments, and each one that names a
session or a child must match the context. Tools that change a score, consent or
a payment are refused for every agent. Every call is written to the audit log with
audit_entry().
"""

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

FORBIDDEN_TOOLS = frozenset(
    {
        "write_score",
        "write_report",
        "write_level",
        "write_profile",
        "change_consent",
        "delete_child",
        "charge_payment",
        "refund_payment",
        "change_subscription",
        "run_sql",
    }
)


@dataclass(frozen=True)
class AgentPolicy:
    """tool_limits: the most calls of each tool in one run (None: no limit of its own)."""

    tool_limits: Mapping[str, int | None]
    run_limit: int | None = None
    requires_consent: bool = False


POLICIES: Mapping[str, AgentPolicy] = {
    "session_conductor": AgentPolicy(
        tool_limits=dict.fromkeys(
            [
                "end_turn",
                "request_repeat",
                "pause_session",
                "move_on",
                "end_kindly",
                "switch_to_clips",
            ]
        ),
        run_limit=50,
    ),
    "reading_coach": AgentPolicy(
        tool_limits={
            "get_report": 20,
            "get_history": 20,
            "get_activity_library": 20,
            "search_books": 20,
            "queue_story": 2,
            "save_plan": 2,
            "schedule_session": 1,
            "send_parent_email": 1,
        },
        requires_consent=True,
    ),
}

SCOPED_ARGUMENTS = ("session_id", "child_id")


@dataclass(frozen=True)
class RunContext:
    agent: str
    principal_id: str
    session_id: str | None = None
    child_id: str | None = None
    consent_on_file: bool = False


@dataclass
class RunState:
    """Allowed calls so far in this run, counted by authorize()."""

    calls: Counter = field(default_factory=Counter)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def authorize(ctx: RunContext, tool: str, args: Mapping[str, Any], state: RunState) -> Decision:
    """Allow or refuse one tool call, and count it in state when allowed."""
    policy = POLICIES.get(ctx.agent)
    if tool in FORBIDDEN_TOOLS:
        return Decision(False, f"{tool} is forbidden for every agent")
    if policy is None:
        return Decision(False, f"unknown agent {ctx.agent}")
    if tool not in policy.tool_limits:
        return Decision(False, f"{tool} is not allowed for {ctx.agent}")
    if policy.requires_consent and not ctx.consent_on_file:
        return Decision(False, "no consent is on file for this child")
    for name in SCOPED_ARGUMENTS:
        if name in args and args[name] != getattr(ctx, name):
            return Decision(False, f"{name} is outside this run")
    limit = policy.tool_limits[tool]
    if limit is not None and state.calls[tool] >= limit:
        return Decision(False, f"{tool} reached its limit of {limit} calls in a run")
    if policy.run_limit is not None and state.calls.total() >= policy.run_limit:
        return Decision(False, f"{ctx.agent} reached its limit of {policy.run_limit} calls")
    state.calls[tool] += 1
    return Decision(True, "allowed")


def audit_entry(
    ctx: RunContext,
    tool: str,
    args: Mapping[str, Any],
    decision: Decision,
    *,
    result_size: int | None,
    at: str,
) -> dict:
    """One audit_log document. The arguments are stored only as a hash."""
    canonical = json.dumps(args, sort_keys=True, default=str).encode()
    return {
        "agent": ctx.agent,
        "principal_id": ctx.principal_id,
        "tool": tool,
        "args_sha256": hashlib.sha256(canonical).hexdigest(),
        "allowed": decision.allowed,
        "reason": decision.reason,
        "result_size": result_size,
        "at": at,
    }
