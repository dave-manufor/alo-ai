import json
import logging
from pathlib import Path

import pytest
from aloai_contracts import (
    SESSION_ROOM_METADATA,
    SESSION_START_REQUEST,
    SESSION_START_RESPONSE,
    SESSION_STATUS,
)
from services.account.tests.support import GUARDIAN, bearer, make_client
from services.account.tests.test_children import OTHER, add_child

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/contracts"


class FakeRooms:
    url = "wss://livekit.example.test"

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.opened: list[tuple[str, dict]] = []
        self.tokens: list[tuple[str, str]] = []

    def open(self, room: str, metadata: str) -> None:
        if self.fail_on == "open":
            raise RuntimeError("LiveKit said no for child_1")
        self.opened.append((room, json.loads(metadata)))

    def token(self, room: str, identity: str) -> str:
        if self.fail_on == "token":
            raise RuntimeError("no token")
        self.tokens.append((room, identity))
        return "room-token"


def started(rooms=None):
    """(client, store, rooms, child_id): a guardian with one consented child, ready to start."""
    rooms = FakeRooms() if rooms is None else rooms
    client, store = make_client(rooms=rooms)
    child_id = add_child(client).json()["child_id"]
    return client, store, rooms, child_id


def start(client, child_id, who=None, **body):
    return client.post(
        "/v1/sessions", json={"child_id": child_id} | body, headers=bearer(**(who or {}))
    )


def test_a_consented_childs_session_starts_with_a_room_and_a_token():
    client, store, rooms, child_id = started()
    response = start(client, child_id)
    assert response.status_code == 201
    reply = response.json()
    SESSION_START_RESPONSE.validate(reply)
    assert reply == {
        "session_id": "sess_5",
        "livekit_url": "wss://livekit.example.test",
        "token": "room-token",
    }
    assert rooms.tokens == [("sess_5", f"guardian:{GUARDIAN}")]


def test_the_room_carries_what_the_agent_needs_and_nothing_the_browser_chose():
    client, _store, rooms, child_id = started()
    start(client, child_id)
    room, metadata = rooms.opened[0]
    SESSION_ROOM_METADATA.validate(metadata)
    assert room == metadata["session_id"]
    assert metadata == {
        "session_id": "sess_5",
        "child_id": child_id,
        "context": "HOME",
        "capture_mode": "LIVE",
    }


def test_school_can_be_chosen_but_a_server_setting_cannot():
    client, _store, rooms, child_id = started()
    assert start(client, child_id, context="SCHOOL").status_code == 201
    assert rooms.opened[0][1]["context"] == "SCHOOL"
    for field in ({"context": "CAFE"}, {"voice_mode": "live_first"}, {"session_profile": "demo"}):
        refused = start(client, child_id, **field)
        assert refused.status_code == 400
        assert refused.json()["error"]["code"] == "INVALID_REQUEST"


def test_starting_a_session_is_audited_without_the_arguments_in_clear():
    client, store, _rooms, child_id = started()
    start(client, child_id)
    logged = [d for d in store.where("audit_log", "action", "session.start")]
    assert len(logged) == 1
    assert logged[0]["principal_id"] == GUARDIAN
    assert set(logged[0]) >= {"args_sha256", "at", "allowed"}
    assert child_id not in json.dumps(logged[0])


def test_another_guardians_child_looks_like_a_child_that_does_not_exist():
    client, _store, rooms, child_id = started()
    refused = start(client, child_id, who={"oid": OTHER})
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert start(client, "child_missing").status_code == 404
    assert rooms.opened == []


def test_no_consent_no_session():
    client, store, rooms, child_id = started()
    for path in store.list_paths("consents"):
        store.delete(path)
    refused = start(client, child_id)
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "CONSENT_REQUIRED")
    assert rooms.opened == []


def test_sign_in_is_needed():
    client, _store, _rooms, child_id = started()
    assert client.post("/v1/sessions", json={"child_id": child_id}).status_code == 401


def test_without_a_livekit_server_the_answer_is_a_retryable_503():
    client, _store = make_client()
    child_id = add_child(client).json()["child_id"]
    refused = start(client, child_id)
    assert refused.status_code == 503
    assert refused.json()["error"] == {
        "code": "SESSION_UNAVAILABLE",
        "message": "We could not start the session. Please try again.",
        "retryable": True,
    }


@pytest.mark.parametrize("fail_on", ["open", "token"])
def test_a_livekit_failure_is_a_503_that_logs_only_the_error_class(fail_on, caplog):
    client, store, _rooms, child_id = started(FakeRooms(fail_on))
    with caplog.at_level(logging.ERROR):
        refused = start(client, child_id)
    assert refused.status_code == 503
    assert refused.json()["error"]["code"] == "SESSION_UNAVAILABLE"
    assert "RuntimeError" in caplog.text
    assert "child_1" not in caplog.text
    assert store.where("audit_log", "action", "session.start") == []


def test_the_fixtures_are_the_shapes_the_schema_describes():
    for name, check in (
        ("request", SESSION_START_REQUEST),
        ("response", SESSION_START_RESPONSE),
        ("room_metadata", SESSION_ROOM_METADATA),
        ("status", SESSION_STATUS),
    ):
        check.validate(json.loads((FIXTURES / f"session_start.{name}.json").read_text()))
    assert not SESSION_START_REQUEST.is_valid({"child_id": "c", "voice_mode": "live_first"})


def status(client, session_id, who=None):
    return client.get(f"/v1/sessions/{session_id}", headers=bearer(**(who or {})))


def test_a_session_the_agent_has_not_written_yet_is_pending():
    client, _store, _rooms, child_id = started()
    session_id = start(client, child_id).json()["session_id"]
    reply = status(client, session_id).json()
    SESSION_STATUS.validate(reply)
    assert (reply["status"], reply["report_ready"], reply["plan_ready"]) == ("PENDING", False, False)


def test_the_status_follows_the_session_and_says_when_report_and_plan_exist():
    client, store, _rooms, child_id = started()
    session_id = start(client, child_id).json()["session_id"]
    store.set(f"sessions/{session_id}", {"child_id": child_id, "status": "STARTED"})
    assert status(client, session_id).json()["status"] == "STARTED"
    store.set(f"sessions/{session_id}", {"child_id": child_id, "status": "COMPLETE"})
    store.set(f"reports/{session_id}", {"session_id": session_id})
    reply = status(client, session_id).json()
    assert (reply["status"], reply["report_ready"], reply["plan_ready"]) == ("COMPLETE", True, False)
    store.set(f"plans/plan_{session_id}", {"session_id": session_id})
    assert status(client, session_id).json()["plan_ready"] is True


def test_someone_elses_session_and_an_unknown_one_look_the_same():
    client, _store, _rooms, child_id = started()
    session_id = start(client, child_id).json()["session_id"]
    refused = status(client, session_id, {"oid": OTHER})
    missing = status(client, "sess_missing")
    assert (refused.status_code, missing.status_code) == (404, 404)
    assert refused.json() == missing.json()
    assert status(client, "bad.id").status_code == 404


def test_reading_the_status_needs_a_sign_in_and_is_audited_without_the_id_in_clear():
    client, store, _rooms, child_id = started()
    session_id = start(client, child_id).json()["session_id"]
    assert client.get(f"/v1/sessions/{session_id}").status_code == 401
    status(client, session_id)
    logged = store.where("audit_log", "action", "session.read")
    assert len(logged) == 1
    assert session_id not in json.dumps(logged[0])
