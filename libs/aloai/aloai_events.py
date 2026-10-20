"""Events the Alo.ai services publish on aloai.session-events (SDD 11).

One topic, typed by the "type" attribute, with at-least-once delivery. Every
publication of one session's event carries the same event_id (stable_event_id), so
consumers drop repeats by it. PubSubPublisher uses the emulator when
PUBSUB_EMULATOR_HOST is set; MemoryPublisher stands in for it in tests. Each service
receives events through its own push subscription (pushed_event). Pub/Sub redelivers
anything a push endpoint does not acknowledge, so an event that can never be handled
is parked (park) and acknowledged instead.
"""

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from google.cloud import pubsub_v1

import aloai_contracts
from aloai_store import Store

TOPIC = "aloai.session-events"
SCHEMA_VERSIONS = {
    "session.started": 1,
    "phase1.recorded": 1,
    "session.done": 2,
    "phase1.scored": 1,
    "report.ready": 1,
    "plan.ready": 1,
}
EVENT_IDS = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/dave-manufor/alo-ai/events")


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


def stable_event_id(session_id: str, event_type: str) -> str:
    return str(uuid.uuid5(EVENT_IDS, f"{session_id}/{event_type}"))


def envelope(
    event_type: str, session_id: str, data: dict, *, now: datetime, event_id: str | None = None
) -> dict:
    """The event, checked against the envelope schema; event_id defaults to the stable one."""
    event = {
        "event_id": event_id or stable_event_id(session_id, event_type),
        "type": event_type,
        "schema_version": SCHEMA_VERSIONS[event_type],
        "occurred_at": iso_utc(now),
        "session_id": session_id,
        "data": data,
    }
    aloai_contracts.EVENT_ENVELOPE.validate(event)
    return event


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def pushed_event(body: Any) -> dict | None:
    """The event inside a Pub/Sub push body, or None when it is not a valid event."""
    try:
        event = json.loads(base64.b64decode(body["message"]["data"], validate=True))
    except (KeyError, TypeError, ValueError):
        return None
    return event if aloai_contracts.EVENT_ENVELOPE.is_valid(event) else None


def park(store: Store, event: dict, error: Exception, now: datetime) -> str:
    """Keep an event that can never succeed where a person can look at it and replay it.
    The path is sessions/{session_id}/errors/{type}; the message is not logged."""
    path = f"sessions/{event['session_id']}/errors/{event['type']}"
    store.set(
        path,
        {
            "event_id": event["event_id"],
            "type": event["type"],
            "error": type(error).__name__,
            "message": str(error)[:2000],
            "at": iso_utc(now),
        },
    )
    return path
