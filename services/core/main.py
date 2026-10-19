"""Core service entry point: uvicorn services.core.main:create_app --factory.

Wires the Grader to Firestore and Pub/Sub (their emulators when the *_EMULATOR_HOST
variables are set) and, by AI_MODE, to Vertex AI and Speech-to-Text or to the
recorded responses in fixtures/ai/. Refuses to start with ALO_ENV=local on Cloud Run.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI
from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud import firestore, pubsub_v1, speech_v2

from . import config
from .events import PubSubPublisher
from .grader.api import router
from .grader.asr import CHIRP_LOCATION, ChirpTranscriber, FixtureTranscriber, Transcriber
from .grader.assembly import ReportAssembler
from .grader.final import FinalGrader
from .grader.models import FixtureGradingModel, GradingModel, VertexGradingModel
from .grader.quick import QuickGrader
from .store import FirestoreStore

RECORDED = Path(__file__).resolve().parents[2] / "fixtures" / "ai"


def create_app(env: Mapping[str, str] | None = None) -> FastAPI:
    settings = config.load(os.environ if env is None else env)
    store = FirestoreStore(firestore.Client(project=settings.project))
    publisher = PubSubPublisher(pubsub_v1.PublisherClient(), settings.project)
    assembler = ReportAssembler(store, publisher)
    model, transcriber = _ai(settings)
    app = FastAPI(title="Alo.ai Core")
    app.include_router(
        router(
            QuickGrader(store, model),
            FinalGrader(store, model, transcriber, assembler),
            assembler,
        )
    )
    return app


def _ai(settings: config.Config) -> tuple[GradingModel, Transcriber]:
    if settings.ai_mode == "fixtures":
        return FixtureGradingModel(RECORDED / "grader"), FixtureTranscriber(RECORDED / "asr")
    speech = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{CHIRP_LOCATION}-speech.googleapis.com")
    )
    vertex = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return VertexGradingModel(vertex), ChirpTranscriber(speech, settings.project)
