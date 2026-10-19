"""Agent tool authorization (PRD 12.1, SDD 8).

Every agent tool call passes through authorize() before the tool runs. The run
context is built by the server from the verified token and the trigger, never by
the model; the model supplies only business arguments, and each one that names a
session or a child must match the context. Tools that change a score, consent or
a payment are refused for every agent.
"""

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
    tools: frozenset[str]
    run_limit: int


POLICIES: Mapping[str, AgentPolicy] = {
    "session_conductor": AgentPolicy(
        tools=frozenset(
            {
                "end_turn",
                "request_repeat",
                "pause_session",
                "move_on",
                "end_kindly",
                "switch_to_clips",
            }
        ),
        run_limit=50,
    ),
}

SCOPED_ARGUMENTS = ("session_id", "child_id")


@dataclass(frozen=True)
class RunContext:
    agent: str
    principal_id: str
    session_id: str | None = None
    child_id: str | None = None


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
    if tool not in policy.tools:
        return Decision(False, f"{tool} is not allowed for {ctx.agent}")
    for name in SCOPED_ARGUMENTS:
        if name in args and args[name] != getattr(ctx, name):
            return Decision(False, f"{name} is outside this run")
    if state.calls.total() >= policy.run_limit:
        return Decision(False, f"{ctx.agent} reached its limit of {policy.run_limit} calls")
    state.calls[tool] += 1
    return Decision(True, "allowed")
