"""Events the Core service publishes on aloai.session-events (SDD 11).

One topic, typed by the "type" attribute, with at-least-once delivery, so consumers
drop duplicates by event_id. PubSubPublisher uses the emulator when
PUBSUB_EMULATOR_HOST is set; MemoryPublisher stands in for it in tests.
"""

import json
from datetime import UTC, datetime
from typing import Protocol

from google.cloud import pubsub_v1

TOPIC = "aloai.session-events"
SCHEMA_VERSION = 1


class Publisher(Protocol):
    def publish(self, event: dict) -> None: ...


class MemoryPublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)


class PubSubPublisher:
    def __init__(self, client: pubsub_v1.PublisherClient, project: str) -> None:
        self._client = client
        self._topic = client.topic_path(project, TOPIC)

    def publish(self, event: dict) -> None:
        data = json.dumps(event, separators=(",", ":")).encode()
        self._client.publish(self._topic, data, type=event["type"]).result()


def envelope(event_type: str, session_id: str, data: dict, *, event_id: str, now: datetime) -> dict:
    return {
        "event_id": event_id,
        "type": event_type,
        "schema_version": SCHEMA_VERSION,
        "occurred_at": iso_utc(now),
        "session_id": session_id,
        "data": data,
    }


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")
