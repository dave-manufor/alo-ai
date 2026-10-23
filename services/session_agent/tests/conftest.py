import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from services.session_agent.machine.profiles import PROFILES

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


@pytest.fixture
def override_profile(monkeypatch):
    """override_profile("demo", listening_module=True) changes fields of a session profile for
    one test and keeps its name, so the session records still say "demo" or "standard". The demo
    passages in the fixtures are the only pair most driver tests have, so a test of the
    listening module runs them with it switched on."""

    def apply(name: str = "demo", **changes) -> None:
        monkeypatch.setitem(PROFILES, name, replace(PROFILES[name], **changes))

    return apply
