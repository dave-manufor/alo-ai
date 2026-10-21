"""Smoke test of the Azure deployment: a fake child takes a session to a finished report.

It starts a session the way the Account service will (a LiveKit room with the session
metadata; the Session Agent worker joins any new room), runs the fake child through it, waits
for the report and the parent plan to appear, and checks that both dead-letter queues are
empty. Exit status 0 only if every check passed. The data is fictional: one child
(child_smoke) of one guardian (guardian_smoke), and each run adds one session, one report and
one plan, which it leaves in place.

    CLOUD=azure AZURE_COSMOS_ENDPOINT=... AZURE_SERVICEBUS_NAMESPACE=... \
    AZURE_SPEECH_REGION=... AZURE_SPEECH_RESOURCE_ID=... \
    LIVEKIT_URL=wss://... LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... \
    PYTHONPATH=libs/aloai services/session_agent/.venv/bin/python \
        services/session_agent/tools/cloud_smoke.py

It uses your `az login` (Cosmos DB data contributor, and Service Bus data owner to read the
queue counts). Take the LiveKit key and secret from Key Vault (livekit-api-key,
livekit-api-secret) into the shell; do not write them to a file.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

EVENTS = Path(__file__).resolve().parents[3] / "infra" / "events.json"

CHILD_ID = "child_smoke"
GUARDIAN_ID = "guardian_smoke"
# What the Grader and the Coach read from children/{id}: the class, the guardian and the tags.
CHILD = {
    "guardian_id": GUARDIAN_ID,
    "primary_class": 3,
    "first_name": "Smoke",
    "saved_tags": ["food", "football"],
}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""

    def line(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}  {self.name}" + (
            f": {self.detail}" if self.detail else ""
        )


def queue_names(path: Path = EVENTS) -> list[str]:
    """The event queues, from infra/events.json (each has a dead-letter queue)."""
    return sorted(json.loads(path.read_text())["queues"])


def new_session_id() -> str:
    return f"sess_smoke_{uuid.uuid4().hex[:12]}"


def report_done(store, session_id: str) -> bool:
    """The report and the parent plan are written and the report has the parent's summary:
    the Grader wrote reports/{id}, then the Coach added the summary and plans/plan_{id}."""
    report = store.get(f"reports/{session_id}")
    plan = store.get(f"plans/plan_{session_id}")
    if report is None or plan is None:
        return False
    return bool((report.get("parent_reporting") or {}).get("summary_script"))


def wait_for(
    condition: Callable[[], bool],
    *,
    timeout_s: float,
    interval_s: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    deadline = clock() + timeout_s
    while True:
        if condition():
            return True
        if clock() >= deadline:
            return False
        sleep(interval_s)


def dead_letter_counts(admin, queues: list[str]) -> dict[str, int]:
    """Messages in each queue's dead-letter queue (ServiceBusAdministrationClient)."""
    return {
        queue: admin.get_queue_runtime_properties(queue).dead_letter_message_count
        for queue in queues
    }


def run_smoke(
    *,
    store,
    admin,
    queues: list[str],
    drive: Callable[[str, str], dict],
    timeout_s: float,
    interval_s: float = 5.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Check]:
    """drive(session_id, child_id) runs the fake child through one session and returns its
    result ({"ended": bool, ...}). Returns every check, passed or not."""
    session_id = new_session_id()
    store.set(f"children/{CHILD_ID}", CHILD)
    checks: list[Check] = []
    try:
        result = drive(session_id, CHILD_ID)
    except Exception as error:  # the room, the agent or the network: report it, then go on
        checks.append(Check("session ran", False, f"{type(error).__name__}: {error}"))
    else:
        detail = f"{session_id}, {result.get('messages', 0)} agent messages"
        checks.append(Check("session ran", bool(result.get("ended")), detail))
    reached = wait_for(
        lambda: report_done(store, session_id),
        timeout_s=timeout_s,
        interval_s=interval_s,
        clock=clock,
        sleep=sleep,
    )
    waited = f"within {timeout_s:.0f} s" if reached else f"not within {timeout_s:.0f} s"
    checks.append(Check("report and plan written", reached, f"{session_id} {waited}"))
    session = store.get(f"sessions/{session_id}") or {}
    checks.append(Check("session record", bool(session), f"status {session.get('status')}"))
    for queue, count in dead_letter_counts(admin, queues).items():
        checks.append(Check(f"dead-letter queue {queue} is empty", count == 0, f"{count} messages"))
    return checks


def main() -> int:  # pragma: no cover - builds real clients
    import aloai_env
    import aloai_store
    import fake_child
    from azure.identity import DefaultAzureCredential
    from azure.servicebus.management import ServiceBusAdministrationClient

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=300, help="seconds to wait for the report")
    parser.add_argument("--seconds", type=int, default=900, help="longest the fake child stays")
    parser.add_argument("--voice", default=fake_child.DEFAULT_VOICE)
    parser.add_argument(
        "--silent", action="store_true", help="a silent child (the session ends early)"
    )
    args = parser.parse_args()

    env = dict(os.environ)
    config = aloai_env.load(env, receives_pushes=False)
    namespace = aloai_env.require_setting(config.servicebus_namespace, "AZURE_SERVICEBUS_NAMESPACE")
    admin = ServiceBusAdministrationClient(
        f"{namespace}.servicebus.windows.net", DefaultAzureCredential()
    )
    speak = None if args.silent else fake_child.azure_speaker(env, args.voice)
    url = aloai_env.require_setting(env.get("LIVEKIT_URL"), "LIVEKIT_URL")
    key = aloai_env.require_setting(env.get("LIVEKIT_API_KEY"), "LIVEKIT_API_KEY")
    secret = aloai_env.require_setting(env.get("LIVEKIT_API_SECRET"), "LIVEKIT_API_SECRET")

    def drive(session_id: str, child_id: str) -> dict:
        metadata = {"session_id": session_id, "child_id": child_id, "context": "HOME"}
        return asyncio.run(
            fake_child.run_session(
                url=url,
                key=key,
                secret=secret,
                room_name=f"alo-{session_id}",
                metadata=metadata,
                speak=speak,
                seconds=args.seconds,
            )
        )

    checks = run_smoke(
        store=aloai_store.open_store(config),
        admin=admin,
        queues=queue_names(),
        drive=drive,
        timeout_s=args.timeout,
    )
    for check in checks:
        print(check.line())
    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
