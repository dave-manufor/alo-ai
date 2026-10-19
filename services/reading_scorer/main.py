"""Reading Scorer entry point: uvicorn services.reading_scorer.main:create_app --factory.

Wires the scorer to Firestore, Pub/Sub and Cloud Storage (their emulators when the
*_EMULATOR_HOST variables are set), to the CPU aligner and pause finder, and by AI_MODE
to Chirp 3 and Gemini or to the recorded transcripts in fixtures/ai/reading/. Refuses
to start with ALO_ENV=local on Cloud Run.
"""

import os
from collections.abc import Mapping
from pathlib import Path

import aloai_env
from aloai_events import PubSubPublisher
from aloai_store import FirestoreStore
from fastapi import FastAPI
from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud import firestore, pubsub_v1, speech_v2, storage

from .api import router
from .audio import GcsAudio
from .scorer import Phase1Scorer
from .transcribers import (
    CHIRP_LOCATION,
    ChirpReading,
    FixtureReading,
    GeminiReading,
    Transcriber,
)

RECORDED = Path(__file__).resolve().parents[2] / "fixtures" / "ai" / "reading"


def create_app(env: Mapping[str, str] | None = None) -> FastAPI:
    settings = aloai_env.load(os.environ if env is None else env)
    from .timing import MmsAligner, SileroPauses  # PyTorch is installed only in the image

    chirp, gemini = _transcribers(settings)
    scorer = Phase1Scorer(
        store=FirestoreStore(firestore.Client(project=settings.project)),
        publisher=PubSubPublisher(pubsub_v1.PublisherClient(), settings.project),
        audio=GcsAudio(storage.Client(project=settings.project)),
        chirp=chirp,
        gemini=gemini,
        aligner=MmsAligner(),
        pause_finder=SileroPauses(),
    )
    app = FastAPI(title="Alo.ai Reading Scorer")
    app.include_router(router(scorer))
    return app


def _transcribers(settings: aloai_env.Config) -> tuple[Transcriber, Transcriber]:
    if settings.ai_mode == "fixtures":
        return FixtureReading(RECORDED, "chirp"), FixtureReading(RECORDED, "gemini")
    speech = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{CHIRP_LOCATION}-speech.googleapis.com")
    )
    vertex = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return ChirpReading(speech, settings.project), GeminiReading(vertex)
