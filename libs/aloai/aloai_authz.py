"""Agent tool authorization (PRD 12.1, SDD 8).

Every agent tool call passes through authorize() before the tool runs. The run
context is built by the server from the verified token and the trigger, never by
the model; the model supplies only business arguments, and each one that names a
session, a child or a class must match the context. Tools that change a score, consent
or a payment are refused for every agent. Every call is written to the audit log with
audit_entry().

The Story Writer and Critic have no tools: the generator's code gate runs the checks
(PRD 3.1). The Teacher Assistant's proposals need the teacher's single-use confirmation
token (PRD 12.1), which comes with that agent, so they are refused until then.
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
    needs_confirmation: frozenset[str] = frozenset()


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
    "story_writer": AgentPolicy(tool_limits={}),
    "story_critic": AgentPolicy(tool_limits={}),
    "grading_panel": AgentPolicy(
        tool_limits={"get_rubric": 20, "get_transcript": 20, "queue_human_review": 5}
    ),
    "teacher_assistant": AgentPolicy(
        tool_limits={
            "query_class": 20,
            "get_child_reports": 20,
            "get_profiles": 20,
            "propose_groups": 5,
            "propose_assignment": 5,
        },
        needs_confirmation=frozenset({"propose_groups", "propose_assignment"}),
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
    class_ids: frozenset[str] = frozenset()


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
    if tool in policy.needs_confirmation:
        return Decision(False, f"{tool} needs the teacher's confirmation token")
    if policy.requires_consent and not ctx.consent_on_file:
        return Decision(False, "no consent is on file for this child")
    for name in SCOPED_ARGUMENTS:
        if name in args and args[name] != getattr(ctx, name):
            return Decision(False, f"{name} is outside this run")
    if "class_id" in args and args["class_id"] not in ctx.class_ids:
        return Decision(False, "class_id is outside the teacher's classes")
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
