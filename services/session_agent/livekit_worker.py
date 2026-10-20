"""The LiveKit Agents worker: one job per session room (SDD 4).

Binds the room to the Driver and does nothing else: microphone audio goes to the
recorder, Silero VAD and Chirp 3 streaming STT; their events, data-channel acks,
connection changes and timers go to the driver; the driver's messages go out on
the data channel. All session logic is in machine/ and driver.py.

Scripted-clip mode only (cache_first and the live_first fallback). The Gemini
Live conductor comes on day 3 and its tools will go through
aloai_authz.authorize (AGENTS.md rule 9).
"""

import asyncio
import functools
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import firestore
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli, stt, vad
from livekit.plugins import google, silero

from . import cloud, config, metadata, quick_grade
from .background import Background
from .clips.catalog import ClipCatalog
from .clips.store import ClipStore
from .driver import Driver, Ports
from .machine.types import Timer
from .passages import PassageBank, folder_bank
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
    def __init__(self, settings: config.WorkerSettings, cfg: config.Config, items: int) -> None:
        self._live = cfg.ai_mode == "live"
        self._fixture = quick_grade.FixtureQuickGrader(
            items=items, fixtures_dir=Path("fixtures/ai/quick")
        )
        # One HTTP client and one ID token for the whole session (2 s p90 target).
        self._client = (
            quick_grade.QuickGradeClient(settings.core_url, _id_token(settings))
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


def _id_token(settings: config.WorkerSettings):
    """A Cloud Run ID token for Core, or None locally."""
    if not os.environ.get("K_SERVICE"):
        return None
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return lambda: id_token.fetch_id_token(Request(), settings.core_url)


class _Passages:
    """No Passage Generator yet (day 3): a story request falls back to the bank,
    so the session is honestly flagged FALLBACK_PASSAGE."""

    def __init__(self, bank: PassageBank, passage_id: str) -> None:
        self._bank, self._passage_id = bank, passage_id
        self.driver: Driver | None = None

    def pair(self, passage_id: str):
        return self._bank.pair(passage_id)

    def generate(self, with_tags: bool) -> None:
        log.info("Passage Generator not wired yet; using the bank passage")
        self.bank()

    def bank(self) -> None:
        pair = self._bank.pair(self._passage_id)
        asyncio.get_running_loop().call_soon(
            functools.partial(self.driver.passage_arrived, pair, fallback=True)
        )


def _bank(settings: config.WorkerSettings, db: cloud.FirestoreDocuments) -> PassageBank:
    if settings.bank_dir:
        return folder_bank(Path(settings.bank_dir))
    return PassageBank(lambda passage_id: db.get(f"passages/{passage_id}"))


async def entrypoint(ctx: JobContext) -> None:
    cfg = config.load(os.environ)
    settings = config.worker_settings(os.environ)
    start = metadata.parse(ctx.job.metadata or ctx.job.room.metadata, settings.voice_profile_id)
    log.info("session %s starting", start.ctx.session_id)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    child = await ctx.wait_for_participant()
    loop = asyncio.get_running_loop()

    gcs = cloud.storage_client(settings.project)
    audio_bucket = cloud.GcsBucket(gcs, settings.audio_bucket)
    db = cloud.FirestoreDocuments(firestore.Client(project=settings.project))
    background = Background()
    timers = _Timers(loop)
    channel = _Channel(ctx.room)
    profile = config.PROFILES[cfg.session_profile]
    grader = _Grader(settings, cfg, profile.n_questions)
    passages = _Passages(_bank(settings, db), settings.bank_passage_id)

    def upload(audio_uri: str, flac: bytes) -> None:
        bucket, name = object_name(audio_uri)
        background.run(audio_bucket.upload, name, flac, "audio/flac")

    class _Docs:
        def set(self, path: str, data: dict) -> None:
            background.run(db.set, path, data)

    publisher = cloud.PubSubPublisher(settings.project)

    class _Publish:
        def publish(self, event: dict) -> None:
            # After the uploads and records queued so far, so an event never runs ahead
            # of the audio and documents it names (the Scorer and Grader read them).
            background.run_after_pending(publisher.publish, event)

    ended = asyncio.Event()
    started = time.monotonic()
    store = ClipStore(
        cloud.GcsBucket(gcs, settings.clips_bucket),
        settings.clips_bucket,
        settings.voice_profile_id,
        settings.tts_version,
    )
    driver = Driver(
        ctx=start.ctx,
        child_id=start.child_id,
        profile=cfg.session_profile,
        voice_mode=cfg.voice_mode,
        audio=AudioLog(settings.audio_bucket, str(uuid.uuid4())),
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
        _pump(ctx, driver, track, cfg)

    ctx.room.on("data_received", lambda packet: _on_data(driver, packet))
    ctx.room.on(
        "participant_disconnected",
        lambda p: driver.on_disconnected() if p.identity == child.identity else None,
    )
    ctx.room.on("track_subscribed", lambda track, publication, p: listen(track, p))

    returning = passages.pair(start.passage_id) if start.passage_id else None
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
    await asyncio.sleep(1)  # let the last data-channel messages go
    ctx.shutdown(reason="session ended")


def _on_data(driver: Driver, packet: rtc.DataPacket) -> None:
    if packet.topic == TOPIC:
        driver.on_client_message(packet.data)


def _pump(ctx: JobContext, driver: Driver, track: rtc.Track, cfg: config.Config) -> None:
    """Microphone frames -> recorder, VAD and STT; their events -> the driver."""
    audio = rtc.AudioStream.from_track(track=track, sample_rate=16_000, num_channels=1)
    vad_stream = ctx.proc.userdata["vad"].stream()
    speech = _stt(cfg)

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


def _stt(cfg: config.Config):
    """Chirp 3 streaming STT. AI_MODE=fixtures has none: no cloud calls locally, so
    the reading runs to its 90 s cap and answers reach grade:quick empty."""
    if cfg.ai_mode != "live":
        log.warning("AI_MODE=fixtures: no speech to text; the position tracker will not move")
        return None
    settings = config.worker_settings(os.environ)
    return google.STT(
        model="chirp_3",
        languages=settings.stt_language,
        location=settings.stt_location,
        interim_results=True,
    ).stream()


def run() -> None:  # pragma: no cover - the worker process
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
