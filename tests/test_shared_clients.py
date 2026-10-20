"""Tests for the shared clients in libs/aloai: settings, Firestore, Pub/Sub. Fake
clients only: no test reaches a Google service."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import aloai_env
import jsonschema
import pytest
from aloai_events import SCHEMA_VERSIONS, PubSubPublisher, envelope, park, stable_event_id
from aloai_store import FirestoreStore, MemoryStore
from google.api_core.exceptions import AlreadyExists


def test_local_shortcuts_are_refused_on_cloud_run():
    with pytest.raises(aloai_env.ConfigError):
        aloai_env.load({"ALO_ENV": "local", "K_SERVICE": "aloai-core"})


def test_an_unknown_ai_mode_is_refused():
    with pytest.raises(aloai_env.ConfigError):
        aloai_env.load({"AI_MODE": "mock"})


def test_settings_default_to_recorded_ai_in_the_eu_project():
    settings = aloai_env.load({})
    assert (settings.ai_mode, settings.project, settings.location) == (
        "fixtures",
        "aloai-dev",
        "europe-west1",
    )


class FakeDocument:
    def __init__(self, documents, path):
        self._documents, self._path = documents, path

    def get(self):
        data = self._documents.get(self._path)
        return SimpleNamespace(exists=data is not None, to_dict=lambda: data)

    def set(self, data, merge=False):
        base = self._documents.get(self._path, {}) if merge else {}
        self._documents[self._path] = base | data

    def create(self, data):
        if self._path in self._documents:
            raise AlreadyExists("exists")
        self._documents[self._path] = data


class FakeFirestore:
    def __init__(self):
        self.documents = {}
        self.filters = []

    def document(self, path):
        return FakeDocument(self.documents, path)

    def collection(self, name):
        def where(filter):
            self.filters.append(filter)
            found = [d for p, d in self.documents.items() if p.startswith(f"{name}/")]
            return SimpleNamespace(
                stream=lambda: [SimpleNamespace(to_dict=lambda d=d: d) for d in found]
            )

        return SimpleNamespace(where=where)


def test_firestore_documents_are_read_written_merged_and_created_once():
    client = FakeFirestore()
    store = FirestoreStore(client)
    assert store.get("reports/a") is None
    store.set("children/c", {"primary_class": 2})
    store.merge("children/c", {"next_passage_arl": 3})
    assert store.get("children/c") == {"primary_class": 2, "next_passage_arl": 3}
    assert store.create("reports/a", {"child_id": "c"}) is True
    assert store.create("reports/a", {"child_id": "other"}) is False
    assert store.where("reports", "child_id", "c") == [{"child_id": "c"}]
    [query] = client.filters
    assert (query.field_path, query.op_string, query.value) == ("child_id", "==", "c")


def test_events_are_published_with_their_type_as_an_attribute():
    published = []
    client = SimpleNamespace(
        topic_path=lambda project, topic: f"projects/{project}/topics/{topic}",
        publish=lambda topic, data, **attrs: (
            published.append((topic, data, attrs)) or SimpleNamespace(result=lambda: "1")
        ),
    )
    PubSubPublisher(client, "aloai-dev").publish({"type": "report.ready", "session_id": "s"})
    [(topic, data, attrs)] = published
    assert topic == "projects/aloai-dev/topics/aloai.session-events"
    assert json.loads(data) == {"type": "report.ready", "session_id": "s"}
    assert attrs == {"type": "report.ready"}


NOW = datetime(2026, 1, 15, 9, 9, 5, tzinfo=UTC)
SCORED = {"session_id": "sess_demo_001", "telemetry_ref": "sessions/sess_demo_001/phase1/telemetry"}


def test_an_event_carries_its_types_version_and_one_id_per_session():
    event = envelope("phase1.scored", "sess_demo_001", SCORED, now=NOW)
    assert (event["schema_version"], event["occurred_at"]) == (1, "2026-01-15T09:09:05Z")
    assert event["event_id"] == stable_event_id("sess_demo_001", "phase1.scored")
    assert event["event_id"] != stable_event_id("sess_demo_002", "phase1.scored")
    assert event["event_id"] != stable_event_id("sess_demo_001", "report.ready")
    assert SCHEMA_VERSIONS["session.done"] == 2


def test_an_event_its_schema_refuses_is_never_built():
    with pytest.raises(jsonschema.ValidationError):
        envelope("phase1.scored", "sess_demo_001", {"session_id": "sess_demo_001"}, now=NOW)


def test_an_event_that_can_never_succeed_is_kept_by_session_and_type():
    store = MemoryStore()
    event = envelope("phase1.scored", "sess_demo_001", SCORED, now=NOW)
    path = park(store, event, LookupError("no document passages/x"), NOW)
    assert path == "sessions/sess_demo_001/errors/phase1.scored"
    assert store.get(path) == {
        "event_id": event["event_id"],
        "type": "phase1.scored",
        "error": "LookupError",
        "message": "no document passages/x",
        "at": "2026-01-15T09:09:05Z",
    }
