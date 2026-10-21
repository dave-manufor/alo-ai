"""Documents for the Alo.ai services (SDD 12): Firestore on GCP, Cosmos DB on Azure.

Paths are full document paths such as "sessions/{session_id}". FirestoreStore talks
to Firestore, or to its emulator when FIRESTORE_EMULATOR_HOST is set; CosmosStore talks to
Cosmos DB for NoSQL; MemoryStore stands in for both in tests. Each cloud's SDK is imported
only when its store is used. merge works as Firestore's set(merge=True): nested maps are
merged field by field, and any other value, a list included, is replaced.

CosmosStore keeps each document in an item {"id", "pk", "col", "d"}: id is the path with "/"
as "|" (Cosmos ids cannot hold "/"), pk is the top-level document ("sessions/{id}", so a
session and its turns share a partition), col is the collection the document is in (so
where() can find it), and d is the document itself, apart from the keys Cosmos adds. A
collection in `dedicated` (books, which has a vector index) lives in its own container.
"""

import copy
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Protocol

from aloai_env import Config, require_setting

if TYPE_CHECKING:
    from google.cloud import firestore

MERGE_ATTEMPTS = 8
FIELD_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


class Store(Protocol):
    def get(self, path: str) -> dict | None: ...

    def get_many(self, paths: Sequence[str]) -> list[dict | None]:
        """The documents in the order asked, in one round trip."""
        ...

    def set(self, path: str, data: dict) -> None: ...

    def merge(self, path: str, data: dict) -> None: ...

    def create(self, path: str, data: dict) -> bool:
        """Write only if the document does not exist. True if this call wrote it."""
        ...

    def where(self, collection: str, field: str, value: Any) -> list[dict]: ...

    def delete(self, path: str) -> bool:
        """Remove one document, not the collections under it. True if it existed."""
        ...

    def list_paths(self, collection: str) -> list[str]:
        """The paths of the documents directly in a collection, such as
        "sessions/s1/turns", whatever they hold."""
        ...


def require(store: Store, path: str) -> dict:
    document = store.get(path)
    if document is None:
        raise LookupError(f"no document {path}")
    return document


class MemoryStore:
    def __init__(self, docs: dict[str, dict] | None = None) -> None:
        self.docs: dict[str, dict] = {} if docs is None else docs

    def get(self, path: str) -> dict | None:
        return copy.deepcopy(self.docs.get(path))

    def get_many(self, paths: Sequence[str]) -> list[dict | None]:
        return [self.get(path) for path in paths]

    def set(self, path: str, data: dict) -> None:
        self.docs[path] = copy.deepcopy(data)

    def merge(self, path: str, data: dict) -> None:
        self.docs[path] = _merged(self.docs.get(path, {}), copy.deepcopy(data))

    def create(self, path: str, data: dict) -> bool:
        if path in self.docs:
            return False
        self.set(path, data)
        return True

    def where(self, collection: str, field: str, value: Any) -> list[dict]:
        prefix = f"{collection}/"
        return [
            copy.deepcopy(doc)
            for path, doc in self.docs.items()
            if path.startswith(prefix)
            and "/" not in path[len(prefix) :]
            and doc.get(field) == value
        ]

    def delete(self, path: str) -> bool:
        return self.docs.pop(path, None) is not None

    def list_paths(self, collection: str) -> list[str]:
        prefix = f"{collection}/"
        return [
            path
            for path in self.docs
            if path.startswith(prefix) and "/" not in path[len(prefix) :]
        ]


def _merged(base: dict, changes: dict) -> dict:
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merged(merged[key], value)
        else:
            merged[key] = value
    return merged


class FirestoreStore:
    def __init__(self, client: "firestore.Client") -> None:
        self._client = client

    def get(self, path: str) -> dict | None:
        snapshot = self._client.document(path).get()
        return snapshot.to_dict() if snapshot.exists else None

    def get_many(self, paths: Sequence[str]) -> list[dict | None]:
        snapshots = self._client.get_all([self._client.document(path) for path in paths])
        found = {s.reference.path: s.to_dict() for s in snapshots if s.exists}
        return [found.get(path) for path in paths]

    def set(self, path: str, data: dict) -> None:
        self._client.document(path).set(data)

    def merge(self, path: str, data: dict) -> None:
        self._client.document(path).set(data, merge=True)

    def create(self, path: str, data: dict) -> bool:
        from google.api_core.exceptions import AlreadyExists

        try:
            self._client.document(path).create(data)
        except AlreadyExists:
            return False
        return True

    def where(self, collection: str, field: str, value: Any) -> list[dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._client.collection(collection).where(filter=FieldFilter(field, "==", value))
        return [snapshot.to_dict() for snapshot in query.stream()]

    def delete(self, path: str) -> bool:
        from google.api_core.exceptions import NotFound

        try:
            self._client.document(path).delete(option=self._client.write_option(exists=True))
        except NotFound:
            return False
        return True

    def list_paths(self, collection: str) -> list[str]:
        return [reference.path for reference in self._client.collection(collection).list_documents()]


class CosmosStore:
    def __init__(self, docs, dedicated: Mapping[str, Any] | None = None) -> None:
        """docs and each dedicated container are azure.cosmos ContainerProxy objects, with
        partition key /pk."""
        self._docs = docs
        self._dedicated = dict(dedicated or {})

    def _container(self, path: str):
        return self._dedicated.get(path.partition("/")[0], self._docs)

    @staticmethod
    def _key(path: str) -> tuple[str, str]:
        """(item id, partition key) of a document path."""
        parts = path.split("/")
        if len(parts) % 2 or not all(parts) or "|" in path:
            raise ValueError(f"not a document path: {path!r}")
        return "|".join(parts), "/".join(parts[:2])

    def _item(self, path: str, data: dict) -> dict:
        item_id, partition = self._key(path)
        return {"id": item_id, "pk": partition, "col": path.rpartition("/")[0], "d": data}

    def get(self, path: str) -> dict | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        item_id, partition = self._key(path)
        try:
            return self._container(path).read_item(item=item_id, partition_key=partition)["d"]
        except CosmosResourceNotFoundError:
            return None

    def get_many(self, paths: Sequence[str]) -> list[dict | None]:
        by_container: dict[int, tuple[Any, list[tuple[str, str]]]] = {}
        for path in paths:
            container = self._container(path)
            by_container.setdefault(id(container), (container, []))[1].append(self._key(path))
        found: dict[str, dict] = {}
        for container, keys in by_container.values():
            for item in container.read_items(items=keys):
                found[item["id"]] = item["d"]
        return [found.get(self._key(path)[0]) for path in paths]

    def set(self, path: str, data: dict) -> None:
        self._container(path).upsert_item(self._item(path, copy.deepcopy(data)))

    def merge(self, path: str, data: dict) -> None:
        """Read, merge and write back under the item's etag, again if another writer got
        in between, so two merges to one document never drop each other's fields."""
        from azure.core import MatchConditions
        from azure.cosmos.exceptions import (
            CosmosAccessConditionFailedError,
            CosmosResourceExistsError,
            CosmosResourceNotFoundError,
        )

        item_id, partition = self._key(path)
        container = self._container(path)
        for _ in range(MERGE_ATTEMPTS):
            try:
                current = container.read_item(item=item_id, partition_key=partition)
            except CosmosResourceNotFoundError:
                try:
                    container.create_item(self._item(path, copy.deepcopy(data)))
                    return
                except CosmosResourceExistsError:
                    continue
            item = self._item(path, _merged(current["d"], copy.deepcopy(data)))
            try:
                container.replace_item(
                    item=item_id,
                    body=item,
                    etag=current["_etag"],
                    match_condition=MatchConditions.IfNotModified,
                )
                return
            except CosmosAccessConditionFailedError:
                continue
        raise RuntimeError(f"could not merge into {path}: too many concurrent writers")

    def create(self, path: str, data: dict) -> bool:
        from azure.cosmos.exceptions import CosmosResourceExistsError

        try:
            self._container(path).create_item(self._item(path, copy.deepcopy(data)))
        except CosmosResourceExistsError:
            return False
        return True

    def where(self, collection: str, field: str, value: Any) -> list[dict]:
        if not FIELD_PATH.match(field):
            raise ValueError(f"not a field path: {field!r}")
        column = "c.d" + "".join(f'["{part}"]' for part in field.split("."))
        container = self._dedicated.get(collection.partition("/")[0], self._docs)
        parameters = [{"name": "@col", "value": collection}, {"name": "@value", "value": value}]
        return list(
            container.query_items(
                query=f"SELECT VALUE c.d FROM c WHERE c.col = @col AND {column} = @value",
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )

    def delete(self, path: str) -> bool:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        item_id, partition = self._key(path)
        try:
            self._container(path).delete_item(item=item_id, partition_key=partition)
        except CosmosResourceNotFoundError:
            return False
        return True

    def list_paths(self, collection: str) -> list[str]:
        container = self._dedicated.get(collection.partition("/")[0], self._docs)
        ids = container.query_items(
            query="SELECT VALUE c.id FROM c WHERE c.col = @col",
            parameters=[{"name": "@col", "value": collection}],
            enable_cross_partition_query=True,
        )
        # An item id is its path with "/" written as "|" (_key refuses a path that has one).
        return [item_id.replace("|", "/") for item_id in ids]


def open_store(config: Config) -> Store:  # pragma: no cover - builds a real client
    """The document store for this cloud. Google picks up Application Default Credentials
    (or FIRESTORE_EMULATOR_HOST); Azure uses the managed identity, or the emulator's key."""
    if config.cloud == "gcp":
        from google.cloud import firestore

        return FirestoreStore(firestore.Client(project=config.project))
    database = _cosmos_database(config)
    return CosmosStore(
        database.get_container_client("docs"),
        {"books": database.get_container_client("books")},
    )


def open_container(config: Config, name: str):  # pragma: no cover - builds a real client
    """A Cosmos DB container by name (azure only), for what the Store has no call for, such
    as the vector search on `books`."""
    return _cosmos_database(config).get_container_client(name)


def _cosmos_database(config: Config):  # pragma: no cover - builds a real client
    from azure.cosmos import CosmosClient

    endpoint = require_setting(config.cosmos_endpoint, "AZURE_COSMOS_ENDPOINT")
    if config.cosmos_key:
        client = CosmosClient(endpoint, config.cosmos_key, connection_verify=False)
    else:
        from azure.identity import DefaultAzureCredential

        client = CosmosClient(endpoint, DefaultAzureCredential())
    return client.get_database_client(config.cosmos_database)
