"""The LiveKit Agents worker: one job per session room (SDD 4).

Binds the room to the Driver and does nothing else: microphone audio goes to the
recorder, Silero VAD and streaming STT (Chirp 3, or Azure AI Speech when CLOUD=azure);
their events, data-channel acks,
connection changes and timers go to the driver; the driver's messages go out on
the data channel. All session logic is in machine/ and driver.py.

Scripted-clip mode only (cache_first and the live_first fallback). With AI_MODE=live
and GENERATOR_ON=true the story comes from the Passage Generator in Core (generation.py). The Gemini
Live conductor comes on day 3 and its tools will go through
aloai_authz.authorize (AGENTS.md rule 9).
"""

import asyncio
import functools
import logging
import os
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import aloai_env
from aloai_azure import deployment, open_openai_async, speech_credentials
from aloai_blobs import SCHEME_OF, open_blobs
from aloai_events import open_publisher
from aloai_service_auth import service_token
from aloai_store import Store, open_store
from google import genai
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli, stt, vad
from livekit.plugins import silero

from . import cloud, config, generation, metadata, quick_grade
from .background import Background
from .clips.catalog import ClipCatalog
from .clips.store import ClipStore
from .core_client import CoreClient
from .driver import Driver, Ports
from .machine.profiles import PASSAGE_WAIT_MS
from .machine.types import Profile, Timer
from .passages import PassageBank, PassageError, folder_bank, passage_id_for_level
from .protocol import encode
from .recorder import FlacRecorder, object_name
from .recording import AudioLog

log = logging.getLogger("aloai.session_agent")

TOPIC = "aloai.session"  # data-channel topic shared with the web app
TICK_S = 0.2
VAD_THRESHOLD = 0.45  # [CAL] PRD 5.1: speech probability below this is non-speech
VAD_MIN_SILENCE_S = 0.12  # [CAL] PRD 5.1: ... for more than 120 ms


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load(
        activation_threshold=VAD_THRESHOLD, min_silence_duration=VAD_MIN_SILENCE_S
    )


class _Channel:
    """Sends protocol messages in order, on one task."""

    def __init__(self, room: rtc.Room) -> None:
        self._room = room
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self.task = asyncio.create_task(self._run())

    def send(self, message: dict) -> None:
        self._queue.put_nowait(message)

    async def _run(self) -> None:
        while True:
            message = await self._queue.get()
            try:
                await self._room.local_participant.publish_data(
                    encode(message), reliable=True, topic=TOPIC
                )
            except Exception:  # noqa: BLE001 - one lost message must not end the session
                log.exception("data channel send failed: %s", message.get("cmd"))


class _Timers:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.driver: Driver | None = None

    def start(self, name: str, ms: int) -> None:
        self._loop.call_later(ms / 1000, lambda: self.driver.handle(Timer(name)))


class _Grader:
    def __init__(
        self,
        settings: config.WorkerSettings,
        cfg: config.Config,
        shared: aloai_env.Config,
        items: int,
    ) -> None:
        self._live = cfg.ai_mode == "live"
        self._fixture = quick_grade.FixtureQuickGrader(
            items=items, fixtures_dir=Path("fixtures/ai/quick")
        )
        # One HTTP client and one ID token for the whole session (2 s p90 target).
        self._client = (
            quick_grade.QuickGradeClient(settings.core_url, _id_token(settings, shared))
            if self._live
            else None
        )
        self._calls: set[asyncio.Task] = set()
        self.driver: Driver | None = None

    def request(self, body: dict) -> None:
        if not self._live:
            asyncio.get_running_loop().call_soon(
                self.driver.on_quick_response, self._fixture.answer(body)
            )
            return

        async def call() -> None:
            self.driver.on_quick_response(await self._client.post(body))

        task = asyncio.create_task(call())
        self._calls.add(task)
        task.add_done_callback(self._calls.discard)

    async def close(self) -> None:
        if self._calls:
            await asyncio.gather(*self._calls, return_exceptions=True)
        if self._client is not None:
            await self._client.aclose()


def _id_token(settings: config.WorkerSettings, shared: aloai_env.Config):
    """A token for Core from the cloud this runs on (a Google ID token, or an Entra access
    token for CORE_AUDIENCE), or None when not hosted. A new one on each call."""
    if not shared.hosted:
        return None
    if shared.cloud == "azure" and not settings.core_audience:
        # An Entra token is for an app ID URI, not for Core's URL. Until Core has one
        # (infra/azure/README.md, known gaps) only the environment's internal ingress protects it.
        log.warning("CORE_AUDIENCE is not set: calling Core without a token")
        return None
    audience = settings.core_audience or settings.core_url
    return lambda: service_token(shared, audience)


class _Passages:
    """The story from the Passage Generator (AI_MODE=live and GENERATOR_ON=true), or the
    bank passage: with AI_MODE=fixtures, with the generator off, when it gives none, or
    when the machine's passage_wait timer runs out first (the machine then drops a story
    that arrives late)."""

    def __init__(
        self,
        bank: PassageBank,
        passage_id: str,
        profile: Profile,
        requester: generation.StoryRequester | None,
    ) -> None:
        self._bank, self._passage_id, self._profile = bank, passage_id, profile
        self._requester = requester
        self._calls: set[asyncio.Task] = set()
        self.driver: Driver | None = None

    def pair(self, passage_id: str):
        return self._bank.pair(passage_id, self._profile)

    def generate(self, interest: str | None, deadline_ms: int) -> None:
        if self._requester is None:
            log.info("no story requester (AI_MODE=fixtures or GENERATOR_ON=false): bank passage")
            self.bank()
            return

        async def call() -> None:
            pair = await self._requester.request(interest, deadline_ms)
            if pair is None:
                self.bank()
            else:
                self.driver.passage_arrived(pair, fallback=False)

        task = asyncio.create_task(call())
        self._calls.add(task)
        task.add_done_callback(self._calls.discard)

    def bank(self) -> None:
        pair = self.pair(self._passage_id)
        asyncio.get_running_loop().call_soon(
            functools.partial(self.driver.passage_arrived, pair, fallback=True)
        )

    async def close(self) -> None:
        if self._calls:
            await asyncio.gather(*self._calls, return_exceptions=True)
        if self._requester is not None:
            await self._requester.client.aclose()


async def _bank_by_level(db: Store, child_id: str, profile_name: str) -> str:
    """The bank passage for this child's level: the last report's next level, else the
    class's start level. A child record that can't be read must not end the session, so
    the profile's default passage is used then."""
    try:
        child = await asyncio.get_running_loop().run_in_executor(
            None, db.get, f"children/{child_id}"
        )
    except Exception:
        log.exception("no child record for %s; using the default bank passage", child_id)
        child = None
    return passage_id_for_level(profile_name, generation.start_arl(child, date.today()))


def _prepared(passages: _Passages, passage_id: str | None):
    """A returning child's prepared story, or None for a fresh one: a prepared passage
    that is missing or doesn't fit SESSION_PROFILE must not end the session."""
    if not passage_id:
        return None
    try:
        return passages.pair(passage_id)
    except PassageError:
        log.warning("prepared passage %s can't be used; starting a fresh story", passage_id)
        return None


def _bank_opening(passages: _Passages, passage_id: str):
    """A generic session (INTEREST_CHAT=false) opens at the mic check with the bank passage
    chosen by the child's level. None if that passage can't be used, and the session then
    opens with the interest chat as before rather than ending."""
    try:
        return passages.pair(passage_id)
    except PassageError:
        log.warning("bank passage %s can't be used; opening with the interest chat", passage_id)
        return None


def _consume_prepared(background: Background, db: Store, child_id: str) -> None:
    """A prepared story is read once. Clearing next_passage_id when the session starts
    means a session that ends INCOMPLETE (no plan.ready) can't give the child the same
    story again next time; a failed write is logged by Background and never ends the
    session."""
    background.run(db.merge, f"children/{child_id}", {"next_passage_id": None})


def _tagger(settings: config.WorkerSettings, shared: aloai_env.Config) -> generation.Tagger:
    """The tagger for this cloud: Azure OpenAI's "tagger" deployment, or Gemini on Vertex AI."""
    if shared.cloud == "azure":
        return generation.AzureTagger(open_openai_async(shared), deployment(shared, "tagger"))
    vertex = genai.Client(
        vertexai=True, project=settings.project, location=settings.vertex_location
    )
    return generation.VertexTagger(vertex)


def _story_requester(
    settings: config.WorkerSettings,
    cfg: config.Config,
    start: metadata.SessionStart,
    profile: Profile,
    bank: PassageBank,
    db: Store,
    shared: aloai_env.Config,
) -> generation.StoryRequester | None:
    if cfg.ai_mode != "live" or not cfg.generator_on:
        return None
    return generation.StoryRequester(
        session_id=start.ctx.session_id,
        child_ref=start.child_id,
        voice_profile_id=settings.voice_profile_id,
        length_profile=profile.name.upper(),
        tagger=_tagger(settings, shared),
        child=lambda: db.get(f"children/{start.child_id}"),
        client=CoreClient(
            settings.core_url, generation.PATH, PASSAGE_WAIT_MS / 1000, _id_token(settings, shared)
        ),
        load_pair=lambda passage_id: bank.pair(passage_id, profile),
    )


def _bank(settings: config.WorkerSettings, db: Store) -> PassageBank:
    if settings.bank_dir:
        return folder_bank(Path(settings.bank_dir))
    return PassageBank(lambda passage_id: db.get(f"passages/{passage_id}"))


# The room is made when the guardian taps Start, and the child joins a moment later. If nobody
# does (the tab was closed, the mic prompt was never answered), the agent would wait for ever and
# hold a worker slot; give up after this long. LiveKit closes the empty room after 300 s anyway.
CHILD_JOIN_WAIT_S = 180


async def _wait_for_child(ctx: JobContext, wait_s: float) -> rtc.RemoteParticipant | None:
    """The participant who joined, or None (and the job is shut down) if nobody did in time."""
    try:
        return await asyncio.wait_for(ctx.wait_for_participant(), wait_s)
    except TimeoutError:
        log.info("nobody joined the room in %s s; leaving", wait_s)
        ctx.shutdown(reason="nobody joined")
        return None


async def entrypoint(ctx: JobContext) -> None:
    cfg = config.load(os.environ)
    settings = config.worker_settings(os.environ)
    start = metadata.parse(ctx.job.metadata or ctx.job.room.metadata, settings.voice_profile_id)
    log.info("session %s starting", start.ctx.session_id)

    shared = aloai_env.load(os.environ, receives_pushes=False)
    scheme = SCHEME_OF[settings.cloud]
    blobs = open_blobs(shared)
    audio_bucket = cloud.BlobBucket(blobs, settings.cloud, settings.audio_bucket)
    db = open_store(shared)
    profile = config.PROFILES[cfg.session_profile]
    bank_passage_id = settings.bank_passage_id or await _bank_by_level(
        db, start.child_id, profile.name
    )
    bank = _bank(settings, db)
    passages = _Passages(
        bank,
        bank_passage_id,
        profile,
        _story_requester(settings, cfg, start, profile, bank, db, shared),
    )
    # Fail before the child joins, not mid-session, if the fallback passage doesn't fit
    # SESSION_PROFILE.
    passages.pair(bank_passage_id)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    child = await _wait_for_child(ctx, CHILD_JOIN_WAIT_S)
    if child is None:
        return
    loop = asyncio.get_running_loop()

    background = Background()
    timers = _Timers(loop)
    channel = _Channel(ctx.room)
    grader = _Grader(settings, cfg, shared, profile.n_questions)

    def upload(audio_uri: str, flac: bytes) -> None:
        bucket, name = object_name(audio_uri)
        background.run(audio_bucket.upload, name, flac, "audio/flac")

    class _Docs:
        def set(self, path: str, data: dict) -> None:
            background.run(db.set, path, data)

    publisher = open_publisher(shared)

    class _Publish:
        def publish(self, event: dict) -> None:
            # After the uploads and records queued so far, so an event never runs ahead
            # of the audio and documents it names (the Scorer and Grader read them).
            background.run_after_pending(publisher.publish, event)

    ended = asyncio.Event()
    started = time.monotonic()
    store = ClipStore(
        cloud.BlobBucket(blobs, settings.cloud, settings.clips_bucket),
        settings.clips_bucket,
        settings.voice_profile_id,
        settings.tts_version,
        scheme,
    )
    driver = Driver(
        ctx=start.ctx,
        child_id=start.child_id,
        profile=cfg.session_profile,
        voice_mode=cfg.voice_mode,
        audio=AudioLog(settings.audio_bucket, str(uuid.uuid4()), scheme=scheme),
        catalog=ClipCatalog(store, settings.clips_base_url),
        ports=Ports(channel, FlacRecorder(upload), timers, grader, passages, _Publish(), _Docs()),
        clock_ms=lambda: int((time.monotonic() - started) * 1000),
        wall=lambda: datetime.now(UTC),
        on_end=lambda status: ended.set(),
    )
    timers.driver = grader.driver = passages.driver = driver

    pumped: set[str] = set()

    def listen(track: rtc.Track, participant: rtc.Participant) -> None:
        if participant.identity != child.identity or track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if track.sid in pumped:
            return
        pumped.add(track.sid)
        if driver.state.disconnected:
            driver.on_reconnected()  # the child is back with a new microphone track
        _pump(ctx, driver, track, cfg, shared)

    ctx.room.on("data_received", lambda packet: _on_data(driver, packet))
    ctx.room.on(
        "participant_disconnected",
        lambda p: driver.on_disconnected() if p.identity == child.identity else None,
    )
    ctx.room.on("track_subscribed", lambda track, publication, p: listen(track, p))

    returning = _prepared(passages, start.passage_id)
    if returning is not None:
        _consume_prepared(background, db, start.child_id)
    elif not cfg.interest_chat:
        returning = _bank_opening(passages, bank_passage_id)
    driver.start(returning=returning)
    for publication in child.track_publications.values():
        if publication.track is not None:
            listen(publication.track, child)

    async def ticker() -> None:
        while not ended.is_set():
            driver.tick()
            await asyncio.sleep(TICK_S)

    tick_task = asyncio.create_task(ticker())
    await ended.wait()
    tick_task.cancel()
    await background.drain()
    await grader.close()
    await passages.close()
    await asyncio.sleep(1)  # let the last data-channel messages go
    ctx.shutdown(reason="session ended")


def _on_data(driver: Driver, packet: rtc.DataPacket) -> None:
    if packet.topic == TOPIC:
        driver.on_client_message(packet.data)


def _pump(
    ctx: JobContext,
    driver: Driver,
    track: rtc.Track,
    cfg: config.Config,
    shared: aloai_env.Config,
) -> None:
    """Microphone frames -> recorder, VAD and STT; their events -> the driver."""
    audio = rtc.AudioStream.from_track(track=track, sample_rate=16_000, num_channels=1)
    vad_stream = ctx.proc.userdata["vad"].stream()
    speech = _stt(cfg, shared)

    async def frames() -> None:
        async for event in audio:
            driver.on_audio(bytes(event.frame.data))
            vad_stream.push_frame(event.frame)
            if speech is not None:
                speech.push_frame(event.frame)

    async def vad_events() -> None:
        async for event in vad_stream:
            if event.type == vad.VADEventType.START_OF_SPEECH:
                driver.on_speech_started()
            elif event.type == vad.VADEventType.END_OF_SPEECH:
                driver.on_speech_ended()

    async def transcripts() -> None:
        async for event in speech:
            if not event.alternatives:
                continue
            text = event.alternatives[0].text
            if event.type == stt.SpeechEventType.INTERIM_TRANSCRIPT:
                driver.on_transcript(text, final=False)
            elif event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                driver.on_transcript(text, final=True)

    asyncio.create_task(frames())
    asyncio.create_task(vad_events())
    if speech is not None:
        asyncio.create_task(transcripts())


def azure_stt_options(shared: aloai_env.Config) -> dict[str, str]:
    """The LiveKit Azure plugin's options for this service's speech settings: the locale,
    the region, and the key (local) or the managed identity's token (hosted)."""
    credentials = speech_credentials(shared)
    options = {"language": shared.speech_locale, "speech_region": credentials["region"]}
    if "key" in credentials:
        return options | {"speech_key": credentials["key"]}
    return options | {"speech_auth_token": credentials["auth_token"]}


def _stt(cfg: config.Config, shared: aloai_env.Config):
    """Streaming STT: Chirp 3 on gcp, Azure AI Speech on azure. AI_MODE=fixtures has none:
    no cloud calls locally, so the reading runs to its 90 s cap and answers reach
    grade:quick empty."""
    if cfg.ai_mode != "live":
        log.warning("AI_MODE=fixtures: no speech to text; the position tracker will not move")
        return None
    if shared.cloud == "azure":
        from livekit.plugins import azure

        return azure.STT(**azure_stt_options(shared)).stream()
    from livekit.plugins import google

    settings = config.worker_settings(os.environ)
    return google.STT(
        model="chirp_3",
        languages=settings.stt_language,
        location=settings.stt_location,
        interim_results=True,
    ).stream()


def run() -> None:  # pragma: no cover - the worker process
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
