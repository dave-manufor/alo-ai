"""Core service entry point: uvicorn services.core.main:create_app --factory.

Wires the Grader and the Reading Coach to Firestore and Pub/Sub (their emulators when
the *_EMULATOR_HOST variables are set) and, by AI_MODE, to Vertex AI, Speech-to-Text and
Text-to-Speech or to the recorded responses in fixtures/ai/. The Coach's email goes to
the Account and Payments service at ACCOUNT_URL, or to the Firestore outbox with
ALO_ENV=local. COACH_ON=false turns the Coach off, so every plan is the template plan.
Refuses to start with ALO_ENV=local on Cloud Run.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

import aloai_env
import requests
from aloai_events import PubSubPublisher
from aloai_store import FirestoreStore, Store
from fastapi import FastAPI
from google import genai
from google.adk.models import BaseLlm, Gemini
from google.api_core.client_options import ClientOptions
from google.auth.transport.requests import Request
from google.cloud import firestore, pubsub_v1, speech_v2, storage, texttospeech
from google.oauth2 import id_token

from .api import events_router
from .coach.agent import COACH_MODEL, RecordedModel
from .coach.clients import (
    AccountNotifier,
    ChirpSpeaker,
    Notifier,
    Outbox,
    SilentSpeaker,
    Speaker,
    StoryRequests,
)
from .coach.run import ReadingCoach
from .grader.api import router
from .grader.asr import CHIRP_LOCATION, ChirpTranscriber, FixtureTranscriber, Transcriber
from .grader.assembly import ReportAssembler
from .grader.final import FinalGrader
from .grader.models import FixtureGradingModel, GradingModel, VertexGradingModel
from .grader.quick import QuickGrader

RECORDED = Path(__file__).resolve().parents[2] / "fixtures" / "ai"
TTS_ENDPOINT = "eu-texttospeech.googleapis.com"
FLAGS = {"true": True, "false": False}


def create_app(env: Mapping[str, str] | None = None) -> FastAPI:
    env = os.environ if env is None else env
    settings = aloai_env.load(env)
    store = FirestoreStore(firestore.Client(project=settings.project))
    publisher = PubSubPublisher(pubsub_v1.PublisherClient(), settings.project)
    assembler = ReportAssembler(store, publisher)
    model, transcriber = _ai(settings)
    coach = ReadingCoach(
        store=store,
        publisher=publisher,
        stories=StoryRequests(store),
        notifier=_notifier(settings, env, store),
        speaker=_speaker(settings, env),
        model_for=_coach_model(settings),
        enabled=_flag(env, "COACH_ON"),
    )
    app = FastAPI(title="Alo.ai Core")
    app.include_router(router(QuickGrader(store, model)))
    app.include_router(
        events_router(FinalGrader(store, model, transcriber, assembler), assembler, coach)
    )
    return app


def _ai(settings: aloai_env.Config) -> tuple[GradingModel, Transcriber]:
    if settings.ai_mode == "fixtures":
        return FixtureGradingModel(RECORDED / "grader"), FixtureTranscriber(RECORDED / "asr")
    speech = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{CHIRP_LOCATION}-speech.googleapis.com")
    )
    vertex = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return VertexGradingModel(vertex), ChirpTranscriber(speech, settings.project)


def _coach_model(settings: aloai_env.Config) -> Callable[[str], BaseLlm | str]:
    if settings.ai_mode == "fixtures":
        return lambda session_id: RecordedModel.from_file(RECORDED / "coach" / f"{session_id}.json")
    gemini = Gemini(
        model=COACH_MODEL,
        client_kwargs={
            "vertexai": True,
            "project": settings.project,
            "location": settings.location,
        },
    )
    return lambda session_id: gemini


def _notifier(settings: aloai_env.Config, env: Mapping[str, str], store: Store) -> Notifier:
    if settings.alo_env == "local":
        return Outbox(store)
    return AccountNotifier(_required(env, "ACCOUNT_URL"), requests.post, _id_token)


def _id_token(audience: str) -> str:
    return id_token.fetch_id_token(Request(), audience)


def _speaker(settings: aloai_env.Config, env: Mapping[str, str]) -> Speaker:
    if settings.ai_mode == "fixtures":
        return SilentSpeaker()
    tts = texttospeech.TextToSpeechClient(client_options=ClientOptions(api_endpoint=TTS_ENDPOINT))
    bucket = storage.Client(project=settings.project).bucket(_required(env, "AUDIO_BUCKET"))
    return ChirpSpeaker(tts, bucket, _required(env, "TTS_VOICE"))


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "true")
    if value not in FLAGS:
        raise aloai_env.ConfigError(f"{name}={value!r} is not one of {sorted(FLAGS)}")
    return FLAGS[value]


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise aloai_env.ConfigError(f"{name} must be set")
    return value
