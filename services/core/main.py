"""Core service entry point: uvicorn services.core.main:create_app --factory.

Wires the Passage Generator, the Grader and the Reading Coach to Firestore (and its vector search for books) and
Pub/Sub, or their emulators when the *_EMULATOR_HOST variables are set, and, by AI_MODE,
to Vertex AI, Speech-to-Text and Text-to-Speech or to the recorded responses in
fixtures/ai/. The Coach's email goes to
the Account and Payments service at ACCOUNT_URL, or to the Firestore outbox with
ALO_ENV=local. COACH_ON=false turns the Coach off, so every plan is the template plan.
GENERATOR_ON (default false, a server setting from terraform.tfvars) lets plan.ready
pre-generate the child's next story; off, plan.ready is ignored and the Session Agent
(which has the same setting) uses the bank passage.
Generated passages point their word clips at CLIPS_BUCKET and TTS_VERSION (the Session
Agent's settings and defaults).
Refuses to start with ALO_ENV=local on Cloud Run.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

import aloai_env
import requests
import spacy
from aloai_events import PubSubPublisher, PushCheck, anyone, pushed_by
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
from .generator.models import FixtureModel, Model, VertexModel
from .generator.pipeline import Generator
from .generator_api import router as generator_router
from .generator_requests import NextStories
from .grader.api import router
from .grader.asr import CHIRP_LOCATION, ChirpTranscriber, FixtureTranscriber, Transcriber
from .grader.assembly import ReportAssembler
from .grader.books import (
    BookRecommender,
    Embedder,
    FirestoreBookSearch,
    FixtureEmbedder,
    VertexEmbedder,
)
from .grader.final import FinalGrader
from .grader.models import FixtureGradingModel, GradingModel, VertexGradingModel
from .grader.quick import QuickGrader

RECORDED = Path(__file__).resolve().parents[2] / "fixtures" / "ai"
TTS_ENDPOINT = "eu-texttospeech.googleapis.com"
FLAGS = {"true": True, "false": False}


def create_app(env: Mapping[str, str] | None = None) -> FastAPI:
    env = os.environ if env is None else env
    settings = aloai_env.load(env)
    db = firestore.Client(project=settings.project)
    store = FirestoreStore(db)
    publisher = PubSubPublisher(pubsub_v1.PublisherClient(), settings.project)
    model, transcriber, embedder = _ai(settings)
    assembler = ReportAssembler(
        store, publisher, BookRecommender(FirestoreBookSearch(db), embedder)
    )
    coach = ReadingCoach(
        store=store,
        publisher=publisher,
        stories=StoryRequests(store),
        notifier=_notifier(settings, env, store),
        speaker=_speaker(settings, env),
        model_for=_coach_model(settings),
        enabled=_flag(env, "COACH_ON"),
    )
    generator = _generator(settings, env)
    app = FastAPI(title="Alo.ai Core")
    app.include_router(generator_router(generator, store))
    app.include_router(router(QuickGrader(store, model)))
    app.include_router(
        events_router(
            FinalGrader(store, model, transcriber, assembler),
            assembler,
            coach,
            store,
            _push_check(settings),
            # Off until the Writer + Critic evaluation set passes (and a switch on demo day).
            NextStories(generator, store) if _flag(env, "GENERATOR_ON", "false") else None,
        )
    )
    return app


def _push_check(settings: aloai_env.Config) -> PushCheck:
    account = settings.push_service_account
    return pushed_by(account, settings.push_audience) if account else anyone


def _ai(settings: aloai_env.Config) -> tuple[GradingModel, Transcriber, Embedder]:
    if settings.ai_mode == "fixtures":
        return (
            FixtureGradingModel(RECORDED / "grader"),
            FixtureTranscriber(RECORDED / "asr"),
            FixtureEmbedder(RECORDED / "embeddings.json"),
        )
    speech = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{CHIRP_LOCATION}-speech.googleapis.com")
    )
    vertex = genai.Client(vertexai=True, project=settings.project, location=settings.location)
    return (
        VertexGradingModel(vertex),
        ChirpTranscriber(speech, settings.project),
        VertexEmbedder(vertex),
    )


def _generator(settings: aloai_env.Config, env: Mapping[str, str]) -> Generator:
    model: Model
    if settings.ai_mode == "fixtures":
        model = FixtureModel(RECORDED / "generator")
    else:
        model = VertexModel(
            genai.Client(vertexai=True, project=settings.project, location=settings.location)
        )
    return Generator(
        model=model,
        nlp=spacy.load("en_core_web_sm"),  # once per instance, not per request
        clips_bucket=env.get("CLIPS_BUCKET", "aloai-dev-clips"),
        tts_version=env.get("TTS_VERSION", "v1"),
    )


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


def _flag(env: Mapping[str, str], name: str, default: str = "true") -> bool:
    value = env.get(name, default)
    if value not in FLAGS:
        raise aloai_env.ConfigError(f"{name}={value!r} is not one of {sorted(FLAGS)}")
    return FLAGS[value]


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise aloai_env.ConfigError(f"{name} must be set")
    return value
