"""Runs one session: feeds the machine and carries out its actions (SDD 4).

The machine decides; this module only translates. Inputs (audio, VAD, speech to
text, data-channel acks, connection changes, the clock) become machine events,
and each action goes to a port: the data channel, the recorder, the timers, the
quick grader, the passage source, the event publisher and the session records.
The LiveKit worker supplies real ports; tests supply fakes.

Nothing here scores or judges an answer (AGENTS.md rule 1).
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from . import protocol, quick_grade, session_store
from .audio_stats import AudioStats
from .clips.catalog import PROMPTS, ClipCatalog
from .events import Publisher, SessionContext, build_event
from .intents import intent
from .machine import initial_state, step
from .machine import profiles as cfg
from .machine.types import (
    Action,
    CallQuickScore,
    ClipAck,
    Disconnected,
    EmitEvent,
    EndSession,
    Event,
    Log,
    MicResult,
    PassageFallback,
    PassageReady,
    PassageShown,
    Phase,
    PlayClip,
    PlayWordClip,
    ReadingDone,
    QuickScore,
    Reconnected,
    RequestPassage,
    SetFlag,
    SetLiveMode,
    ShowPassage,
    SpeakLive,
    Start,
    StartRecording,
    StartTimer,
    StopRecording,
    StreamClipFromStore,
    TurnEnd,
    UseBankPassage,
)
from .mic_check import MicMeter
from .passages import PassagePair
from .position_tracker import PositionTracker
from .recording import AudioLog, Turn
from .turns import TurnKind, TurnTaker

log = logging.getLogger(__name__)
STATS_EVERY_MS = 10_000  # how often the audio counters are written to the log


class Channel(Protocol):
    def send(self, message: dict) -> None: ...


class Recorder(Protocol):
    def start(self, turn: Turn) -> None: ...

    def feed(self, pcm: bytes) -> None: ...

    def stop(self) -> None:
        """Finish the turn and write its 16 kHz mono FLAC to turn.audio_uri."""
        ...


class Timers(Protocol):
    def start(self, name: str, ms: int) -> None:
        """Call Driver.handle(Timer(name)) after ms."""
        ...


class Grader(Protocol):
    def request(self, body: dict) -> None:
        """Send to grade:quick; pass the reply to Driver.on_quick_response."""
        ...


class Passages(Protocol):
    def generate(self, interest: str | None, deadline_ms: int) -> None:
        """Start a story on the child's interest-chat answer (None: no answer); call
        Driver.passage_arrived(pair, fallback=False) when ready."""
        ...

    def bank(self) -> None:
        """Choose a bank passage; call Driver.passage_arrived(pair, fallback=True)."""
        ...


@dataclass
class Ports:
    channel: Channel
    recorder: Recorder
    timers: Timers
    grader: Grader
    passages: Passages
    publisher: Publisher
    documents: session_store.Documents


_TURN_KIND: dict[str, TurnKind] = {
    "INTEREST_CHAT": "chat",
    "MIC_CHECK": "mic",
    "RETELL": "retell",
    "LISTENING_RETELL": "retell",
}


@dataclass
class Driver:
    ctx: SessionContext
    child_id: str
    profile: str
    voice_mode: str
    audio: AudioLog
    catalog: ClipCatalog
    ports: Ports
    clock_ms: Callable[[], int]
    wall: Callable[[], datetime]
    on_end: Callable[[str], None] = lambda status: None
    new_event_id: Callable[[], str] = lambda: str(uuid.uuid4())

    state: object = None
    pair: PassagePair | None = None
    tracker: PositionTracker | None = None
    turns: TurnTaker = field(default_factory=TurnTaker)
    mic: MicMeter = field(default_factory=MicMeter)
    created_at: datetime | None = None
    _turn: Turn | None = None
    _final: list[str] = field(default_factory=list)
    _interim: str = ""
    _transcripts: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    _reading: bool = False
    # What the agent heard, for the logs only (audio_stats.py): a session that hears nothing
    # looks the same as one that hears a child unless these are written down.
    stats: AudioStats = field(default_factory=AudioStats)
    _stats_logged_ms: int = 0

    @property
    def _clip_playing(self) -> bool:
        # Clips sent whose ack has not come back (several can be queued); a lost ack expires.
        return self.turns.playing(self.clock_ms())

    # ---- lifecycle

    def start(self, returning: PassagePair | None = None, live_available: bool = False) -> None:
        self.state = initial_state(self.profile, self.voice_mode)
        self.created_at = self.wall()
        prompts = [(c, self.catalog.url(c), self.catalog.text(c)) for c in PROMPTS]
        self.ports.channel.send(protocol.clip_list(prompts))
        if returning is not None:
            self._use(returning)
        read = returning.read["passage_id"] if returning else None
        listening = self._listening_id()
        self.handle(Start(read, live_available, listening))

    def passage_arrived(self, pair: PassagePair, *, fallback: bool) -> None:
        if self.pair is None:
            self._use(pair)
        event_type = PassageFallback if fallback else PassageReady
        self.handle(event_type(pair.read["passage_id"], self._listening_id(pair)))

    # ---- inputs

    def handle(self, event: Event) -> None:
        before = self.state.phase
        self.state, actions = step(self.state, event)
        if self.state.phase is not before or isinstance(event, Reconnected):
            # The web app follows the agent's step, and clears its waiting screen on a
            # reconnect; it never moves the session on by itself.
            message = protocol.step(self.state.phase)
            if message is not None:
                self.ports.channel.send(message)
        for action in actions:
            self._run(action)

    def on_audio(self, pcm: bytes) -> None:
        now = self.clock_ms()
        self.stats.frame(pcm, now)
        if self._turn is not None:
            self.ports.recorder.feed(pcm)  # everything is recorded, as it was heard
            # The level check is of the child's voice, not of Kemi's prompt coming back
            # through the phone's microphone.
            if self._turn.phase == "MIC_CHECK" and not self.turns.ignoring(now):
                self.mic.feed(pcm)

    def on_speech_started(self) -> None:
        self.stats.vad_started(self._clip_playing)
        # Speech while a prompt plays is Kemi's own voice in the room: not the child.
        if self.turns.speech_started(self.clock_ms()):
            self.ports.channel.send(protocol.child_speaking(True))

    def on_speech_ended(self) -> None:
        self.stats.vad_ended()
        if self.turns.speech_ended(self.clock_ms()):
            self.ports.channel.send(protocol.child_speaking(False))

    def on_transcript(self, text: str, *, final: bool) -> None:
        self.stats.transcript(text, final=final)
        now = self.clock_ms()
        if self.turns.ignoring(now):
            return  # Kemi's prompt heard back by the microphone, not an answer or the reading
        if self._reading and self.tracker is not None:
            (self.tracker.on_final if final else self.tracker.on_partial)(text, now)
            return
        if not final:
            self._interim = text
            return
        self._interim = ""
        self._final.append(text)
        heard = intent(text)
        if heard is not None:
            self.handle(heard)

    def on_client_message(self, raw: bytes) -> None:
        ack = protocol.parse_client(raw)
        if ack is None:
            return
        if isinstance(ack, PassageShown):
            self.handle(ack)  # the story is up: the reading clock starts
            return
        # A clip that could not play is over too: do not wait for it.
        self.turns.prompt_finished(self.clock_ms())
        self.handle(ack)

    def on_quick_response(self, response: dict) -> None:
        run = quick_grade.decision(response)
        if run is None:
            if "error" in response:
                log.warning("grade:quick error: %s", response["error"])
            return
        self.handle(QuickScore(run))

    def on_disconnected(self) -> None:
        self.handle(Disconnected())

    def on_reconnected(self) -> None:
        self.handle(Reconnected())

    def tick(self) -> None:
        """Called a few times a second: reading progress, and the end of a turn."""
        now = self.clock_ms()
        if now - self._stats_logged_ms >= STATS_EVERY_MS:
            self._stats_logged_ms = now
            log.info("audio: %s", self.stats.line())
        if self._reading and self.tracker is not None:
            self._reading_tick(now)
        ended = self.turns.tick(now)
        if ended is None:
            return
        if self.state.phase is Phase.MIC_CHECK:
            self._mic_turn_ended(ended, now)
        else:
            self.handle(TurnEnd(ended))

    # ---- actions

    def _run(self, action: Action) -> None:
        match action:
            case PlayClip(clip_id=clip_id) | SpeakLive(clip_id=clip_id):
                # SpeakLive plays the clip until the Gemini Live conductor exists.
                self._send({"cmd": "play", "clip_id": clip_id})
            case PlayWordClip(word_index=index):
                token = self.pair.read["tokens"][index]
                self._send({"cmd": "play", "clip_id": self.catalog.word_clip_id(token)})
            case StartRecording(turn_phase=phase, index=index):
                self._start_turn(phase, index)
            case StopRecording():
                self._stop_turn()
            case CallQuickScore(turn_phase=phase, index=index, answered=answered):
                text = " ".join(self._transcripts.get((phase, index), [])) if answered else ""
                body = quick_grade.request_body(
                    self.ctx.session_id, self.state.passage_id, phase, index, text.strip()
                )
                self.ports.grader.request(body)
            case EmitEvent():
                self._emit(action)
            case RequestPassage(with_tags=with_tags, deadline_ms=deadline_ms):
                interest = self._interest_answer() if with_tags else None
                self.ports.passages.generate(interest, deadline_ms)
            case UseBankPassage():
                self.ports.passages.bank()
            case StartTimer(name=name, ms=ms):
                self.ports.timers.start(name, ms)
            case StreamClipFromStore(clip_id=clip_id):
                url = self.catalog.url(clip_id, **self._passage_ids())
                text = self.catalog.text(clip_id, *self._passages())
                self.ports.channel.send(protocol.clip_list([(clip_id, url, text)]))
                self._send({"cmd": "play", "clip_id": clip_id})
            case ShowPassage():
                self.ports.channel.send(protocol.show_passage(self.pair.read))
            case EndSession(status=status):
                self._write_session(status)
                self.on_end(status)
            case SetFlag() | SetLiveMode() | ClipAck():
                pass  # flags live in the state and reach session.done and the session record
            case Log(reason=reason):
                log.info("machine: %s", reason)
            case _:
                message = protocol.message_for(action, lambda i: "")
                if message is not None:
                    self.ports.channel.send(message)

    def _send(self, message: dict) -> None:
        if message.get("cmd") == "play":
            self.turns.prompt_started(self.clock_ms())
        self.ports.channel.send({"schema_version": protocol.SCHEMA_VERSION, **message})

    def _emit(self, action: EmitEvent) -> None:
        event = build_event(
            action, self.ctx, self.audio, event_id=self.new_event_id(), now=self.wall()
        )
        self.ports.publisher.publish(event)
        if action.type == "session.started":
            self._write_session("STARTED")

    # ---- turns

    def _start_turn(self, phase: str, index: int) -> None:
        if self._turn is not None:
            self._stop_turn()
        now = self.clock_ms()
        self._turn = self.audio.new_turn(phase, index)  # type: ignore[arg-type]
        self._final, self._interim = [], ""
        self.ports.recorder.start(self._turn)
        if phase == "READING":
            self._reading = True
            self.tracker.start(now)
            self.turns.stop()
            return
        if phase == "MIC_CHECK":
            self.mic.reset()
        self.turns.start(_TURN_KIND.get(phase, "answer"), now)

    def _interest_answer(self) -> str | None:
        """What the child said in the interest chat, for the tagger only."""
        parts = [
            text
            for (phase, _), texts in sorted(self._transcripts.items())
            if phase == "INTEREST_CHAT"
            for text in texts
        ]
        return " ".join(parts).strip() or None

    def _stop_turn(self) -> None:
        if self._turn is None:
            return
        turn, self._turn = self._turn, None
        self._reading = False
        self.turns.stop()
        self.ports.recorder.stop()
        text = " ".join([*self._final, self._interim]).strip()
        # Numbers only, never the words: whether this turn was heard at all, and how loud.
        log.info(
            "turn %s %d ended: %s; %s",
            turn.phase,
            turn.index,
            self.stats.end_turn(),
            self.stats.line(),
        )
        self._transcripts.setdefault((turn.phase, turn.index), []).append(text)
        self.ports.documents.set(
            session_store.turn_path(self.ctx.session_id, turn.turn_id),
            session_store.turn_record(turn, live_transcript=text or None),
        )

    def _mic_turn_ended(self, ended: str, now: int) -> None:
        result = self.mic.result() if ended == "ANSWERED" else MicResult(False, "quiet")
        self.handle(result)
        if self.state.phase is Phase.MIC_CHECK and not self.state.mic_done:
            # A retry prompt was played; the recording goes on, so listen again.
            self.mic.reset()
            self.turns.start("mic", now)

    def _reading_tick(self, now: int) -> None:
        if self.turns.ignoring(now):
            self.tracker.hold(now)  # Kemi is still speaking: the first word's wait has not begun
        for event in (
            self.tracker.stall(now),
            self.tracker.progress(now, self.state.told),
            self.tracker.done(now),
            self._reader_finished(now),
        ):
            if event is not None and self._reading:
                self.handle(event)

    def _reader_finished(self, now: int) -> ReadingDone | None:
        """The child has stopped reading although speech to text never matched the last word:
        most of the story followed and a while since they spoke, or any words and a long
        quiet. Without this the reading waited out the 90 s cap."""
        quiet = self.turns.quiet_ms(now)
        if quiet is None or self.turns.ignoring(now) or self.tracker.done_reached:
            return None
        far = self.tracker.fraction_read >= cfg.READING_DONE_FRACTION
        # A child who read only a few words and stopped is not "done": the kindness rule
        # (fewer than 10 words in 30 s) ends that reading kindly, as before.
        read_enough = self.tracker.words_read >= cfg.KINDNESS_MIN_WORDS
        if (far and quiet >= self.state.profile.reading_done_quiet_ms) or (
            read_enough and quiet >= cfg.READING_GAVE_UP_QUIET_MS
        ):
            return ReadingDone(elapsed_ms=self.tracker.elapsed(now))
        return None

    # ---- passages and records

    def _use(self, pair: PassagePair) -> None:
        self.pair = pair
        self.tracker = PositionTracker([t["text"] for t in pair.read["tokens"]])
        profile = self.state.profile
        # A session that never runs the listening module doesn't send its clips, so the phone
        # downloads less. The pair keeps its listening passage: the contracts name it.
        clips = self.catalog.session_clips(
            pair.read,
            pair.listening if profile.listening_module else None,
            profile.n_questions,
            profile.n_listening_items,
        )
        for message in protocol.clip_lists(clips):
            self.ports.channel.send(message)

    def _listening_id(self, pair: PassagePair | None = None) -> str | None:
        pair = pair or self.pair
        if pair is None or pair.listening is None:
            return None
        return pair.listening["passage_id"]

    def _passages(self) -> tuple[dict | None, dict | None]:
        if self.pair is None:
            return None, None
        return self.pair.read, self.pair.listening

    def _passage_ids(self) -> dict:
        if self.pair is None:
            return {}
        return {
            "passage_id": self.pair.read["passage_id"],
            "listening_passage_id": self._listening_id(),
        }

    def _write_session(self, status: str) -> None:
        if self.pair is None:
            return  # nothing to record before a passage exists (schema requires one)
        record = session_store.session_record(
            self.ctx,
            child_id=self.child_id,
            status=status,
            voice_mode=self.voice_mode,
            session_profile=self.profile,
            passage_id=self.pair.read["passage_id"],
            passage_source=self.pair.read["source"],
            flags=self.state.flags,
            created_at=self.created_at,
        )
        self.ports.documents.set(session_store.session_path(self.ctx.session_id), record)
