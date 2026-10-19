"""Test data and fakes for the Core service.

The session is the fictional sess_demo_001 on the Market Day passage, built from
fixtures/contracts/ and the recorded responses in fixtures/ai/.
"""

import base64
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import aloai_scoring as scoring
from aloai_events import MemoryPublisher, envelope
from aloai_store import MemoryStore
from fastapi import APIRouter
from services.core.api import events_router
from services.core.coach.agent import RecordedModel as RecordedCoach
from services.core.coach.clients import Outbox, SilentSpeaker, StoryRequests
from services.core.coach.run import ReadingCoach
from services.core.grader import paths
from services.core.grader.asr import FixtureTranscriber
from services.core.grader.assembly import ReportAssembler
from services.core.grader.books import BookRecommender, FixtureEmbedder
from services.core.grader.final import FinalGrader
from services.core.grader.models import FixtureGradingModel, GradingTask

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "fixtures" / "contracts"
RECORDED = ROOT / "fixtures" / "ai"
SESSION_ID = "sess_demo_001"
PASSAGE_ID = "bank_p3_market_day"
LISTEN_ID = "bank_l3_rain"
NOW = datetime(2026, 1, 15, 9, 9, 5, tzinfo=UTC)
AUDIO = "gs://aloai-dev-audio/3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10"
CHILD_ID = "child_demo_001"
GUARDIAN_ID = "guardian_demo_001"


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text())


# Fictional catalogue books. For the demo session ("food", band 1 to 2) they rank 001,
# 002, 003; 004 sits a level above the band and 005 is too far to be a candidate.
BOOKS = {
    "book_demo_001": {"arl": 2, "embedding": [0.9, 0.1, 0.0, 0.0], "west_african_setting": True},
    "book_demo_002": {"arl": 1, "embedding": [0.6, 0.8, 0.0, 0.0], "west_african_setting": True},
    "book_demo_003": {"arl": 2, "embedding": [0.8, 0.0, 0.6, 0.0], "west_african_setting": False},
    "book_demo_004": {"arl": 3, "embedding": [1.0, 0.0, 0.0, 0.0], "west_african_setting": True},
    "book_demo_005": {"arl": 6, "embedding": [1.0, 0.0, 0.0, 0.0], "west_african_setting": True},
}


def catalogue() -> dict[str, dict]:
    return {
        f"books/{book_id}": book | {"title": f"Demo Book {book_id[-1]}", "licence": "CC BY"}
        for book_id, book in BOOKS.items()
    }


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
            paths.passage(LISTEN_ID): contract("passage.bank_l3_rain.json"),
            **catalogue(),
        }
    )


class MemoryBookSearch:
    """Cosine similarity over the books in a MemoryStore, as Firestore's find_nearest."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def nearest(self, vector, levels, limit) -> list[scoring.BookCandidate]:
        candidates = [
            scoring.BookCandidate(
                book_id=path.removeprefix("books/"),
                arl=book["arl"],
                similarity=_cosine(vector, book["embedding"]),
                west_african=book.get("west_african_setting", False),
            )
            for path, book in self._store.docs.items()
            if path.startswith("books/") and book["arl"] in levels
        ]
        return sorted(candidates, key=lambda book: -book.similarity)[:limit]


def _cosine(a, b) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))


def recommender(store: MemoryStore) -> BookRecommender:
    return BookRecommender(MemoryBookSearch(store), FixtureEmbedder(RECORDED / "embeddings.json"))


def add_telemetry(store: MemoryStore) -> None:
    store.set(paths.telemetry(SESSION_ID), contract("phase1_telemetry.sess_demo_001.json"))


def turn(number: int, phase: str, index: int = 0, part: int = 0) -> dict:
    return {
        "turn_id": f"turn_{number:03d}",
        "phase": phase,
        "index": index,
        "part": part,
        "audio_uri": f"{AUDIO}/{phase}/a1b2c3d4-0000-4000-8000-{number:012d}.flac",
    }


def session_done(**changes) -> dict:
    """The session.done contract's data: a demo session whose listening module ran."""
    return contract("event.session_done.json")["data"] | changes


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
    """An event as its producer sends it; session.done is at schema_version 2."""
    sent = envelope(
        event_type, SESSION_ID, data, event_id="6f1c2f0e-3a55-4a7e-9d1a-2b8c5e0a1009", now=NOW
    )
    return sent | {"schema_version": 2} if event_type == "session.done" else sent


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
        recommender(store),
        clock=lambda: NOW,
        new_event_id=lambda: "6f1c2f0e-3a55-4a7e-9d1a-2b8c5e0a1005",
    )


def events(store: MemoryStore, publisher: MemoryPublisher) -> APIRouter:
    """Core's push route on the recorded responses, wired as AI_MODE=fixtures wires it."""
    model, reports = FixtureGradingModel(RECORDED / "grader"), assembler(store, publisher)
    coach = ReadingCoach(
        store=store,
        publisher=publisher,
        stories=StoryRequests(store),
        notifier=Outbox(store),
        speaker=SilentSpeaker(),
        model_for=lambda session_id: RecordedCoach.from_file(
            RECORDED / "coach" / f"{session_id}.json"
        ),
        clock=lambda: NOW,
    )
    grader = FinalGrader(store, model, FixtureTranscriber(RECORDED / "asr"), reports)
    return events_router(grader, reports, coach)


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


def coach_store() -> MemoryStore:
    """sess_demo_001's finished report, with its child, consent and catalogue books."""
    docs = {
        paths.report(SESSION_ID): contract("reading_report.sess_demo_001.json"),
        paths.child(CHILD_ID): {
            "guardian_id": GUARDIAN_ID,
            "first_name": "Chidi",
            "saved_tags": ["food"],
        },
        "consents/consent_demo_001": {"guardian_id": GUARDIAN_ID, "child_id": CHILD_ID},
    }
    return MemoryStore(docs | catalogue())


def demo_report(**changes) -> dict:
    """sess_demo_001's report with its profile, level or fluency fields changed."""
    report = contract("reading_report.sess_demo_001.json")
    for section in ("profile", "level", "fluency"):
        report[section] |= {k: v for k, v in changes.items() if k in report[section]}
    return report
