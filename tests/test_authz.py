"""Tests for aloai_authz (PRD 12.1). The library must stay at 100% line coverage."""

import pytest
from aloai_authz import FORBIDDEN_TOOLS, POLICIES, RunContext, RunState, authorize

CONDUCTOR_TOOLS = [
    "end_turn",
    "request_repeat",
    "pause_session",
    "move_on",
    "end_kindly",
    "switch_to_clips",
]


def conductor(session_id="sess_demo_001"):
    return RunContext(
        agent="session_conductor",
        principal_id="guardian_demo_001",
        session_id=session_id,
        child_id="child_demo_001",
    )


@pytest.mark.parametrize("tool", CONDUCTOR_TOOLS)
def test_the_conductor_may_call_its_six_tools(tool):
    state = RunState()
    decision = authorize(conductor(), tool, {}, state)
    assert decision.allowed
    assert state.calls[tool] == 1


@pytest.mark.parametrize("agent", [*POLICIES, "reading_coach", "unknown"])
@pytest.mark.parametrize("tool", sorted(FORBIDDEN_TOOLS))
def test_every_agent_is_refused_every_forbidden_tool(agent, tool):
    ctx = RunContext(agent=agent, principal_id="guardian_demo_001")
    decision = authorize(ctx, tool, {}, RunState())
    assert not decision.allowed
    assert "forbidden" in decision.reason


def test_tools_outside_the_allowlist_are_refused():
    decision = authorize(conductor(), "send_parent_email", {}, RunState())
    assert not decision.allowed


def test_an_unknown_agent_is_refused():
    ctx = RunContext(agent="teacher_assistant", principal_id="teacher_demo_001")
    assert not authorize(ctx, "end_turn", {}, RunState()).allowed


@pytest.mark.parametrize("name", ["session_id", "child_id"])
def test_arguments_must_stay_within_the_run(name):
    decision = authorize(conductor(), "end_turn", {name: "someone_else"}, RunState())
    assert not decision.allowed
    assert name in decision.reason


def test_arguments_that_match_the_run_are_allowed():
    args = {"session_id": "sess_demo_001", "reason": "ANSWERED"}
    assert authorize(conductor(), "end_turn", args, RunState()).allowed


def test_the_conductor_stops_at_50_calls_in_a_run():
    state = RunState()
    decisions = [authorize(conductor(), "end_turn", {}, state) for _ in range(51)]
    assert all(d.allowed for d in decisions[:50])
    assert not decisions[50].allowed
    assert state.calls.total() == 50


def test_refused_calls_are_not_counted():
    state = RunState()
    authorize(conductor(), "write_score", {}, state)
    authorize(conductor(), "end_turn", {"session_id": "other"}, state)
    assert state.calls.total() == 0
