"""Tests for aloai_authz (PRD 12.1). The library must stay at 100% line coverage."""

import pytest
from aloai_authz import (
    FORBIDDEN_TOOLS,
    POLICIES,
    Decision,
    RunContext,
    RunState,
    audit_entry,
    authorize,
)

CONDUCTOR_TOOLS = [
    "end_turn",
    "request_repeat",
    "pause_session",
    "move_on",
    "end_kindly",
    "switch_to_clips",
]
COACH_LIMITS = {
    "get_report": 20,
    "get_history": 20,
    "get_activity_library": 20,
    "search_books": 20,
    "queue_story": 2,
    "save_plan": 2,
    "schedule_session": 1,
    "send_parent_email": 1,
}


def conductor(session_id="sess_demo_001"):
    return RunContext(
        agent="session_conductor",
        principal_id="guardian_demo_001",
        session_id=session_id,
        child_id="child_demo_001",
    )


def coach(consent=True):
    return RunContext(
        agent="reading_coach",
        principal_id="guardian_demo_001",
        session_id="sess_demo_001",
        child_id="child_demo_001",
        consent_on_file=consent,
    )


@pytest.mark.parametrize("tool", CONDUCTOR_TOOLS)
def test_the_conductor_may_call_its_six_tools(tool):
    state = RunState()
    decision = authorize(conductor(), tool, {}, state)
    assert decision.allowed
    assert state.calls[tool] == 1


@pytest.mark.parametrize("agent", [*POLICIES, "unknown"])
@pytest.mark.parametrize("tool", sorted(FORBIDDEN_TOOLS))
def test_every_agent_is_refused_every_forbidden_tool(agent, tool):
    ctx = RunContext(agent=agent, principal_id="guardian_demo_001", consent_on_file=True)
    decision = authorize(ctx, tool, {}, RunState())
    assert not decision.allowed
    assert "forbidden" in decision.reason


def test_tools_outside_the_allowlist_are_refused():
    assert not authorize(conductor(), "send_parent_email", {}, RunState()).allowed
    assert not authorize(coach(), "end_turn", {}, RunState()).allowed


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


@pytest.mark.parametrize("tool, limit", sorted(COACH_LIMITS.items()))
def test_each_coach_tool_has_its_own_limit_per_run(tool, limit):
    state = RunState()
    decisions = [authorize(coach(), tool, {}, state) for _ in range(limit + 1)]
    assert all(d.allowed for d in decisions[:limit])
    assert decisions[limit] == Decision(
        False, f"{tool} reached its limit of {limit} calls in a run"
    )


def test_the_coach_emails_a_parent_once_per_run():
    state = RunState()
    assert authorize(coach(), "send_parent_email", {"child_id": "child_demo_001"}, state).allowed
    assert not authorize(
        coach(), "send_parent_email", {"child_id": "child_demo_001"}, state
    ).allowed


def test_the_coach_reads_nothing_without_consent_on_file():
    decision = authorize(coach(consent=False), "get_report", {}, RunState())
    assert decision == Decision(False, "no consent is on file for this child")


def test_the_coach_cannot_read_another_childs_history():
    assert not authorize(coach(), "get_history", {"child_id": "child_other"}, RunState()).allowed


def test_an_audit_entry_keeps_a_hash_of_the_arguments_not_the_arguments():
    args = {"child_id": "child_demo_001", "summary": "Ada read well."}
    entry = audit_entry(
        coach(),
        "save_plan",
        args,
        Decision(True, "allowed"),
        result_size=42,
        at="2026-01-15T09:09:20Z",
    )
    assert entry == {
        "agent": "reading_coach",
        "principal_id": "guardian_demo_001",
        "tool": "save_plan",
        "args_sha256": entry["args_sha256"],
        "allowed": True,
        "reason": "allowed",
        "result_size": 42,
        "at": "2026-01-15T09:09:20Z",
    }
    assert len(entry["args_sha256"]) == 64
    assert "Ada read well." not in str(entry)


def test_the_same_arguments_in_any_order_hash_the_same():
    decision = Decision(False, "refused")
    first = audit_entry(coach(), "get_report", {"a": 1, "b": 2}, decision, result_size=None, at="t")
    second = audit_entry(
        coach(), "get_report", {"b": 2, "a": 1}, decision, result_size=None, at="t"
    )
    assert first["args_sha256"] == second["args_sha256"]
