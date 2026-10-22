"""Reading Scorer entry point: uvicorn services.reading_scorer.main:create_app --factory.

CLOUD picks the clients (aloai_env). On gcp it wires the scorer to Firestore, Pub/Sub and
Cloud Storage (their emulators when the *_EMULATOR_HOST variables are set) and takes
events from the push route. On azure it wires Cosmos DB, Service Bus and Blob Storage and
takes events from its own queue (EVENT_QUEUE); the push route is not mounted, because
nothing on Azure signs a push. Both use the CPU aligner and pause finder, and by AI_MODE
the recorded transcripts in fixtures/ai/reading/, or live: Chirp 3 and Gemini on gcp,
Azure AI Speech and an Azure OpenAI transcription deployment on azure. Refuses to start
with ALO_ENV=local on Cloud Run or Container Apps.
"""

import os
from collections.abc import Mapping
from pathlib import Path

import aloai_env
from aloai_azure import deployment, open_openai, recognize_words
from aloai_blobs import Blobs, open_blobs
from aloai_events import anyone, open_publisher, pump_lifespan, pushed_by
from aloai_store import open_store
from fastapi import FastAPI
from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud import speech_v2

from .api import event_handler, router
from .audio import BlobAudio
from .azure import AzureSpeechReading, OpenAIReading
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
    env = os.environ if env is None else env
    settings = aloai_env.load(env)
    blobs = open_blobs(settings)
    chirp, gemini = _transcribers(settings, blobs, second=_second_transcript(env))
    from .timing import MmsAligner, SileroPauses  # PyTorch is installed only in the image

    scorer = Phase1Scorer(
        store=open_store(settings),
        publisher=open_publisher(settings),
        audio=BlobAudio(blobs),
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


def _second_transcript(env: Mapping[str, str]) -> bool:
    """SECOND_TRANSCRIPT: "on" (default) scores a word only where two transcripts agree
    (PRD 5.3); "off" scores from the first transcript alone (labels._label_single). A server
    setting, changed only through Terraform."""
    value = env.get("SECOND_TRANSCRIPT", "on")
    if value not in ("on", "off"):
        raise aloai_env.ConfigError(f"SECOND_TRANSCRIPT={value!r} is not 'on' or 'off'")
    return value == "on"


def _transcribers(
    settings: aloai_env.Config, blobs: Blobs, *, second: bool = True
) -> tuple[Transcriber, Transcriber | None]:
    """The two transcripts: Chirp 3 and Gemini on gcp, Azure AI Speech and an Azure OpenAI
    transcription deployment on azure, or the recorded ones. With second=False only the first
    (no second transcriber is built, so no transcription deployment is needed)."""
    if settings.ai_mode == "fixtures":
        return FixtureReading(RECORDED, "chirp"), (
            FixtureReading(RECORDED, "gemini") if second else None
        )
    if settings.cloud == "azure":
        return (
            AzureSpeechReading(blobs, lambda pcm, phrases: recognize_words(settings, pcm, phrases)),
            OpenAIReading(open_openai(settings), deployment(settings, "transcribe"), blobs)
            if second
            else None,
        )
    speech = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{CHIRP_LOCATION}-speech.googleapis.com")
    )
    vertex = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return ChirpReading(speech, settings.project), GeminiReading(vertex) if second else None
