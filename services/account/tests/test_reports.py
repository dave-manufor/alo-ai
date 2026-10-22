import json
from pathlib import Path

from aloai_store import MemoryStore
from services.account.tests.support import GUARDIAN, bearer, make_client

OTHER = "guardian_other_002"
FIXTURE = (
    Path(__file__).resolve().parents[3] / "fixtures/contracts/reading_report.sess_demo_001.json"
)
REPORT = json.loads(FIXTURE.read_text())


def report(session_id: str, when: str, guardian: str = GUARDIAN) -> dict:
    return REPORT | {"session_id": session_id, "guardian_id": guardian, "timestamp_iso": when}


def with_reports(*reports: dict):
    store = MemoryStore()
    for each in reports:
        store.set(f"reports/{each['session_id']}", each)
    client, store = make_client(store=store)
    return client, store


def audited(store, action: str) -> list[dict]:
    return store.where("audit_log", "action", action)


def test_the_guardian_sees_their_reports_newest_first():
    older = report("sess_a", "2026-01-10T09:00:00Z")
    newer = report("sess_b", "2026-01-12T09:00:00Z")
    client, _store = with_reports(older, newer)
    response = client.get("/v1/reports", headers=bearer())
    assert response.status_code == 200
    assert response.json() == {"reports": [newer, older]}


def test_another_guardians_reports_are_never_listed():
    mine = report("sess_a", "2026-01-10T09:00:00Z")
    theirs = report("sess_b", "2026-01-12T09:00:00Z", guardian=OTHER)
    client, _store = with_reports(mine, theirs)
    assert client.get("/v1/reports", headers=bearer()).json() == {"reports": [mine]}
    assert client.get("/v1/reports", headers=bearer(oid=OTHER)).json() == {"reports": [theirs]}


def test_no_reports_yet_is_an_empty_list():
    client, _store = with_reports()
    assert client.get("/v1/reports", headers=bearer()).json() == {"reports": []}


def test_one_report_comes_back_as_stored():
    stored = report("sess_a", "2026-01-10T09:00:00Z")
    client, _store = with_reports(stored)
    response = client.get("/v1/reports/sess_a", headers=bearer())
    assert response.status_code == 200
    assert response.json() == stored


def test_someone_elses_report_looks_like_one_that_does_not_exist():
    theirs = report("sess_b", "2026-01-12T09:00:00Z", guardian=OTHER)
    client, store = with_reports(theirs)
    refused = client.get("/v1/reports/sess_b", headers=bearer())
    missing = client.get("/v1/reports/sess_missing", headers=bearer())
    assert (refused.status_code, missing.status_code) == (404, 404)
    assert refused.json() == missing.json()
    assert refused.json()["error"]["code"] == "NOT_FOUND"
    assert audited(store, "report.read") == []


def test_an_id_that_is_not_an_id_is_a_404():
    client, _store = with_reports()
    for bad in ("sess%20a", "a" * 65, "..%2Fchildren"):
        assert client.get(f"/v1/reports/{bad}", headers=bearer()).status_code == 404


def test_reads_are_audited_without_the_report_in_the_log():
    stored = report("sess_a", "2026-01-10T09:00:00Z")
    client, store = with_reports(stored)
    client.get("/v1/reports", headers=bearer())
    client.get("/v1/reports/sess_a", headers=bearer())
    listed, read = audited(store, "report.list"), audited(store, "report.read")
    assert (len(listed), len(read)) == (1, 1)
    for entry in (*listed, *read):
        assert entry["principal_id"] == GUARDIAN
        assert set(entry) >= {"args_sha256", "at", "allowed"}
        assert "fluency" not in json.dumps(entry)


def test_sign_in_is_needed():
    client, _store = with_reports(report("sess_a", "2026-01-10T09:00:00Z"))
    assert client.get("/v1/reports").status_code == 401
    assert client.get("/v1/reports/sess_a").status_code == 401
