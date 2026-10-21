"""Events the Alo.ai services publish (SDD 11): Pub/Sub on GCP, Service Bus on Azure.

On GCP, one topic, aloai.session-events, typed by the "type" attribute, with at-least-once
delivery. PubSubPublisher uses the emulator when PUBSUB_EMULATOR_HOST is set. Each service
receives events through its own push subscription (pushed_event). Pub/Sub redelivers
anything a push endpoint does not acknowledge, so an event that can never be handled is
parked (park) and acknowledged instead.

On Azure there is no topic: ServiceBusPublisher sends each event to the queue of every
service that handles its type (infra/events.json: queue -> event types, handed to the app
as EVENT_ROUTES), and each service pulls its own queue (QueuePump). A handler that returns
completes the message and one that raises abandons it, so Service Bus redelivers it and
then moves it to the dead-letter queue, as Pub/Sub does. Event handlers are the same on
both clouds: one function that parks what can never succeed and raises for the rest.

Every publication of one session's event carries the same event_id (stable_event_id), so
consumers drop repeats by it. MemoryPublisher stands in for both clouds in tests. Each
cloud's SDK is imported only when its client is built.
"""

import base64
import json
import logging
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

import aloai_contracts
from aloai_env import Config, ConfigError, require_setting
from aloai_service_auth import ServiceCheck, google_caller
from aloai_service_auth import anyone as anyone
from aloai_store import Store

if TYPE_CHECKING:
    from google.cloud import pubsub_v1

log = logging.getLogger(__name__)

TOPIC = "aloai.session-events"
SCHEMA_VERSIONS = {
    "session.started": 1,
    "phase1.recorded": 2,
    "session.done": 3,
    "phase1.scored": 1,
    "report.ready": 1,
    "plan.ready": 1,
}
EVENT_IDS = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/dave-manufor/alo-ai/events")
PushCheck = ServiceCheck  # the push routes import PushCheck and anyone from here


class Publisher(Protocol):
    def publish(self, event: dict) -> None: ...


class MemoryPublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)


def _wire(event: dict) -> str:
    return json.dumps(event, separators=(",", ":"))


class PubSubPublisher:
    def __init__(self, client: "pubsub_v1.PublisherClient", project: str) -> None:
        self._client = client
        self._topic = client.topic_path(project, TOPIC)

    def publish(self, event: dict) -> None:
        self._client.publish(self._topic, _wire(event).encode(), type=event["type"]).result()


class ServiceBusPublisher:
    def __init__(self, client, routes: Mapping[str, Sequence[str]]) -> None:
        """client is an azure.servicebus.ServiceBusClient; routes maps an event type to
        the queues that handle it. A type no queue handles (session.started) goes nowhere."""
        self._client = client
        self._routes = routes

    def publish(self, event: dict) -> None:
        from azure.servicebus import ServiceBusMessage

        for queue in self._routes.get(event["type"], ()):
            message = ServiceBusMessage(
                _wire(event),
                content_type="application/json",
                message_id=event["event_id"],
                application_properties={"type": event["type"]},
            )
            with self._client.get_queue_sender(queue_name=queue) as sender:
                sender.send_messages(message)


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


def bus_event(message: Any) -> dict | None:
    """The event in a Service Bus message, or None when it is not a valid event."""
    try:
        event = json.loads(b"".join(bytes(part) for part in message.body))
    except (TypeError, ValueError):
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


def pushed_by(
    service_account: str,
    audience: str | None = None,
    verify: Callable[[str, str | None], Mapping[str, Any]] | None = None,
) -> PushCheck:
    """A check that a push carries a Google-signed ID token for the push service account
    (aloai_service_auth.google_caller)."""
    return google_caller(service_account, audience, verify)


Handler = Callable[[dict], None]


def pump_once(receiver: Any, handle: Handler, *, wait_s: float = 5) -> int:
    """Receive one message from a queue and settle it. A message that is not a valid event
    is completed (and logged), as a push that is not one is acknowledged. A handler that
    returns completes the message; one that raises abandons it, for Service Bus to deliver
    again and then dead-letter. Returns how many messages were completed."""
    completed = 0
    for message in receiver.receive_messages(max_message_count=1, max_wait_time=wait_s):
        event = bus_event(message)
        if event is None:
            log.warning("completed a message that is not a valid event")
        else:
            try:
                handle(event)
            except Exception as error:
                log.error("abandoned %s: %s", event["type"], type(error).__name__)
                receiver.abandon_message(message)
                continue
        receiver.complete_message(message)
        completed += 1
    return completed


class QueuePump:
    """Takes the events of one queue on a background thread and hands each to `handle`,
    the way a push route does on GCP. open_receiver returns a context manager around a
    receiver; it is opened again if the connection drops."""

    def __init__(
        self,
        open_receiver: Callable[[], AbstractContextManager],
        handle: Handler,
        *,
        wait_s: float = 5,
        retry_s: float = 5,
    ) -> None:
        self._open = open_receiver
        self._handle = handle
        self._wait_s = wait_s
        self._retry_s = retry_s
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, name="queue-pump", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 30) -> None:
        self._stopping.set()
        self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                with self._open() as receiver:
                    while not self._stopping.is_set():
                        pump_once(receiver, self._handle, wait_s=self._wait_s)
            except Exception as error:
                log.error("queue pump stopped: %s", type(error).__name__)
                self._stopping.wait(self._retry_s)


def service_bus_pump(client, queue: str, handle: Handler, *, lock_s: float = 600) -> QueuePump:
    """A pump over one Service Bus queue. The lock is renewed while the handler runs, up to
    lock_s: as long as the 600 s Pub/Sub acknowledgement deadline (grading takes a while)."""
    from azure.servicebus import AutoLockRenewer

    @contextmanager
    def open_receiver():
        renewer = AutoLockRenewer(max_lock_renewal_duration=lock_s)
        try:
            with client.get_queue_receiver(queue_name=queue, auto_lock_renewer=renewer) as receiver:
                yield receiver
        finally:
            renewer.close()

    return QueuePump(open_receiver, handle)


def open_publisher(config: Config) -> Publisher:  # pragma: no cover - builds a real client
    """The publisher for this cloud (see open_store for how each finds its credentials)."""
    if config.cloud == "gcp":
        from google.cloud import pubsub_v1

        return PubSubPublisher(pubsub_v1.PublisherClient(), config.project)
    routes = config.event_routes
    if routes is None:
        raise ConfigError("EVENT_ROUTES must be set")
    return ServiceBusPublisher(_service_bus(config), routes)


def _service_bus(config: Config):  # pragma: no cover - builds a real client
    from azure.servicebus import ServiceBusClient

    if config.servicebus_connection_string:
        return ServiceBusClient.from_connection_string(config.servicebus_connection_string)
    from azure.identity import DefaultAzureCredential

    namespace = require_setting(config.servicebus_namespace, "AZURE_SERVICEBUS_NAMESPACE")
    return ServiceBusClient(f"{namespace}.servicebus.windows.net", DefaultAzureCredential())


def open_queue_pump(config: Config, queue: str, handle: Handler) -> QueuePump:  # pragma: no cover
    """The pump a service starts for its own queue when CLOUD=azure."""
    return service_bus_pump(_service_bus(config), queue, handle)
