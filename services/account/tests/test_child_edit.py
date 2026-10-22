import json

import pytest
from aloai_contracts import CHILD
from services.account.tests.support import GUARDIAN, NOW, bearer, make_client
from services.account.tests.test_children import OTHER, add_child


def edit(client, child_id, who=None, **body):
    return client.patch(f"/v1/children/{child_id}", json=body, headers=bearer(**(who or {})))


def test_a_guardian_edits_their_childs_name_class_and_birth_year():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    response = edit(client, child_id, first_name="  Ada ", primary_class=4, birth_year=2017)
    assert response.status_code == 200
    stored = store.get(f"children/{child_id}")
    CHILD.validate(stored)
    assert (stored["first_name"], stored["primary_class"], stored["birth_year"]) == ("Ada", 4, 2017)
    assert stored["class_confirmed_year"] == NOW.year
    assert stored["guardian_id"] == GUARDIAN
    assert response.json() == {"child_id": child_id, **stored}


def test_changing_only_the_birth_year_does_not_reconfirm_the_class():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    store.merge(f"children/{child_id}", {"class_confirmed_year": 2025})
    assert edit(client, child_id, birth_year=2016).status_code == 200
    stored = store.get(f"children/{child_id}")
    assert (stored["birth_year"], stored["class_confirmed_year"]) == (2016, 2025)


def test_a_field_sent_as_null_is_left_as_it_is():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    name = store.get(f"children/{child_id}")["first_name"]
    assert edit(client, child_id, first_name=None, birth_year=2016).status_code == 200
    stored = store.get(f"children/{child_id}")
    assert (stored["first_name"], stored["birth_year"]) == (name, 2016)


def test_an_edit_keeps_what_the_coach_wrote_and_leaves_consent_alone():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    store.merge(f"children/{child_id}", {"next_session_at": "2026-01-22T09:09:20Z"})
    consents_before = store.where("consents", "child_id", child_id)
    assert edit(client, child_id, first_name="Ada").status_code == 200
    assert store.get(f"children/{child_id}")["next_session_at"] == "2026-01-22T09:09:20Z"
    assert store.where("consents", "child_id", child_id) == consents_before


def test_an_edit_is_audited_without_the_new_values():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    edit(client, child_id, first_name="Ada", birth_year=2017)
    (entry,) = store.where("audit_log", "action", "child.update")
    assert entry["principal_id"] == GUARDIAN
    assert set(entry) >= {"args_sha256", "at", "allowed"}
    assert "Ada" not in json.dumps(entry)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"first_name": "   "},
        {"first_name": ""},
        {"first_name": "x" * 41},
        {"primary_class": 7},
        {"primary_class": 0},
        {"birth_year": 1999},
        {"guardian_id": "guardian_other_002"},
        {"saved_tags": ["food"]},
        {"first_name": "Ada", "created_at": "2020-01-01T00:00:00Z"},
    ],
)
def test_an_edit_that_is_empty_or_asks_for_more_than_it_may_is_refused(body):
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    before = store.get(f"children/{child_id}")
    response = edit(client, child_id, **body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert store.get(f"children/{child_id}") == before


def test_another_guardians_child_cannot_be_edited():
    client, store = make_client()
    child_id = add_child(client).json()["child_id"]
    before = store.get(f"children/{child_id}")
    refused = edit(client, child_id, who={"oid": OTHER}, first_name="Mine now")
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert edit(client, "child_missing", first_name="X").status_code == 404
    assert store.get(f"children/{child_id}") == before
    assert store.where("audit_log", "action", "child.update") == []


def test_editing_needs_a_sign_in():
    client, _ = make_client()
    assert client.patch("/v1/children/child_1", json={"first_name": "A"}).status_code == 401
