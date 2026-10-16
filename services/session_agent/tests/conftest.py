import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[3] / "schemas"

_REGISTRY = Registry().with_resources(
    (path.name, Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.schema.json")
)


@pytest.fixture
def validate():
    """validate("event_envelope.schema.json", instance) raises if the instance breaks the schema."""

    def check(schema_file: str, instance) -> None:
        schema = json.loads((SCHEMAS / schema_file).read_text())
        Draft202012Validator(schema, registry=_REGISTRY, format_checker=FormatChecker()).validate(
            instance
        )

    return check
