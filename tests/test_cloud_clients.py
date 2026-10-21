"""Tests for the cloud seams in libs/aloai (CLOUD=gcp|azure): settings, documents, blobs,
event queues and service-to-service checks. Fake clients only: no test reaches Google or
Azure. The store and blob contracts run against every backend, so the Cosmos and Azure
adapters must behave as Firestore and Cloud Storage do for the services.
"""

import asyncio
import base64
import copy
import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import aloai_env
import pytest
from aloai_blobs import (
    AzureBlobs,
    BlobNotFound,
    GcsBlobs,
    MemoryBlobs,
    blob_uri,
    split_uri,
)
from aloai_events import (
    SCHEMA_VERSIONS,
    MemoryPublisher,
    QueuePump,
    ServiceBusPublisher,
    bus_event,
    envelope,
    pump_lifespan,
    pump_once,
    pushed_event,
    service_bus_pump,
)
from aloai_service_auth import anyone, entra_caller
from aloai_store import CosmosStore, FirestoreStore, MemoryStore, require
from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.cosmos.exceptions import (
    CosmosAccessConditionFailedError,
    CosmosResourceExistsError,
    CosmosResourceNotFoundError,
)
from google.api_core.exceptions import AlreadyExists, NotFound, PreconditionFailed

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 1, 15, 9, 9, 5, tzinfo=UTC)

# ---- settings


@pytest.mark.parametrize(
    "hosted",
    [
        {"CONTAINER_APP_NAME": "aloai-core"},
        {"CONTAINER_APP_JOB_NAME": "aloai-book-ingest"},
    ],
)
@pytest.mark.parametrize(
    "shortcut",
    [{"ALO_ENV": "local", "AI_MODE": "live"}, {"AI_MODE": "fixtures"}, {}],
    ids=["emulators", "recorded AI", "recorded AI by default"],
)
def test_local_shortcuts_are_refused_on_container_apps(hosted, shortcut):
    with pytest.raises(aloai_env.ConfigError, match="Container Apps"):
        aloai_env.load({"CLOUD": "azure"} | hosted | shortcut)


@pytest.mark.parametrize(
    "name",
    [
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_COSMOS_KEY",
        "AZURE_SERVICEBUS_CONNECTION_STRING",
    ],
)
def test_emulator_connections_are_refused_when_hosted_but_allowed_locally(name):
    hosted = {
        "CLOUD": "azure",
        "AI_MODE": "live",
        "CONTAINER_APP_NAME": "aloai-core",
        name: "x",
    }
    with pytest.raises(aloai_env.ConfigError, match=name):
        aloai_env.load(hosted)
    local = aloai_env.load({"CLOUD": "azure", "ALO_ENV": "local", name: "x"})
    assert local.hosted is False


def test_an_azure_service_needs_no_push_identity():
    settings = aloai_env.load(
        {"CLOUD": "azure", "AI_MODE": "live", "CONTAINER_APP_NAME": "aloai-core"}
    )
    assert (settings.cloud, settings.hosted, settings.push_service_account) == (
        "azure",
        True,
        None,
    )


def test_the_cloud_defaults_to_gcp_and_an_unknown_one_is_refused():
    assert aloai_env.load({}).cloud == "gcp"
    with pytest.raises(aloai_env.ConfigError, match="CLOUD"):
        aloai_env.load({"CLOUD": "aws"})


def test_the_location_defaults_to_an_eu_region_of_the_chosen_cloud():
    assert aloai_env.load({}).location == "europe-west1"
    assert aloai_env.load({"CLOUD": "azure"}).location == "swedencentral"
    assert (
        aloai_env.load({"CLOUD": "azure", "GOOGLE_CLOUD_LOCATION": "x"}).location == "x"
    )


def test_azure_resources_are_read_from_the_environment():
    settings = aloai_env.load(
        {
            "CLOUD": "azure",
            "AZURE_COSMOS_ENDPOINT": "https://aloai.documents.azure.com",
            "AZURE_COSMOS_DATABASE": "alo",
            "AZURE_SERVICEBUS_NAMESPACE": "aloai-bus",
            "AZURE_STORAGE_ACCOUNT": "aloaistore",
        }
    )
    assert settings.cosmos_endpoint == "https://aloai.documents.azure.com"
    assert (settings.cosmos_database, settings.servicebus_namespace) == (
        "alo",
        "aloai-bus",
    )
    assert settings.storage_account == "aloaistore"
    assert aloai_env.load({}).cosmos_database == "aloai"


def test_a_missing_setting_is_named():
    assert aloai_env.require_setting("x", "NAME") == "x"
    with pytest.raises(aloai_env.ConfigError, match="AZURE_STORAGE_ACCOUNT"):
        aloai_env.require_setting(None, "AZURE_STORAGE_ACCOUNT")


def test_event_routes_turn_queues_into_a_route_for_each_event_type():
    routes = aloai_env.load(
        {"EVENT_ROUTES": '{"a-events": ["x", "y"], "b-events": ["y"]}'}
    ).event_routes
    assert routes == {"x": ("a-events",), "y": ("a-events", "b-events")}
    assert aloai_env.load({}).event_routes is None


@pytest.mark.parametrize("raw", ["not json", "[1]", '{"q": 3}', '{"q": [["x"]]}'])
def test_event_routes_that_are_not_queues_of_types_are_refused(raw):
    with pytest.raises(aloai_env.ConfigError, match="EVENT_ROUTES"):
        aloai_env.load({"EVENT_ROUTES": raw})


def test_infra_events_json_routes_only_real_event_types_and_every_type_once_per_queue():
    queues = json.loads((ROOT / "infra" / "events.json").read_text())["queues"]
    handled = [event_type for types in queues.values() for event_type in types]
    assert set(handled) <= set(SCHEMA_VERSIONS)
    for types in queues.values():
        assert len(types) == len(set(types))
    routes = aloai_env.load({"EVENT_ROUTES": json.dumps(queues)}).event_routes
    assert routes["phase1.recorded"] == ("scorer-events",)
    assert routes["session.done"] == ("core-events",)
    assert "session.started" not in routes


# ---- documents: one contract, every backend


class FirestoreFake:
    """Firestore as the store sees it, with its real merge, create and query behaviour."""

    def __init__(self):
        self.documents = {}

    def document(self, path):
        return FirestoreDocument(self.documents, path)

    def get_all(self, references):
        return [
            SimpleNamespace(
                reference=SimpleNamespace(path=r.path),
                exists=r.path in self.documents,
                to_dict=lambda r=r: copy.deepcopy(self.documents.get(r.path)),
            )
            for r in reversed(references)
        ]

    def collection(self, name):
        def where(filter):
            found = [
                copy.deepcopy(d)
                for p, d in self.documents.items()
                if p.startswith(f"{name}/")
                and "/" not in p[len(name) + 1 :]
                and d.get(filter.field_path) == filter.value
            ]
            return SimpleNamespace(
                stream=lambda: [SimpleNamespace(to_dict=lambda d=d: d) for d in found]
            )

        return SimpleNamespace(where=where)


def _deep_merge(base, changes):
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class FirestoreDocument:
    def __init__(self, documents, path):
        self._documents, self.path = documents, path

    def get(self):
        data = self._documents.get(self.path)
        return SimpleNamespace(
            exists=data is not None, to_dict=lambda: copy.deepcopy(data)
        )

    def set(self, data, merge=False):
        base = self._documents.get(self.path, {}) if merge else {}
        self._documents[self.path] = _deep_merge(base, copy.deepcopy(data))

    def create(self, data):
        if self.path in self._documents:
            raise AlreadyExists("exists")
        self._documents[self.path] = copy.deepcopy(data)


class CosmosFake:
    """One Cosmos DB container: items by (id, partition key), etags, and the one query
    CosmosStore.where sends."""

    def __init__(self):
        self.items = {}
        self.etags = 0
        self.before_replace = None
        self.before_create = None
        self.queries = []

    def _stamp(self, body):
        self.etags += 1
        return copy.deepcopy(body) | {"_etag": f"etag-{self.etags}", "_ts": 1}

    def read_item(self, item, partition_key):
        found = self.items.get((item, partition_key))
        if found is None:
            raise CosmosResourceNotFoundError(message="not found")
        return copy.deepcopy(found)

    def read_items(self, items):
        return [copy.deepcopy(self.items[key]) for key in items if key in self.items]

    def create_item(self, body):
        if self.before_create:
            self.before_create(self)
        key = (body["id"], body["pk"])
        if key in self.items:
            raise CosmosResourceExistsError(message="exists")
        self.items[key] = self._stamp(body)

    def upsert_item(self, body):
        self.items[(body["id"], body["pk"])] = self._stamp(body)

    def replace_item(self, item, body, etag=None, match_condition=None):
        if self.before_replace:
            self.before_replace(self)
        key = (item, body["pk"])
        if key not in self.items:
            raise CosmosResourceNotFoundError(message="not found")
        if (
            match_condition == MatchConditions.IfNotModified
            and self.items[key]["_etag"] != etag
        ):
            raise CosmosAccessConditionFailedError(message="precondition failed")
        self.items[key] = self._stamp(body)

    def query_items(self, query, parameters, enable_cross_partition_query):
        assert enable_cross_partition_query is True
        self.queries.append(query)
        wanted = {p["name"]: p["value"] for p in parameters}
        path = re.findall(r'\["([^"]+)"\]', query)
        found = []
        for item in self.items.values():
            value = item["d"]
            for part in path:
                value = value.get(part) if isinstance(value, dict) else None
            if item["col"] == wanted["@col"] and value == wanted["@value"]:
                found.append(copy.deepcopy(item["d"]))
        return iter(found)


@pytest.fixture(params=["memory", "firestore", "cosmos"])
def store(request):
    if request.param == "memory":
        return MemoryStore()
    if request.param == "firestore":
        return FirestoreStore(FirestoreFake())
    return CosmosStore(CosmosFake())


def test_a_document_is_set_read_and_replaced(store):
    assert store.get("children/c") is None
    store.set("children/c", {"primary_class": 2, "tags": ["food"]})
    assert store.get("children/c") == {"primary_class": 2, "tags": ["food"]}
    store.set("children/c", {"primary_class": 3})
    assert store.get("children/c") == {"primary_class": 3}


def test_a_document_read_back_is_a_copy(store):
    store.set("children/c", {"levels": {"next": 2}})
    store.get("children/c")["levels"]["next"] = 9
    assert store.get("children/c") == {"levels": {"next": 2}}


def test_merge_joins_maps_replaces_lists_and_creates_a_missing_document(store):
    store.merge("children/c", {"guardian_id": "g", "levels": {"next": 2, "last": 3}})
    store.merge("children/c", {"levels": {"next": 4}, "saved_tags": ["food"]})
    store.merge("children/c", {"saved_tags": ["music"]})
    assert store.get("children/c") == {
        "guardian_id": "g",
        "levels": {"next": 4, "last": 3},
        "saved_tags": ["music"],
    }


def test_merge_replaces_a_value_that_is_not_a_map_with_a_map(store):
    store.set("children/c", {"levels": 3})
    store.merge("children/c", {"levels": {"next": 4}})
    assert store.get("children/c") == {"levels": {"next": 4}}


def test_create_writes_only_when_the_document_is_absent(store):
    assert store.create("reports/a", {"child_id": "c"}) is True
    assert store.create("reports/a", {"child_id": "other"}) is False
    assert store.get("reports/a") == {"child_id": "c"}


def test_many_documents_are_read_in_the_order_asked_and_missing_ones_are_none(store):
    store.set("quick/a", {"points": 2})
    store.set("quick/c", {"points": 0})
    assert store.get_many(["quick/c", "quick/b", "quick/a"]) == [
        {"points": 0},
        None,
        {"points": 2},
    ]
    assert store.get_many([]) == []


def test_where_finds_the_documents_of_one_collection_with_a_matching_field(store):
    store.set("reports/a", {"child_id": "c", "n": 1})
    store.set("reports/b", {"child_id": "other"})
    store.set("reports/d", {"child_id": "c", "n": 2})
    store.set("plans/p", {"child_id": "c"})
    store.set("sessions/s/turns/t", {"child_id": "c"})
    found = store.where("reports", "child_id", "c")
    assert sorted(found, key=lambda d: d["n"]) == [
        {"child_id": "c", "n": 1},
        {"child_id": "c", "n": 2},
    ]
    assert store.where("reports", "child_id", "nobody") == []
    assert store.where("sessions/s/turns", "child_id", "c") == [{"child_id": "c"}]


# ---- Cosmos specifics


def test_cosmos_keeps_a_session_and_its_turns_in_one_partition_and_a_document_in_a_wrapper():
    container = CosmosFake()
    store = CosmosStore(container)
    store.set("sessions/s1", {"id": "not-the-item-id", "pk": "x"})
    store.set("sessions/s1/turns/t1", {"phase": "READING"})
    assert set(container.items) == {
        ("sessions|s1", "sessions/s1"),
        ("sessions|s1|turns|t1", "sessions/s1"),
    }
    item = container.items[("sessions|s1|turns|t1", "sessions/s1")]
    assert (item["col"], item["d"]) == ("sessions/s1/turns", {"phase": "READING"})
    assert store.get("sessions/s1") == {"id": "not-the-item-id", "pk": "x"}


@pytest.mark.parametrize("path", ["sessions", "sessions/s1/turns", "", "a//b", "a|b/c"])
def test_cosmos_refuses_what_is_not_a_document_path(path):
    with pytest.raises(ValueError, match="document path"):
        CosmosStore(CosmosFake()).get(path)


@pytest.mark.parametrize(
    "field", ["", "a b", 'a"]; DROP', "a..b", "1a", "a.", "a['b']"]
)
def test_cosmos_refuses_a_field_that_is_not_a_field_path(field):
    with pytest.raises(ValueError, match="field path"):
        CosmosStore(CosmosFake()).where("reports", field, 1)


def test_cosmos_finds_by_a_nested_field_and_sends_the_value_as_a_parameter():
    container = CosmosFake()
    store = CosmosStore(container)
    store.set("reports/a", {"level": {"arl": 4}})
    store.set("reports/b", {"level": {"arl": 5}})
    assert store.where("reports", "level.arl", 4) == [{"level": {"arl": 4}}]
    assert container.queries == [
        'SELECT VALUE c.d FROM c WHERE c.col = @col AND c.d["level"]["arl"] = @value'
    ]


def test_cosmos_keeps_a_dedicated_collection_in_its_own_container():
    docs, books = CosmosFake(), CosmosFake()
    store = CosmosStore(docs, {"books": books})
    store.set("books/b1", {"arl": 3})
    store.set("children/c", {"primary_class": 2})
    assert list(books.items) == [("books|b1", "books/b1")]
    assert list(docs.items) == [("children|c", "children/c")]
    assert store.get_many(["children/c", "books/b1", "books/b2"]) == [
        {"primary_class": 2},
        {"arl": 3},
        None,
    ]
    assert store.where("books", "arl", 3) == [{"arl": 3}]
    assert store.where("children", "primary_class", 2) == [{"primary_class": 2}]


def test_cosmos_merge_tries_again_when_another_writer_got_in_first():
    container = CosmosFake()
    store = CosmosStore(container)
    store.set("children/c", {"levels": {"next": 2}})
    interruptions = []

    def other_writer(fake):
        if not interruptions:
            interruptions.append(1)
            fake.items[("children|c", "children/c")] = fake._stamp(
                {
                    "id": "children|c",
                    "pk": "children/c",
                    "col": "children",
                    "d": {"levels": {"next": 2}, "guardian_id": "g"},
                }
            )

    container.before_replace = other_writer
    store.merge("children/c", {"levels": {"last": 3}})
    assert store.get("children/c") == {
        "levels": {"next": 2, "last": 3},
        "guardian_id": "g",
    }
    assert interruptions == [1]


def test_cosmos_merge_gives_up_when_it_never_gets_a_turn():
    container = CosmosFake()
    store = CosmosStore(container)
    store.set("children/c", {"a": 1})

    def always_first(fake):
        fake.items[("children|c", "children/c")] = fake._stamp(
            {"id": "children|c", "pk": "children/c", "col": "children", "d": {"a": 1}}
        )

    container.before_replace = always_first
    with pytest.raises(RuntimeError, match="concurrent writers"):
        store.merge("children/c", {"b": 2})


def test_cosmos_merge_that_races_a_create_merges_into_the_winner():
    container = CosmosFake()
    store = CosmosStore(container)

    def winner(fake):
        fake.before_create = None
        fake.items[("children|c", "children/c")] = fake._stamp(
            {
                "id": "children|c",
                "pk": "children/c",
                "col": "children",
                "d": {"guardian_id": "g"},
            }
        )

    container.before_create = winner
    store.merge("children/c", {"primary_class": 2})
    assert store.get("children/c") == {"guardian_id": "g", "primary_class": 2}


# ---- blobs: one contract, every backend


class BucketFake:
    """Cloud Storage as GcsBlobs uses it."""

    def __init__(self):
        self.objects = {}

    def bucket(self, name):
        return SimpleNamespace(
            blob=lambda blob_name: GcsObjectFake(self.objects, (name, blob_name))
        )


class GcsObjectFake:
    def __init__(self, objects, key):
        self._objects, self._key = objects, key

    def download_as_bytes(self):
        if self._key not in self._objects:
            raise NotFound("no such object")
        return self._objects[self._key][0]

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        if if_generation_match == 0 and self._key in self._objects:
            raise PreconditionFailed("exists")
        self._objects[self._key] = (data, content_type)

    def exists(self):
        return self._key in self._objects


class BlobServiceFake:
    """Blob Storage as AzureBlobs uses it."""

    def __init__(self):
        self.objects = {}

    def get_blob_client(self, container, name):
        return AzureObjectFake(self.objects, (container, name))


class AzureObjectFake:
    def __init__(self, objects, key):
        self._objects, self._key = objects, key

    def download_blob(self):
        if self._key not in self._objects:
            raise ResourceNotFoundError("no such blob")
        return SimpleNamespace(readall=lambda: self._objects[self._key][0])

    def upload_blob(self, data, overwrite=False, content_settings=None):
        if not overwrite and self._key in self._objects:
            raise ResourceExistsError("exists")
        content_type = content_settings.content_type if content_settings else None
        self._objects[self._key] = (data, content_type)

    def exists(self):
        return self._key in self._objects


@pytest.fixture(params=["memory", "gcs", "azure"])
def blobs(request):
    """(the backend, the URI scheme it takes)."""
    if request.param == "memory":
        return MemoryBlobs(), "gs"
    if request.param == "gcs":
        return GcsBlobs(BucketFake()), "gs"
    return AzureBlobs(BlobServiceFake()), "az"


def _uri(scheme, name="3f2b/READING/a1b2.flac"):
    return f"{scheme}://aloai-audio/{name}"


def test_a_blob_is_written_read_and_replaced(blobs):
    store, scheme = blobs
    uri = _uri(scheme)
    assert store.exists(uri) is False
    store.write(uri, b"one", "audio/flac")
    assert (store.read(uri), store.exists(uri)) == (b"one", True)
    store.write(uri, b"two")
    assert store.read(uri) == b"two"


def test_a_blob_that_is_not_there_is_not_found_whatever_the_backend(blobs):
    store, scheme = blobs
    with pytest.raises(BlobNotFound) as error:
        store.read(_uri(scheme, "missing.flac"))
    assert isinstance(error.value, LookupError)


def test_write_if_absent_never_replaces_a_blob(blobs):
    store, scheme = blobs
    uri = _uri(scheme, "words/rain.mp3")
    assert store.write_if_absent(uri, b"first", "audio/mpeg") is True
    assert store.write_if_absent(uri, b"second", "audio/mpeg") is False
    assert store.read(uri) == b"first"


def test_a_clip_name_is_used_exactly_as_given(blobs):
    store, scheme = blobs
    uri = _uri(scheme, "vp/v1/words/tunde~%CB%88tund%C9%9B.mp3")
    store.write(uri, b"clip")
    assert store.read(uri) == b"clip"
    assert store.exists(_uri(scheme, "vp/v1/words/tunde~ˈtundɛ.mp3")) is False


def test_the_content_type_is_kept():
    gcs, azure, memory = BucketFake(), BlobServiceFake(), MemoryBlobs()
    GcsBlobs(gcs).write("gs://b/a.mp3", b"x", "audio/mpeg")
    AzureBlobs(azure).write("az://b/a.mp3", b"x", "audio/mpeg")
    memory.write("az://b/a.mp3", b"x", "audio/mpeg")
    assert gcs.objects[("b", "a.mp3")] == (b"x", "audio/mpeg")
    assert azure.objects[("b", "a.mp3")] == (b"x", "audio/mpeg")
    assert memory.content_types["az://b/a.mp3"] == "audio/mpeg"


def test_a_backend_takes_only_its_own_clouds_uris():
    with pytest.raises(ValueError, match="gs://"):
        GcsBlobs(BucketFake()).read("az://b/a.flac")
    with pytest.raises(ValueError, match="az://"):
        AzureBlobs(BlobServiceFake()).read("gs://b/a.flac")


@pytest.mark.parametrize(
    "uri",
    [
        "",
        "gs://",
        "gs://bucket",
        "gs://bucket/",
        "s3://b/a",
        "https://b/a",
        "/tmp/a",
        "b/a",
    ],
)
def test_something_that_is_not_a_blob_uri_is_refused(uri):
    with pytest.raises(ValueError, match="not a blob URI"):
        split_uri(uri)
    with pytest.raises(ValueError, match="not a blob URI"):
        MemoryBlobs().exists(uri)


def test_a_blob_uri_splits_into_its_container_and_name():
    assert split_uri("az://clips/vp/v1/words/rain.mp3") == (
        "az",
        "clips",
        "vp/v1/words/rain.mp3",
    )
    assert split_uri("gs://aloai-dev-audio/s/READING/a.flac") == (
        "gs",
        "aloai-dev-audio",
        "s/READING/a.flac",
    )


def test_a_blob_uri_is_built_for_the_chosen_cloud():
    assert blob_uri("gcp", "aloai-audio", "s/a.flac") == "gs://aloai-audio/s/a.flac"
    assert blob_uri("azure", "audio", "s/a.flac") == "az://audio/s/a.flac"
    with pytest.raises(ValueError, match="unknown cloud"):
        blob_uri("aws", "b", "a")


# ---- events on Azure


def _event(name="event.session_done.json"):
    return json.loads((ROOT / "fixtures" / "contracts" / name).read_text())


class SenderFake:
    def __init__(self, sent, queue):
        self._sent, self._queue = sent, queue

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_messages(self, message):
        self._sent.append((self._queue, message))


class MessageFake:
    def __init__(self, payload):
        self.body = iter([payload]) if isinstance(payload, bytes) else payload


class ReceiverFake:
    def __init__(self, messages):
        self.pending = list(messages)
        self.completed, self.abandoned = [], []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def receive_messages(self, max_message_count, max_wait_time):
        assert max_message_count == 1
        return [self.pending.pop(0)] if self.pending else []

    def complete_message(self, message):
        self.completed.append(message)

    def abandon_message(self, message):
        self.abandoned.append(message)


class BusFake:
    def __init__(self, receivers=()):
        self.sent, self.receivers, self.opened = [], list(receivers), []

    def get_queue_sender(self, queue_name):
        return SenderFake(self.sent, queue_name)

    def get_queue_receiver(self, queue_name, **options):
        self.opened.append((queue_name, sorted(options)))
        return self.receivers.pop(0)


def test_an_event_goes_to_the_queue_of_every_service_that_handles_its_type():
    bus = BusFake()
    routes = {
        "session.done": ("core-events",),
        "phase1.recorded": ("scorer-events", "audit"),
    }
    publisher = ServiceBusPublisher(bus, routes)
    event = _event()
    publisher.publish(event)
    [(queue, message)] = bus.sent
    assert queue == "core-events"
    assert json.loads(b"".join(message.body)) == event
    assert message.message_id == event["event_id"]
    assert message.content_type == "application/json"
    assert {str(k): v for k, v in message.application_properties.items()} == {
        "type": "session.done"
    }
    bus.sent.clear()
    publisher.publish(_event("event.phase1_recorded.json"))
    assert [queue for queue, _ in bus.sent] == ["scorer-events", "audit"]


def test_an_event_no_service_handles_goes_nowhere():
    bus = BusFake()
    ServiceBusPublisher(bus, {"session.done": ("core-events",)}).publish(
        _event("event.session_started.json")
    )
    assert bus.sent == []


def test_a_message_is_read_back_as_the_event_it_carries():
    event = _event()
    assert bus_event(MessageFake(json.dumps(event).encode())) == event


@pytest.mark.parametrize(
    "message",
    [
        MessageFake(b"not json"),
        MessageFake(b'{"type": "session.done"}'),
        MessageFake(b'{"type": "mystery"}'),
        SimpleNamespace(body=None),
    ],
)
def test_a_message_that_is_not_a_valid_event_is_none(message):
    assert bus_event(message) is None


def test_a_handled_message_is_completed_and_a_failed_one_is_abandoned():
    good, bad = _event(), _event("event.phase1_recorded.json")
    receiver = ReceiverFake([MessageFake(json.dumps(good).encode())])
    handled = []
    assert pump_once(receiver, handled.append) == 1
    assert (handled, len(receiver.completed), receiver.abandoned) == ([good], 1, [])

    def fails(event):
        raise OSError("the grader is down")

    receiver = ReceiverFake([MessageFake(json.dumps(bad).encode())])
    assert pump_once(receiver, fails) == 0
    assert (receiver.completed, len(receiver.abandoned)) == ([], 1)


def test_a_message_that_is_not_an_event_is_completed_without_asking_the_handler():
    receiver = ReceiverFake([MessageFake(b"junk")])
    handled = []
    assert pump_once(receiver, handled.append) == 1
    assert (handled, len(receiver.completed), receiver.abandoned) == ([], 1, [])


def test_an_empty_queue_completes_nothing():
    assert pump_once(ReceiverFake([]), lambda event: None) == 0


def _messages(*events):
    return [MessageFake(json.dumps(event).encode()) for event in events]


def test_the_pump_hands_events_to_the_handler_until_it_is_stopped():
    receiver = ReceiverFake(_messages(_event(), _event("event.phase1_scored.json")))
    seen, both = [], threading.Event()

    def handle(event):
        seen.append(event["type"])
        if len(seen) == 2:
            both.set()

    pump = QueuePump(lambda: receiver, handle, wait_s=0.01)
    pump.start()
    assert both.wait(5)
    pump.stop()
    assert seen == ["session.done", "phase1.scored"]
    assert len(receiver.completed) == 2


def test_the_pump_opens_its_receiver_again_after_an_error():
    broken = ReceiverFake(_messages(_event()))
    broken.receive_messages = lambda **_: (_ for _ in ()).throw(
        ConnectionError("dropped")
    )
    healthy = ReceiverFake(_messages(_event("event.phase1_scored.json")))
    receivers, seen, done = [broken, healthy], [], threading.Event()

    def handle(event):
        seen.append(event["type"])
        done.set()

    pump = QueuePump(lambda: receivers.pop(0), handle, wait_s=0.01, retry_s=0.01)
    pump.start()
    assert done.wait(5)
    pump.stop()
    assert seen == ["phase1.scored"]


def test_a_service_bus_pump_reads_its_queue_and_renews_the_lock_while_the_handler_runs():
    receiver = ReceiverFake(_messages(_event()))
    bus = BusFake([receiver])
    done = threading.Event()
    pump = service_bus_pump(bus, "core-events", lambda event: done.set(), lock_s=600)
    pump.start()
    assert done.wait(5)
    pump.stop()
    assert bus.opened == [("core-events", ["auto_lock_renewer"])]


# ---- service to service


CALLER = "11111111-1111-1111-1111-111111111111"
TENANT = "22222222-2222-2222-2222-222222222222"
AUDIENCE = "api://aloai-core"


@pytest.mark.parametrize(
    "authorization, claims, allowed",
    [
        ("Bearer t", {"aud": AUDIENCE, "tid": TENANT, "oid": CALLER}, True),
        ("Bearer t", {"aud": "api://other", "tid": TENANT, "oid": CALLER}, False),
        ("Bearer t", {"aud": AUDIENCE, "tid": "other-tenant", "oid": CALLER}, False),
        ("Bearer t", {"aud": AUDIENCE, "tid": TENANT, "oid": "someone-else"}, False),
        ("Bearer t", {"aud": AUDIENCE, "tid": TENANT}, False),
        ("Basic t", {"aud": AUDIENCE, "tid": TENANT, "oid": CALLER}, False),
        (None, {}, False),
    ],
)
def test_a_call_must_carry_an_entra_token_for_this_service_from_an_allowed_identity(
    authorization, claims, allowed
):
    check = entra_caller(
        AUDIENCE, TENANT, {CALLER}, verify=lambda token, audience: claims
    )
    assert check(authorization) is allowed


def test_the_entra_check_asks_for_this_services_audience_and_refuses_a_forged_token():
    asked = []

    def verify(token, audience):
        asked.append((token, audience))
        return {"aud": AUDIENCE, "tid": TENANT, "oid": CALLER}

    assert entra_caller(AUDIENCE, TENANT, {CALLER}, verify)("Bearer abc")
    assert asked == [("abc", AUDIENCE)]

    def forged(token, audience):
        raise ValueError("Signature verification failed")

    assert entra_caller(AUDIENCE, TENANT, {CALLER}, forged)("Bearer forged") is False


def test_events_still_build_with_the_same_envelope_on_either_cloud():
    event = envelope("session.done", "sess_demo_001", _event()["data"], now=NOW)
    assert event["schema_version"] == 3
    assert bus_event(MessageFake(json.dumps(event).encode())) == event


# ---- helpers every backend shares


def test_a_missing_document_is_a_lookup_error_when_it_is_required():
    store = MemoryStore({"children/c": {"primary_class": 2}})
    assert require(store, "children/c") == {"primary_class": 2}
    with pytest.raises(LookupError, match="no document children/x"):
        require(store, "children/x")


def test_the_memory_publisher_keeps_what_it_is_given():
    publisher = MemoryPublisher()
    publisher.publish(_event())
    assert publisher.events == [_event()]


def test_a_push_body_is_read_back_as_the_event_it_carries():
    event = _event()
    body = {"message": {"data": base64.b64encode(json.dumps(event).encode()).decode()}}
    assert pushed_event(body) == event
    assert pushed_event({"message": {"data": "%%%"}}) is None
    assert pushed_event({}) is None


def test_off_the_cloud_anyone_may_call():
    assert anyone(None) is True


# ---- the app lifespan


class PumpFake:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def _azure(**more):
    return aloai_env.load({"ALO_ENV": "local", "CLOUD": "azure"} | more)


def test_the_event_queue_is_read_from_the_environment():
    assert _azure(EVENT_QUEUE="core-events").event_queue == "core-events"
    assert _azure().event_queue is None


def test_on_azure_the_app_pumps_its_own_queue_into_the_handler_while_it_runs():
    pump, opened = PumpFake(), []

    def open_pump(config, queue, handle):
        opened.append((config.cloud, queue, handle))
        return pump

    def handle(event):
        pass

    lifespan = pump_lifespan(_azure(EVENT_QUEUE="core-events"), handle, open_pump)

    async def run():
        async with lifespan(None):
            assert pump.running is True

    asyncio.run(run())
    assert opened == [("azure", "core-events", handle)]
    assert pump.running is False


def test_the_pump_is_stopped_when_the_app_fails():
    pump = PumpFake()
    lifespan = pump_lifespan(
        _azure(EVENT_QUEUE="core-events"), lambda event: None, lambda *args: pump
    )

    async def run():
        async with lifespan(None):
            raise RuntimeError("the app failed")

    with pytest.raises(RuntimeError, match="the app failed"):
        asyncio.run(run())
    assert pump.running is False


def test_on_gcp_nothing_is_pumped_because_pub_sub_pushes():
    def open_pump(*args):
        raise AssertionError("pumped")

    lifespan = pump_lifespan(
        aloai_env.load({"EVENT_QUEUE": "core-events"}), lambda e: None, open_pump
    )

    async def run():
        async with lifespan(None):
            pass

    asyncio.run(run())


def test_on_azure_a_missing_queue_fails_at_start_not_on_the_first_event():
    with pytest.raises(aloai_env.ConfigError, match="EVENT_QUEUE"):
        pump_lifespan(_azure(), lambda event: None)
