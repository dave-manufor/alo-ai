"""Contract tests for what W3 produces after the session (PRD 10.2 to 10.4, SDD 11).

Every fixture validates against its schema, the fixtures describe one consistent
fictional session (sess_demo_001 on the Market Day passage), and shapes the
consumers must never receive are refused.
"""

import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures" / "contracts"

REGISTRY = Registry().with_resources(
    (path.name, Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.schema.json")
)

W3_SCHEMAS = [
    "phase1_telemetry.schema.json",
    "grader_output.schema.json",
    "reading_report.schema.json",
    "phase1_scored.schema.json",
    "report_ready.schema.json",
    "plan_ready.schema.json",
]


def _load(path: Path):
    return json.loads(path.read_text())


def _validator(schema_file: str) -> Draft202012Validator:
    return Draft202012Validator(
        _load(SCHEMAS / schema_file), registry=REGISTRY, format_checker=FormatChecker()
    )


def _fixture(name: str) -> dict:
    return _load(FIXTURES / name)


TELEMETRY = _validator("phase1_telemetry.schema.json")
GRADER = _validator("grader_output.schema.json")
REPORT = _validator("reading_report.schema.json")
ENVELOPE = _validator("event_envelope.schema.json")


@pytest.mark.parametrize("schema_file", W3_SCHEMAS)
def test_schemas_are_valid_json_schema(schema_file):
    Draft202012Validator.check_schema(_load(SCHEMAS / schema_file))


@pytest.mark.parametrize(
    "validator, name",
    [
        (TELEMETRY, "phase1_telemetry.sess_demo_001.json"),
        (GRADER, "grader_output.sess_demo_001.json"),
        (REPORT, "reading_report.sess_demo_001.json"),
        (ENVELOPE, "event.phase1_scored.json"),
        (ENVELOPE, "event.report_ready.json"),
        (ENVELOPE, "event.plan_ready.json"),
    ],
)
def test_fixtures_validate(validator, name):
    validator.validate(_fixture(name))


@pytest.mark.parametrize(
    "name, other_type",
    [
        ("event.phase1_scored.json", "report.ready"),
        ("event.report_ready.json", "plan.ready"),
        ("event.plan_ready.json", "phase1.scored"),
    ],
)
def test_event_data_must_match_its_type(name, other_type):
    event = _fixture(name) | {"type": other_type}
    assert not ENVELOPE.is_valid(event)


# ---- the fixtures describe one session


def test_telemetry_follows_the_passage_word_by_word():
    tokens = _fixture("passage.bank_p3_market_day.json")["tokens"]
    events = _fixture("phase1_telemetry.sess_demo_001.json")["word_events"]
    assert [e["token_index"] for e in events] == [t["token_index"] for t in tokens]
    assert [e["target_word"] for e in events] == [t["clean_text"] for t in tokens]


def test_telemetry_counts_match_the_word_labels():
    telemetry = _fixture("phase1_telemetry.sess_demo_001.json")
    labels = Counter(e["label"] for e in telemetry["word_events"])
    errors = telemetry["error_counts"]
    assert [labels["SUBSTITUTION"], labels["OMISSION"], labels["TOLD"]] == [
        errors["substitution"],
        errors["omission"],
        errors["told"],
    ]
    self_corrected = sum(e["is_self_corrected"] for e in telemetry["word_events"])
    assert labels["UNCERTAIN"] == telemetry["uncertain_count"]
    assert self_corrected == telemetry["self_correction_count"]
    scored = telemetry["words_attempted"] - telemetry["uncertain_count"]
    assert telemetry["words_correct"] == scored - sum(errors.values())


def test_telemetry_reading_time_runs_from_first_onset_to_last_offset():
    telemetry = _fixture("phase1_telemetry.sess_demo_001.json")
    events = telemetry["word_events"]
    span = (events[-1]["end_ms"] - events[0]["start_ms"]) / 1000
    assert round(span, 1) == telemetry["reading_seconds"]


def test_grader_output_covers_the_passage():
    passage = _fixture("passage.bank_p3_market_day.json")
    graded = _fixture("grader_output.sess_demo_001.json")
    assert [p["id"] for p in graded["propositions"]] == [p["id"] for p in passage["propositions"]]
    assert [i["item_id"] for i in graded["items"]] == [i["item_id"] for i in passage["items"]]


def test_report_repeats_the_passage_telemetry_and_event():
    passage = _fixture("passage.bank_p3_market_day.json")
    telemetry = _fixture("phase1_telemetry.sess_demo_001.json")
    report = _fixture("reading_report.sess_demo_001.json")
    ready = _fixture("event.report_ready.json")["data"]

    assert report["passage"] == {
        "passage_id": passage["passage_id"],
        "source": passage["source"],
        "title": passage["title"],
        "topic_tags": passage["topic_tags"],
    }
    assert report["level"]["passage_arl"] == passage["arl_level"]
    for field in ("accuracy_pct", "wcpm", "words_attempted", "reading_seconds"):
        assert report["fluency"][field] == telemetry[field]
    assert set(telemetry["flags"]) <= set(report["flags"])
    assert (ready["profile"], ready["provisional"]) == (
        report["profile"]["code"],
        report["profile"]["provisional"],
    )


# ---- what consumers can rely on


def test_the_coach_text_is_null_until_the_coach_writes_it():
    report = _fixture("reading_report.sess_demo_001.json")
    assert report["parent_reporting"] is None
    report["parent_reporting"] = {"summary_script": "Hello!", "home_practice": "Read together."}
    assert REPORT.is_valid(report)
    report["parent_reporting"] = {"summary_script": "Hello!"}
    assert not REPORT.is_valid(report)


def test_a_reading_stopped_early_reports_no_reading_comprehension():
    report = _fixture("reading_report.sess_demo_001.json")
    report["comprehension"] |= {
        "reading_comprehension": None,
        "retell_coverage": None,
        "item_score": None,
        "quick_reading_comprehension": None,
    }
    report["level"] |= {"band": "FRUSTRATION", "reported_arl": 1, "next_passage_arl": 1}
    assert REPORT.is_valid(report)


def test_insufficient_evidence_has_no_level_or_book_band():
    report = _fixture("reading_report.sess_demo_001.json")
    report["profile"]["code"] = "INSUFFICIENT_EVIDENCE"
    report["level"] |= {"band": None, "reported_arl": None, "approx_primary_class": None}
    report["recommendations"] = {"arl_min": None, "arl_max": None, "book_ids": []}
    assert REPORT.is_valid(report)


@pytest.mark.parametrize("field", ["child_id", "guardian_id", "schema_version", "versions"])
def test_report_needs_every_key_the_rules_and_audit_use(field):
    report = _fixture("reading_report.sess_demo_001.json")
    del report[field]
    assert not REPORT.is_valid(report)


@pytest.mark.parametrize(
    "path, value",
    [
        (("versions",), {"grader_model": "gemini-2.5-pro"}),
        (("flags",), ["DEMO_PROFILE", "NOT_A_FLAG"]),
        (("recommendations", "book_ids"), ["b1", "b2", "b3", "b4"]),
        (("level", "band"), "AVERAGE"),
        (("fluency", "reading_seconds"), 95),
        (("comprehension", "reading_comprehension"), 101),
    ],
)
def test_report_refuses_values_outside_the_contract(path, value):
    report = _fixture("reading_report.sess_demo_001.json")
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert not REPORT.is_valid(report)


@pytest.mark.parametrize(
    "section, field, value",
    [("propositions", "credit", 0.25), ("items", "points", 3), ("items", "needs_review", None)],
)
def test_grader_output_stays_on_the_rubric(section, field, value):
    graded = _fixture("grader_output.sess_demo_001.json")
    graded[section][0][field] = value
    assert not GRADER.is_valid(graded)


@pytest.mark.parametrize(
    "change",
    [
        lambda t: t["word_events"][0].update(label="SKIPPED"),
        lambda t: t.update(flags=["LIVE_FALLBACK"]),
        lambda t: t.update(reading_seconds=90.5),
        lambda t: t["model_versions"].pop("scoring_module"),
    ],
)
def test_telemetry_refuses_values_outside_the_contract(change):
    telemetry = _fixture("phase1_telemetry.sess_demo_001.json")
    change(telemetry)
    assert not TELEMETRY.is_valid(telemetry)
