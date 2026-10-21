"""Contract tests for POST /v1/grade:quick (PRD 7.4, SDD 7).

The fixtures in fixtures/contracts/ validate against the request and response
schemas, and the shapes the Session Agent must never send or receive are refused.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures" / "contracts"


def _load(path: Path):
    return json.loads(path.read_text())


def _validator(schema_file: str) -> Draft202012Validator:
    return Draft202012Validator(_load(SCHEMAS / schema_file), format_checker=FormatChecker())


REQUEST = _validator("grade_quick_request.schema.json")
RESPONSE = _validator("grade_quick_response.schema.json")


def _fixture(name: str) -> dict:
    return _load(FIXTURES / name)


@pytest.mark.parametrize(
    "schema_file", ["grade_quick_request.schema.json", "grade_quick_response.schema.json"]
)
def test_schemas_are_valid_json_schema(schema_file):
    Draft202012Validator.check_schema(_load(SCHEMAS / schema_file))


@pytest.mark.parametrize(
    "name", ["grade_quick_request.retell.json", "grade_quick_request.question_unanswered.json"]
)
def test_request_fixtures_validate(name):
    REQUEST.validate(_fixture(name))


@pytest.mark.parametrize(
    "name",
    [
        "grade_quick_response.pending.json",
        "grade_quick_response.complete.json",
        "grade_quick_response.error.json",
    ],
)
def test_response_fixtures_validate(name):
    RESPONSE.validate(_fixture(name))


def test_the_retell_is_always_index_zero():
    request = _fixture("grade_quick_request.retell.json") | {"index": 1}
    assert not REQUEST.is_valid(request)


@pytest.mark.parametrize("phase", ["READING", "LISTENING_RETELL", "LISTENING_QUESTION", "ITEM"])
def test_only_the_retell_and_questions_are_quick_scored(phase):
    request = _fixture("grade_quick_request.question_unanswered.json") | {"turn_phase": phase}
    assert not REQUEST.is_valid(request)


@pytest.mark.parametrize("index", [-1, 3])
def test_question_index_stays_within_three_items(index):
    request = _fixture("grade_quick_request.question_unanswered.json") | {"index": index}
    assert not REQUEST.is_valid(request)


@pytest.mark.parametrize("field", ["schema_version", "passage_id", "transcript"])
def test_request_needs_every_field(field):
    request = _fixture("grade_quick_request.retell.json")
    del request[field]
    assert not REQUEST.is_valid(request)


def test_unknown_request_fields_are_refused():
    request = _fixture("grade_quick_request.retell.json") | {"item_id": "bank_p3_market_day_q1"}
    assert not REQUEST.is_valid(request)


def test_a_pending_response_carries_no_decision():
    response = _fixture("grade_quick_response.pending.json") | {"run_listening_module": False}
    assert not RESPONSE.is_valid(response)


def test_a_complete_response_always_carries_a_decision():
    response = _fixture("grade_quick_response.complete.json") | {"run_listening_module": None}
    assert not RESPONSE.is_valid(response)


def test_the_quick_rc_is_never_returned():
    response = _fixture("grade_quick_response.complete.json") | {"quick_rc": 58.9}
    assert not RESPONSE.is_valid(response)


@pytest.mark.parametrize("field", ["code", "message", "retryable"])
def test_an_error_needs_code_message_and_retryable(field):
    response = _fixture("grade_quick_response.error.json")
    del response["error"][field]
    assert not RESPONSE.is_valid(response)


def test_a_response_is_either_a_result_or_an_error():
    response = _fixture("grade_quick_response.complete.json") | _fixture(
        "grade_quick_response.error.json"
    )
    assert not RESPONSE.is_valid(response)
