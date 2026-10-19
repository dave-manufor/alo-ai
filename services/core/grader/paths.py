"""Firestore documents the Grader reads and writes (SDD 12)."""


def session(session_id: str) -> str:
    return f"sessions/{session_id}"


def turn(session_id: str, turn_id: str) -> str:
    return f"sessions/{session_id}/turns/{turn_id}"


def child(child_id: str) -> str:
    return f"children/{child_id}"


def passage(passage_id: str) -> str:
    return f"passages/{passage_id}"


def quick(session_id: str, turn_phase: str, index: int) -> str:
    return f"sessions/{session_id}/quick/{turn_phase}_{index}"


def quick_result(session_id: str) -> str:
    return f"sessions/{session_id}/quick/RESULT"


def grading(session_id: str) -> str:
    return f"sessions/{session_id}/grading/final"


def telemetry(session_id: str) -> str:
    return f"sessions/{session_id}/phase1/telemetry"


def report(session_id: str) -> str:
    return f"reports/{session_id}"
