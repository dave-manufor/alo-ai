"""Contract tests for what the Account service writes (consent, guardian, child; SDD 12).

Every fixture validates against its schema, the three fixtures describe one consistent
fictional guardian and child, and shapes the readers must never see are refused.
"""

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from aloai_contracts import CHILD, CONSENT, GUARDIAN

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "contracts"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


CONSENT_FIXTURE = _fixture("consent.child_demo_001.json")
GUARDIAN_FIXTURE = _fixture("guardian.guardian_demo_001.json")
CHILD_FIXTURE = _fixture("child.child_demo_001.json")


@pytest.mark.parametrize(
    ("validator", "document"),
    [(CONSENT, CONSENT_FIXTURE), (GUARDIAN, GUARDIAN_FIXTURE), (CHILD, CHILD_FIXTURE)],
)
def test_fixtures_validate(validator, document):
    validator.validate(document)


def test_fixtures_describe_one_guardian_and_child():
    assert CONSENT_FIXTURE["guardian_id"] == GUARDIAN_FIXTURE["guardian_id"]
    assert CHILD_FIXTURE["guardian_id"] == GUARDIAN_FIXTURE["guardian_id"]
    assert CONSENT_FIXTURE["sign_in_method"] == GUARDIAN_FIXTURE["sign_in_method"]
    assert CONSENT_FIXTURE["verified_email"] == GUARDIAN_FIXTURE["email"]


def test_child_needs_only_the_fields_the_account_service_writes():
    required_only = {
        key: CHILD_FIXTURE[key]
        for key in (
            "schema_version",
            "guardian_id",
            "first_name",
            "primary_class",
            "birth_year",
            "class_confirmed_year",
            "created_at",
        )
    }
    CHILD.validate(required_only)


@pytest.mark.parametrize(
    ("validator", "document", "change"),
    [
        (CONSENT, CONSENT_FIXTURE, {"sign_in_method": "sms"}),
        (CONSENT, CONSENT_FIXTURE, {"verified_email": "not-an-email"}),
        (CONSENT, CONSENT_FIXTURE, {"training_opt_in": "no"}),
        (CONSENT, CONSENT_FIXTURE, {"withdrawn_at": "2026-02-01T00:00:00Z"}),
        (GUARDIAN, GUARDIAN_FIXTURE, {"phone": "08000000000"}),
        (GUARDIAN, GUARDIAN_FIXTURE, {"created_at": "yesterday"}),
        (CHILD, CHILD_FIXTURE, {"primary_class": 7}),
        (CHILD, CHILD_FIXTURE, {"primary_class": 0}),
        (CHILD, CHILD_FIXTURE, {"first_name": ""}),
        (CHILD, CHILD_FIXTURE, {"saved_tags": ["not-a-topic"]}),
        (CHILD, CHILD_FIXTURE, {"next_passage_arl": 13}),
        (CHILD, CHILD_FIXTURE, {"surname": "Example"}),
    ],
)
def test_refuses_what_readers_must_not_see(validator, document, change):
    with pytest.raises(ValidationError):
        validator.validate({**document, **change})


@pytest.mark.parametrize(
    ("validator", "document", "missing"),
    [
        (CONSENT, CONSENT_FIXTURE, "attestation"),
        (CONSENT, CONSENT_FIXTURE, "text_version"),
        (CONSENT, CONSENT_FIXTURE, "verified_email"),
        (GUARDIAN, GUARDIAN_FIXTURE, "email"),
        (CHILD, CHILD_FIXTURE, "guardian_id"),
        (CHILD, CHILD_FIXTURE, "primary_class"),
    ],
)
def test_requires_the_fields_the_gate_relies_on(validator, document, missing):
    broken = {k: v for k, v in document.items() if k != missing}
    with pytest.raises(ValidationError):
        validator.validate(broken)
