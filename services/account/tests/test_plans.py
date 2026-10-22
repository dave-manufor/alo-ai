import json
from pathlib import Path

from aloai_contracts import GUARDIAN_PLAN, PLAN
from aloai_store import MemoryStore
from services.account.tests.support import GUARDIAN, bearer, make_client

OTHER = "guardian_other_002"
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/contracts"
PLAN_DOC = json.loads((FIXTURES / "plan.sess_demo_001.json").read_text())
BOOK_DOC = json.loads((FIXTURES / "book.sample.json").read_text())
EXPECTED = json.loads((FIXTURES / "guardian_plan.sess_demo_001.json").read_text())


def book(book_id: str, **changes) -> dict:
    return BOOK_DOC | {"book_id": book_id} | changes


def with_plan(plan: dict = PLAN_DOC, books: tuple[dict, ...] = (book("book_demo_001"),)):
    store = MemoryStore()
    store.set(f"plans/{plan['plan_id']}", plan)
    for each in books:
        store.set(f"books/{each['book_id']}", each)
    client, store = make_client(store=store)
    return client, store


def test_the_stored_plan_fixture_is_a_plan():
    PLAN.validate(PLAN_DOC)
    GUARDIAN_PLAN.validate(EXPECTED)


def test_the_guardian_gets_the_plan_trimmed_to_what_the_screen_shows():
    client, _store = with_plan()
    response = client.get("/v1/plans/sess_demo_001", headers=bearer())
    assert response.status_code == 200
    reply = response.json()
    GUARDIAN_PLAN.validate(reply)
    assert reply == EXPECTED
    for left_out in ("guardian_id", "summary_audio_uri", "template_used", "activity_library"):
        assert left_out not in reply
    assert "gs://" not in json.dumps(reply)


def test_a_missing_book_or_one_held_for_review_is_left_out():
    plan = PLAN_DOC | {"book_ids": ["book_demo_001", "book_gone", "book_held"]}
    client, _store = with_plan(
        plan, (book("book_demo_001"), book("book_held", held_for_review=True))
    )
    reply = client.get("/v1/plans/sess_demo_001", headers=bearer()).json()
    assert [b["book_id"] for b in reply["books"]] == ["book_demo_001"]
    GUARDIAN_PLAN.validate(reply)


def test_someone_elses_plan_looks_like_one_that_does_not_exist():
    client, store = with_plan(PLAN_DOC | {"guardian_id": OTHER})
    refused = client.get("/v1/plans/sess_demo_001", headers=bearer())
    missing = client.get("/v1/plans/sess_missing", headers=bearer())
    assert (refused.status_code, missing.status_code) == (404, 404)
    assert refused.json() == missing.json()
    assert refused.json()["error"]["code"] == "NOT_FOUND"
    assert store.where("audit_log", "action", "plan.read") == []


def test_an_id_that_is_not_an_id_is_a_404():
    client, _store = with_plan()
    for bad in ("sess%20a", "a" * 65, "..%2Fchildren"):
        assert client.get(f"/v1/plans/{bad}", headers=bearer()).status_code == 404


def test_a_read_is_audited_without_the_plan_in_the_log():
    client, store = with_plan()
    client.get("/v1/plans/sess_demo_001", headers=bearer())
    (entry,) = store.where("audit_log", "action", "plan.read")
    assert entry["principal_id"] == GUARDIAN
    assert set(entry) >= {"args_sha256", "at", "allowed"}
    assert "Sound hunt" not in json.dumps(entry)


def test_sign_in_is_needed():
    client, _store = with_plan()
    assert client.get("/v1/plans/sess_demo_001").status_code == 401
