"""Google Cloud clients behind the small interfaces the session uses.

Cloud Storage (turn audio, clips), Firestore (session records, bank passages) and
Pub/Sub (events). Locally the same code talks to the emulators, which the client
libraries pick up from STORAGE_EMULATOR_HOST, FIRESTORE_EMULATOR_HOST and
PUBSUB_EMULATOR_HOST. Not unit-tested: these are thin calls, exercised in the
end-to-end run against the emulators.
"""

import json
import os

from google.api_core.exceptions import PreconditionFailed
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore, pubsub_v1, storage

EVENTS_TOPIC = "aloai.session-events"


def storage_client(project: str) -> storage.Client:  # pragma: no cover
    if os.environ.get("STORAGE_EMULATOR_HOST"):
        return storage.Client(project=project, credentials=AnonymousCredentials())
    return storage.Client(project=project)


class GcsBucket:  # pragma: no cover
    """A bucket for the clip store (clips/store.Bucket) and for turn audio."""

    def __init__(self, client: storage.Client, name: str) -> None:
        self._bucket = client.bucket(name)

    def exists(self, name: str) -> bool:
        return self._bucket.blob(name).exists()

    def upload_if_absent(self, name: str, data: bytes, content_type: str) -> bool:
        try:
            self._bucket.blob(name).upload_from_string(
                data, content_type=content_type, if_generation_match=0
            )
        except PreconditionFailed:
            return False
        return True

    def upload(self, name: str, data: bytes, content_type: str) -> None:
        self._bucket.blob(name).upload_from_string(data, content_type=content_type)


class FirestoreDocuments:  # pragma: no cover
    """session_store.Documents, and passage reads for the bank."""

    def __init__(self, client: firestore.Client) -> None:
        self._client = client

    def set(self, path: str, data: dict) -> None:
        self._client.document(path).set(data)

    def merge(self, path: str, data: dict) -> None:
        self._client.document(path).set(data, merge=True)

    def get(self, path: str) -> dict | None:
        snapshot = self._client.document(path).get()
        return snapshot.to_dict() if snapshot.exists else None


class PubSubPublisher:  # pragma: no cover
    """events.Publisher on the aloai.session-events topic. The type is also an
    attribute, so subscriptions can filter on it."""

    def __init__(self, project: str, topic: str = EVENTS_TOPIC) -> None:
        self._client = pubsub_v1.PublisherClient()
        self._topic = self._client.topic_path(project, topic)

    def publish(self, event: dict) -> None:
        data = json.dumps(event, separators=(",", ":")).encode()
        self._client.publish(self._topic, data, type=event["type"]).result(timeout=30)
