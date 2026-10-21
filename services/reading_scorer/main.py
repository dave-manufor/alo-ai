"""Reading Scorer entry point: uvicorn services.reading_scorer.main:create_app --factory.

CLOUD picks the clients (aloai_env). On gcp it wires the scorer to Firestore, Pub/Sub and
Cloud Storage (their emulators when the *_EMULATOR_HOST variables are set) and takes
events from the push route. On azure it wires Cosmos DB, Service Bus and Blob Storage and
takes events from its own queue (EVENT_QUEUE); the push route is not mounted, because
nothing on Azure signs a push. Both use the CPU aligner and pause finder, and by AI_MODE
Chirp 3 and Gemini or the recorded transcripts in fixtures/ai/reading/. The live Azure
transcribers are not built yet, so AI_MODE=live needs gcp. Refuses to start with
ALO_ENV=local on Cloud Run or Container Apps.
"""

import os
from collections.abc import Mapping
from pathlib import Path

import aloai_env
from aloai_blobs import open_blobs
from aloai_events import anyone, open_publisher, pump_lifespan, pushed_by
from aloai_store import open_store
from fastapi import FastAPI
from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud import speech_v2

from .api import event_handler, router
from .audio import BlobAudio
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
    chirp, gemini = _transcribers(settings)
    from .timing import MmsAligner, SileroPauses  # PyTorch is installed only in the image

    scorer = Phase1Scorer(
        store=open_store(settings),
        publisher=open_publisher(settings),
        audio=BlobAudio(open_blobs(settings)),
        chirp=chirp,
        gemini=gemini,
        aligner=MmsAligner(),
        pause_finder=SileroPauses(),
    )
    return build_app(settings, scorer)


def build_app(settings: aloai_env.Config, scorer: Phase1Scorer) -> FastAPI:
    """The app around a scorer: the push route on gcp, the queue pump on azure."""
    app = FastAPI(
        title="Alo.ai Reading Scorer",
        lifespan=pump_lifespan(settings, event_handler(scorer)),
    )
    if settings.cloud == "gcp":
        account = settings.push_service_account
        check = pushed_by(account, settings.push_audience) if account else anyone
        app.include_router(router(scorer, check))
    return app


def _transcribers(settings: aloai_env.Config) -> tuple[Transcriber, Transcriber]:
    if settings.ai_mode == "fixtures":
        return FixtureReading(RECORDED, "chirp"), FixtureReading(RECORDED, "gemini")
    if settings.cloud != "gcp":
        raise aloai_env.ConfigError(f"AI_MODE=live is not built for CLOUD={settings.cloud} yet")
    speech = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{CHIRP_LOCATION}-speech.googleapis.com")
    )
    vertex = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return ChirpReading(speech, settings.project), GeminiReading(vertex)
