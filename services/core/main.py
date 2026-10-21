"""Core service entry point: uvicorn services.core.main:create_app --factory.

CLOUD picks the clients (aloai_env). On gcp it wires the Passage Generator, the Grader and
the Reading Coach to Firestore (and its vector search for books) and Pub/Sub, or their
emulators when the *_EMULATOR_HOST variables are set, and takes events from the Pub/Sub push
route. On azure it wires Cosmos DB (and its vector search for books) and Service Bus and takes
events from its own queue (EVENT_QUEUE); the push route is not mounted, because nothing on
Azure signs a push. By AI_MODE the AI is the recorded responses in fixtures/ai/, or live:
Vertex AI, Speech-to-Text and Text-to-Speech on gcp, Azure OpenAI and Azure AI Speech on azure
(the report then records the Azure deployments as the models used). The Passage Generator's
live Azure model is not built yet, so a live start on azure says so.
The Coach's email goes to the Account and Payments service at ACCOUNT_URL, or to the
Firestore outbox with ALO_ENV=local. COACH_ON=false turns the Coach off, so every plan is the
template plan.
GENERATOR_ON (default false, a server setting from terraform.tfvars) lets plan.ready
pre-generate the child's next story; off, plan.ready is ignored and the Session Agent
(which has the same setting) uses the bank passage. Generated passages point their word clips
at CLIPS_BUCKET and TTS_VERSION (the Session Agent's settings and defaults).
Refuses to start with ALO_ENV=local on Cloud Run or Container Apps.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

import aloai_env
import requests
import spacy
from aloai_azure import deployment, open_openai, recognize_words, synthesize
from aloai_blobs import open_blobs
from aloai_events import PushCheck, anyone, open_publisher, pump_lifespan, pushed_by
from aloai_service_auth import service_token
from aloai_store import Store, open_container, open_store
from fastapi import FastAPI
from google import genai
from google.adk.models import BaseLlm, Gemini
from google.api_core.client_options import ClientOptions
from google.cloud import firestore, speech_v2, storage, texttospeech

from .api import event_handler, events_router
from .coach.agent import COACH_MODEL, RecordedModel
from .coach.azure import AzureSpeaker, azure_coach_model
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
from .grader.azure import (
    AzureEmbedder,
    AzureSpeechTranscriber,
    CosmosBookSearch,
    azure_model,
)
from .grader.azure import versions as azure_versions
from .grader.books import (
    BookRecommender,
    BookSearch,
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
    store = open_store(settings)
    publisher = open_publisher(settings)
    model, transcriber, embedder = _ai(settings)
    assembler = ReportAssembler(
        store,
        publisher,
        BookRecommender(_book_search(settings), embedder),
        versions=_versions(settings),
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
    return build_app(
        settings,
        QuickGrader(store, model),
        FinalGrader(store, model, transcriber, assembler),
        assembler,
        coach,
        store,
        generator,
        # Off until the Writer + Critic evaluation set passes (and a switch on demo day).
        NextStories(generator, store) if _flag(env, "GENERATOR_ON", "false") else None,
    )


def build_app(
    settings: aloai_env.Config,
    quick: QuickGrader,
    final: FinalGrader,
    assembler: ReportAssembler,
    coach: ReadingCoach,
    store: Store,
    generator: Generator,
    next_stories: NextStories | None = None,
) -> FastAPI:
    """The app around the graders: the quick endpoint, the Passage Generator, and for events
    the Pub/Sub push route on gcp or the Service Bus queue pump on azure. Both take plan.ready
    to next_stories (None while GENERATOR_ON is false)."""
    app = FastAPI(
        title="Alo.ai Core",
        lifespan=pump_lifespan(
            settings, event_handler(final, assembler, coach, store, next_stories)
        ),
    )
    app.include_router(generator_router(generator, store))
    app.include_router(router(quick))
    if settings.cloud == "gcp":
        app.include_router(
            events_router(final, assembler, coach, store, _push_check(settings), next_stories)
        )
    return app


def _push_check(settings: aloai_env.Config) -> PushCheck:
    account = settings.push_service_account
    return pushed_by(account, settings.push_audience) if account else anyone


def _book_search(settings: aloai_env.Config) -> BookSearch:
    if settings.cloud == "azure":
        return CosmosBookSearch(open_container(settings, "books"))
    return FirestoreBookSearch(firestore.Client(project=settings.project))


def _versions(settings: aloai_env.Config) -> Mapping[str, str] | None:
    """The models the report records as used: the Azure ones when they are the ones called.
    None keeps the Google ones, which is also what recorded responses are named after."""
    if settings.cloud == "azure" and settings.ai_mode == "live":
        return azure_versions(settings)
    return None


def _ai(settings: aloai_env.Config) -> tuple[GradingModel, Transcriber, Embedder]:
    if settings.ai_mode == "fixtures":
        return (
            FixtureGradingModel(RECORDED / "grader"),
            FixtureTranscriber(RECORDED / "asr"),
            FixtureEmbedder(RECORDED / "embeddings.json"),
        )
    if settings.cloud == "azure":
        client = open_openai(settings)
        return (
            azure_model(client, settings),
            AzureSpeechTranscriber(
                open_blobs(settings),
                lambda pcm, phrases: recognize_words(settings, pcm, phrases),
            ),
            AzureEmbedder(client, deployment(settings, "embedding")),
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
        if settings.cloud != "gcp":  # the Azure model comes with the generator's adapters
            raise aloai_env.ConfigError(
                f"the Passage Generator's AI_MODE=live is not built for CLOUD={settings.cloud} yet"
            )
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
    if settings.cloud == "azure":
        return azure_coach_model(settings)
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
    return AccountNotifier(
        _required(env, "ACCOUNT_URL"),
        requests.post,
        lambda audience: service_token(settings, audience),
    )


def _speaker(settings: aloai_env.Config, env: Mapping[str, str]) -> Speaker:
    if settings.ai_mode == "fixtures":
        return SilentSpeaker()
    if settings.cloud == "azure":
        return AzureSpeaker(
            open_blobs(settings),
            lambda ssml: synthesize(settings, ssml),
            _required(env, "AUDIO_BUCKET"),
            _required(env, "TTS_VOICE"),
        )
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
