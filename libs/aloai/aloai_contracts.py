"""The JSON Schemas in schemas/ (PRD 14.2), used to check what a service receives
and what it writes."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def load(schema_file: str) -> dict:
    return json.loads((SCHEMAS / schema_file).read_text())


_REGISTRY = Registry().with_resources(
    (path.name, Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.schema.json")
)


def validator(schema_file: str) -> Draft202012Validator:
    return Draft202012Validator(
        load(schema_file), registry=_REGISTRY, format_checker=FormatChecker()
    )


GRADE_QUICK_REQUEST = validator("grade_quick_request.schema.json")
GRADER_OUTPUT = validator("grader_output.schema.json")
READING_REPORT = validator("reading_report.schema.json")
PHASE1_TELEMETRY = validator("phase1_telemetry.schema.json")
PLAN = validator("plan.schema.json")
EVENT_ENVELOPE = validator("event_envelope.schema.json")
PASSAGE = validator("passage.schema.json")
CONSENT = validator("consent.schema.json")
GUARDIAN = validator("guardian.schema.json")
CHILD = validator("child.schema.json")
PASSAGE_GENERATE_REQUEST = validator("passage_generate_request.schema.json")
PASSAGE_GENERATE_RESPONSE = validator("passage_generate_response.schema.json")
STORY_REQUEST = validator("story_request.schema.json")
TOPIC_TAGS: tuple[str, ...] = tuple(load("topic_tag.schema.json")["enum"])
