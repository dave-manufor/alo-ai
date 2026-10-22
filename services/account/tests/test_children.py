import re
from pathlib import Path

import pytest
from aloai_contracts import CHILD, CONSENT
from aloai_contracts import GUARDIAN as GUARDIAN_SCHEMA
from services.account.consent import CONSENT_TEXT, CONSENT_VERSION
from services.account.tests.support import GUARDIAN, NOW, bearer, make_client

OTHER = "guardian_other_002"
BODY = {
    "first_name": "Demo",
    "primary_class": 3,
    "birth_year": 2018,
    "attested": True,
    "training_opt_in": False,
}
WEB_STORE = Path(__file__).resolve().parents[3] / "apps/web/src/account/store.ts"


def add_child(client, who=None, **changes):
    return client.post("/v1/children", json=BODY | changes, headers=bearer(**(who or {})))


def test_the_consent_text_is_the_one_the_web_app_shows():
    source = WEB_STORE.read_text()
    version = re.search(r"CONSENT_VERSION = '([^']+)'", source).group(1)
    pieces = re.search(r"CONSENT_TEXT =\s*'([^']+)'", source).group(1)
    assert (version, pieces) == (CONSENT_VERSION, CONSENT_TEXT)


def test_me_makes_the_guardian_once_and_keeps_the_first_record():
    client, store = make_client()
    first = client.get("/v1/me", headers=bearer())
    assert first.status_code == 200
    GUARDIAN_SCHEMA.validate(first.json())
    assert first.json()["guardian_id"] == GUARDIAN
    assert first.json()["created_at"] == "2026-01-15T09:00:00Z"
    again = client.get("/v1/me", headers=bearer(email="changed@example.com"))
    assert again.json() == first.json()
    assert list(store.docs) == [f"guardians/{GUARDIAN}"]


def test_me_refuses_a_new_guardian_whose_token_has_no_email():
    client, store = make_client()
    response = client.get("/v1/me", headers=bearer(email=None))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMAIL_MISSING"
    assert store.docs == {}


def test_adding_a_child_records_the_child_and_its_consent_together():
    client, store = make_client()
    response = add_child(client)
    assert response.status_code == 201
    body = response.json()
    child_id = body["child_id"]
    CHILD.validate(body["child"])
    CONSENT.validate(body["consent"])
    assert body["child"]["guardian_id"] == GUARDIAN
    assert body["child"]["class_confirmed_year"] == 2026
    consent = body["consent"]
    assert (consent["guardian_id"], consent["child_id"]) == (GUARDIAN, child_id)
    assert consent["text_version"] == CONSENT_VERSION
    assert consent["verified_email"] == "guardian@example.com"
    assert consent["sign_in_method"] == "email_code"
    assert consent["attestation"].startswith("I am the parent or guardian of Demo, aged 8. ")
    assert consent["attestation"].endswith(CONSENT_TEXT)
    assert store.docs[f"children/{child_id}"] == body["child"]
    assert store.docs[f"consents/{consent['consent_id']}"] == consent
    assert f"guardians/{GUARDIAN}" in store.docs


def test_adding_a_child_and_a_consent_each_write_an_audit_entry_without_the_arguments():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    entries = [d for p, d in store.docs.items() if p.startswith("audit_log/")]
    assert sorted(e["action"] for e in entries) == ["child.create", "consent.create"]
    for entry in entries:
        assert entry["principal_id"] == GUARDIAN
        assert re.fullmatch(r"[0-9a-f]{64}", entry["args_sha256"])
        assert child_id not in str(entry)
        assert entry["at"] == "2026-01-15T09:00:00Z"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"attested": False}, "CONSENT_REQUIRED"),
        ({"primary_class": 7}, "INVALID_REQUEST"),
        ({"primary_class": 0}, "INVALID_REQUEST"),
        ({"first_name": ""}, "INVALID_REQUEST"),
        ({"first_name": "   "}, "INVALID_REQUEST"),
        ({"first_name": "x" * 41}, "INVALID_REQUEST"),
        ({"birth_year": 1990}, "INVALID_REQUEST"),
        ({"attested": "yes please"}, "INVALID_REQUEST"),
        ({"guardian_id": "someone_else"}, "INVALID_REQUEST"),
    ],
)
def test_a_child_is_not_saved_without_consent_or_with_bad_details(changes, code):
    client, store = make_client()
    response = add_child(client, **changes)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert not [p for p in store.docs if p.startswith(("children/", "consents/"))]


def test_a_missing_field_is_named_in_the_error():
    client, _ = make_client()
    body = {k: v for k, v in BODY.items() if k != "birth_year"}
    response = client.post("/v1/children", json=body, headers=bearer())
    assert response.status_code == 400
    assert response.json()["error"]["message"].startswith("birth_year")


def test_the_first_name_is_trimmed():
    client, _ = make_client()
    assert add_child(client, first_name="  Demo ").json()["child"]["first_name"] == "Demo"


def test_a_guardian_lists_only_their_own_children():
    client, _ = make_client()
    mine = add_child(client).json()["child_id"]
    theirs = add_child(client, {"oid": OTHER}, first_name="Other").json()["child_id"]
    listed = client.get("/v1/children", headers=bearer()).json()["children"]
    assert [c["child_id"] for c in listed] == [mine]
    assert listed[0]["first_name"] == "Demo"
    others = client.get("/v1/children", headers=bearer(oid=OTHER)).json()["children"]
    assert [c["child_id"] for c in others] == [theirs]
    assert client.get("/v1/children", headers=bearer(oid="nobody")).json() == {"children": []}


def test_a_guardian_reads_their_own_child_and_its_latest_consent():
    client, _ = make_client()
    child_id = add_child(client).json()["child_id"]
    child = client.get(f"/v1/children/{child_id}", headers=bearer())
    assert child.status_code == 200
    assert child.json()["child_id"] == child_id
    consent = client.get(f"/v1/children/{child_id}/consent", headers=bearer())
    assert consent.status_code == 200
    assert consent.json()["child_id"] == child_id


@pytest.mark.parametrize(
    "path",
    ["/v1/children/{c}", "/v1/children/{c}/consent"],
)
def test_another_guardians_child_looks_like_one_that_does_not_exist(path):
    client, _ = make_client()
    child_id = add_child(client).json()["child_id"]
    real = client.get(path.format(c=child_id), headers=bearer(oid=OTHER))
    missing = client.get(path.format(c="child_nope"), headers=bearer(oid=OTHER))
    assert (real.status_code, real.json()) == (404, missing.json())
    assert missing.status_code == 404


def test_odd_child_ids_are_not_found_rather_than_an_error():
    client, _ = make_client()
    for odd in ["a|b", "x" * 80, "has space"]:
        assert client.get(f"/v1/children/{odd}", headers=bearer()).status_code == 404


def test_a_new_consent_is_added_and_the_latest_is_returned():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    # Later in the day, the guardian opts in to training use.
    client2, _ = make_client(store=store, at=NOW.replace(hour=10))
    added = client2.post(
        "/v1/consents",
        json={"child_id": child_id, "attested": True, "training_opt_in": True},
        headers=bearer(),
    )
    assert added.status_code == 201
    CONSENT.validate(added.json())
    latest = client2.get(f"/v1/children/{child_id}/consent", headers=bearer()).json()
    assert latest["consent_id"] == added.json()["consent_id"]
    assert latest["training_opt_in"] is True
    assert len([p for p in store.docs if p.startswith("consents/")]) == 2


def test_a_consent_needs_the_attestation_and_the_guardians_own_child():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    refused = client.post(
        "/v1/consents", json={"child_id": child_id, "attested": False}, headers=bearer()
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (400, "CONSENT_REQUIRED")
    stranger = client.post(
        "/v1/consents", json={"child_id": child_id, "attested": True}, headers=bearer(oid=OTHER)
    )
    assert stranger.status_code == 404
    assert len([p for p in store.docs if p.startswith("consents/")]) == 1


def test_an_existing_guardians_stored_email_is_used_when_a_later_token_omits_email():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    later, _ = make_client(store=store, at=NOW.replace(hour=10))
    added = later.post(
        "/v1/consents",
        json={"child_id": child_id, "attested": True},
        headers=bearer(email=None),
    )
    assert added.status_code == 201
    assert added.json()["verified_email"] == "guardian@example.com"


def test_a_child_with_no_consent_has_none_to_read():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    for path in [p for p in store.docs if p.startswith("consents/")]:
        del store.docs[path]
    response = client.get(f"/v1/children/{child_id}/consent", headers=bearer())
    assert response.status_code == 404


def test_every_children_route_needs_a_sign_in():
    client, _ = make_client()
    for method, path in [
        ("get", "/v1/children"),
        ("post", "/v1/children"),
        ("get", "/v1/children/child_1"),
        ("get", "/v1/children/child_1/consent"),
        ("post", "/v1/consents"),
    ]:
        assert getattr(client, method)(path).status_code == 401


def test_real_ids_are_a_prefix_and_a_random_hex_string():
    from services.account.children import default_id

    first, second = default_id("child"), default_id("child")
    assert re.fullmatch(r"child_[0-9a-f]{32}", first)
    assert first != second
