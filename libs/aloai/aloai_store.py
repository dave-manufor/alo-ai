"""Firestore documents for the Alo.ai services (SDD 12).

Paths are full document paths such as "sessions/{session_id}". FirestoreStore talks
to Firestore, or to its emulator when FIRESTORE_EMULATOR_HOST is set; MemoryStore
stands in for it in tests. merge works as Firestore's set(merge=True): nested maps are
merged field by field, and any other value, a list included, is replaced.
"""

import copy
from typing import Any, Protocol

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class Store(Protocol):
    def get(self, path: str) -> dict | None: ...

    def set(self, path: str, data: dict) -> None: ...

    def merge(self, path: str, data: dict) -> None: ...

    def create(self, path: str, data: dict) -> bool:
        """Write only if the document does not exist. True if this call wrote it."""
        ...

    def where(self, collection: str, field: str, value: Any) -> list[dict]: ...


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


def _merged(base: dict, changes: dict) -> dict:
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merged(merged[key], value)
        else:
            merged[key] = value
    return merged


class FirestoreStore:
    def __init__(self, client: firestore.Client) -> None:
        self._client = client

    def get(self, path: str) -> dict | None:
        snapshot = self._client.document(path).get()
        return snapshot.to_dict() if snapshot.exists else None

    def set(self, path: str, data: dict) -> None:
        self._client.document(path).set(data)

    def merge(self, path: str, data: dict) -> None:
        self._client.document(path).set(data, merge=True)

    def create(self, path: str, data: dict) -> bool:
        try:
            self._client.document(path).create(data)
        except AlreadyExists:
            return False
        return True

    def where(self, collection: str, field: str, value: Any) -> list[dict]:
        query = self._client.collection(collection).where(filter=FieldFilter(field, "==", value))
        return [snapshot.to_dict() for snapshot in query.stream()]
