"""Test data and fakes for the Core service.

The session is the fictional sess_demo_001 on the Market Day passage, built from
fixtures/contracts/ and the recorded responses in fixtures/ai/.
"""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

from services.core.events import MemoryPublisher, envelope
from services.core.grader import paths
from services.core.grader.assembly import ReportAssembler
from services.core.grader.models import FixtureGradingModel, GradingTask
from services.core.store import MemoryStore

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "fixtures" / "contracts"
RECORDED = ROOT / "fixtures" / "ai"
SESSION_ID = "sess_demo_001"
PASSAGE_ID = "bank_p3_market_day"
NOW = datetime(2026, 1, 15, 9, 9, 5, tzinfo=UTC)
AUDIO = "gs://aloai-dev-audio/3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10"


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text())


def seeded_store() -> MemoryStore:
    session = contract("session_record.session.json") | {
        "session_profile": "demo",
        "flags": ["DEMO_PROFILE"],
        "voice_profile_id": "vp_google_v1",
    }
    return MemoryStore(
        {
            paths.session(SESSION_ID): session,
            paths.child("child_demo_001"): {"guardian_id": "guardian_demo_001", "primary_class": 2},
            paths.passage(PASSAGE_ID): contract("passage.bank_p3_market_day.json"),
        }
    )


def add_telemetry(store: MemoryStore) -> None:
    store.set(paths.telemetry(SESSION_ID), contract("phase1_telemetry.sess_demo_001.json"))


def turn(number: int, phase: str) -> dict:
    return {
        "turn_id": f"turn_{number:03d}",
        "phase": phase,
        "audio_uri": f"{AUDIO}/{phase}/a1b2c3d4-0000-4000-8000-{number:012d}.flac",
    }


def session_done(**changes) -> dict:
    """session.done data for a demo session whose listening module ran."""
    turns = [
        turn(1, "READING"),
        turn(11, "RETELL"),
        turn(12, "RETELL"),
        turn(13, "QUESTION"),
        turn(14, "QUESTION"),
        turn(15, "LISTENING_RETELL"),
        turn(16, "LISTENING_QUESTION"),
    ]
    return {
        "session_id": SESSION_ID,
        "turn_audio_uris": turns,
        "capture_mode": "LIVE",
        "session_settings": {"voice_mode": "cache_first", "session_profile": "demo"},
        "flags": ["DEMO_PROFILE"],
        "listening_module_run": True,
    } | changes


def quick_request(turn_phase: str, index: int, transcript: str) -> dict:
    return {
        "schema_version": 1,
        "session_id": SESSION_ID,
        "passage_id": PASSAGE_ID,
        "turn_phase": turn_phase,
        "index": index,
        "transcript": transcript,
    }


def event(event_type: str, data: dict) -> dict:
    return envelope(
        event_type, SESSION_ID, data, event_id="6f1c2f0e-3a55-4a7e-9d1a-2b8c5e0a1009", now=NOW
    )


def pushed(message: dict) -> dict:
    """A Pub/Sub push request body carrying one event."""
    data = base64.b64encode(json.dumps(message).encode()).decode()
    return {
        "message": {"data": data, "attributes": {"type": message["type"]}, "messageId": "1"},
        "subscription": "projects/aloai-dev/subscriptions/core-session-events",
    }


def assembler(store: MemoryStore, publisher: MemoryPublisher) -> ReportAssembler:
    return ReportAssembler(
        store,
        publisher,
        clock=lambda: NOW,
        new_event_id=lambda: "6f1c2f0e-3a55-4a7e-9d1a-2b8c5e0a1005",
    )


def grader_output(
    propositions: dict[str, float], items: dict[str, int], passage_id: str = PASSAGE_ID
) -> dict:
    return {
        "passage_id": passage_id,
        "propositions": [
            {"id": pid, "credit": credit, "evidence": None} for pid, credit in propositions.items()
        ],
        "items": [
            {
                "item_id": iid,
                "points": points,
                "evidence": None,
                "rationale": "",
                "needs_review": False,
            }
            for iid, points in items.items()
        ],
        "inaccuracies": [],
        "needs_review": False,
    }


class RecordedModel:
    """The recorded responses, noting which calls were made."""

    def __init__(self) -> None:
        self._inner = FixtureGradingModel(RECORDED / "grader")
        self.keys: list[str] = []

    def grade(self, task: GradingTask) -> dict:
        self.keys.append(task.key)
        return self._inner.grade(task)


class ScriptedModel:
    """Answers each call key with a given GraderOutput."""

    def __init__(self, outputs: dict[str, dict]) -> None:
        self._outputs = outputs
        self.tasks: list[GradingTask] = []

    def grade(self, task: GradingTask) -> dict:
        self.tasks.append(task)
        return self._outputs[task.key]
