"""Contract tests for blob URIs and the embedding model (GCP or Azure deployment).

Audio, clip and book-file references are `gs://bucket/name` on GCP and
`az://container/name` on Azure. Anything else (a browser URL, a local path) is refused.
"""

import json
import re
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

BLOB_PATTERN = "^(gs|az)://"


def _patterns(node, found):
    """Every `pattern` in a schema that is about blob URIs."""
    if isinstance(node, dict):
        pattern = node.get("pattern")
        if isinstance(pattern, str) and "://" in pattern and "http" not in pattern:
            found.append(pattern)
        for value in node.values():
            _patterns(value, found)
    elif isinstance(node, list):
        for value in node:
            _patterns(value, found)
    return found


def _blob_patterns():
    return [
        (path.name, pattern)
        for path in sorted(SCHEMAS.glob("*.schema.json"))
        for pattern in _patterns(json.loads(path.read_text()), [])
    ]


def test_every_blob_uri_field_is_checked():
    # book 1, passage 3, phase1_recorded 1, plan 1, session_done 1, session_record 1.
    # A new blob field changes this number, so it is looked at on purpose.
    assert len(_blob_patterns()) == 8


@pytest.mark.parametrize("schema_file, pattern", _blob_patterns())
def test_every_blob_uri_field_takes_either_cloud(schema_file, pattern):
    assert pattern == BLOB_PATTERN, schema_file
    assert re.match(pattern, "gs://aloai-dev-audio/a/b.flac")
    assert re.match(pattern, "az://audio/a/b.flac")
    assert not re.match(pattern, "https://example.org/a.flac")
    assert not re.match(pattern, "/tmp/a.flac")


def _book(**changes) -> dict:
    book = json.loads((FIXTURES / "book.sample.json").read_text())
    return book | changes


BOOK = Draft202012Validator(
    json.loads((SCHEMAS / "book.schema.json").read_text()),
    registry=REGISTRY,
    format_checker=FormatChecker(),
)


def test_the_book_fixture_still_validates():
    BOOK.validate(_book())


def test_a_book_embedded_on_azure_validates():
    BOOK.validate(
        _book(embedding_model="text-embedding-3-small", raw_uri="az://books/raw/book_demo_001.pdf")
    )


@pytest.mark.parametrize(
    "change",
    [
        {"embedding_model": "text-embedding-004"},
        {"raw_uri": "https://example.org/book.pdf"},
        {"embedding": [0.0] * 1536},
    ],
)
def test_a_book_outside_the_contract_is_refused(change):
    assert not BOOK.is_valid(_book(**change))
