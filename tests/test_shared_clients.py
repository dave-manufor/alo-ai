"""Tests for the shared clients in libs/aloai: settings, Firestore, Pub/Sub. Fake
clients only: no test reaches a Google service."""

import json
from types import SimpleNamespace

import aloai_env
import pytest
from aloai_events import PubSubPublisher
from aloai_store import FirestoreStore
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
