"""Types for the Session Agent state machine (PRD 4, SDD 4).

Everything here is immutable data. The machine itself is `step.step`, a pure
function: (state, event) -> (state, actions). It does no I/O, reads no clock and
never computes a score. Events come in from the adapter; actions go out to it.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class Phase(Enum):
    INIT = "INIT"
    INTEREST_CHAT = "INTEREST_CHAT"
    MIC_CHECK = "MIC_CHECK"
    READING = "READING"
    TRANSITION = "TRANSITION"
    RETELL = "RETELL"
    QUESTIONS = "QUESTIONS"
    LISTENING = "LISTENING"
    CLOSE = "CLOSE"
    ENDED = "ENDED"


# Turn phases as written to sessions/{id}/turns/{id} (schemas/session_record.schema.json).
TurnPhase = Literal[
    "INTEREST_CHAT",
    "MIC_CHECK",
    "READING",
    "RETELL",
    "QUESTION",
    "LISTENING_RETELL",
    "LISTENING_QUESTION",
]

SessionStatus = Literal["STARTED", "COMPLETE", "INCOMPLETE"]


@dataclass(frozen=True)
class Profile:
    """Session profile (PRD 4.1). Chosen by server env, never by the browser."""

    name: str
    reading_cap_ms: int
    n_questions: int
    n_listening_items: int
    listening_story_ms: int


@dataclass(frozen=True)
class SessionState:
    phase: Phase
    profile: Profile
    voice_mode: str
    sub: str = ""
    index: int = 0
    task_seq: int = 0
    silences: int = 0
    repeat_used: bool = False
    mic_retries: int = 0
    mic_done: bool = False
    passage_id: str | None = None
    listening_passage_id: str | None = None
    passage_ready: bool = False
    told: tuple[int, ...] = ()
    kindness_checked: bool = False
    reading_stopped_early: bool = False
    flags: tuple[str, ...] = ()
    live_active: bool = True
    live_slow_turns: int = 0
    listening_run: bool = False
    disconnected: bool = False
    streamed: tuple[str, ...] = ()  # clips already streamed from the store after a `missing`
    status: SessionStatus = "STARTED"


# ---- Events (SDD 4: turn_end, silence, passage_ready, passage_fallback,
# ---- quick_score, live_degraded, disconnected, reconnected, child_stop, timer)


@dataclass(frozen=True)
class Start:
    """Begin the session. A returning child arrives with the passage already made."""

    passage_id: str | None = None
    live_available: bool = True
    listening_passage_id: str | None = None


@dataclass(frozen=True)
class TurnEnd:
    """The end of the child's turn, from end-of-speech detection or the conductor.

    ANSWERED: the child spoke and finished (for a retell, after 4 s of silence).
    SILENCE: the child said nothing for 8 s.
    """

    reason: Literal["ANSWERED", "SILENCE"]


@dataclass(frozen=True)
class Silence:
    """The child stalled on one word while reading (the position tracker's report)."""

    ms: int
    word_index: int | None = None


@dataclass(frozen=True)
class ReadingProgress:
    elapsed_ms: int
    words_read: int


@dataclass(frozen=True)
class ReadingDone:
    """The child reached the last word of the passage."""

    elapsed_ms: int


@dataclass(frozen=True)
class MicResult:
    ok: bool
    problem: Literal["quiet", "loud"] | None = None


@dataclass(frozen=True)
class PassageReady:
    """listening_passage_id is the passage's paired_listening_passage_id."""

    passage_id: str
    listening_passage_id: str | None = None


@dataclass(frozen=True)
class PassageFallback:
    """A bank passage is used (the generator fell back, or the 20 s wait ran out)."""

    passage_id: str
    listening_passage_id: str | None = None


@dataclass(frozen=True)
class QuickScore:
    """The Grader's listening decision (grade:quick, PRD 6.5). Only a complete response
    is forwarded; if none arrives in time, the quick_score timer runs the module."""

    run_listening_module: bool


@dataclass(frozen=True)
class RepeatRequest:
    """The child asked to hear the prompt again (allowed once per prompt)."""


@dataclass(frozen=True)
class LiveTurnLatency:
    ms: int


@dataclass(frozen=True)
class LiveError:
    pass


@dataclass(frozen=True)
class Disconnected:
    pass


@dataclass(frozen=True)
class Reconnected:
    pass


@dataclass(frozen=True)
class ChildStop:
    pass


@dataclass(frozen=True)
class ClipAck:
    clip_id: str
    status: Literal["played", "missing"]


@dataclass(frozen=True)
class Timer:
    name: str


Event = (
    Start
    | TurnEnd
    | Silence
    | ReadingProgress
    | ReadingDone
    | MicResult
    | PassageReady
    | PassageFallback
    | QuickScore
    | RepeatRequest
    | LiveTurnLatency
    | LiveError
    | Disconnected
    | Reconnected
    | ChildStop
    | ClipAck
    | Timer
)


# ---- Actions (SDD 4: PlayClip, SpeakLive, StartRecording, StopRecording,
# ---- ShowPassage, HidePassage, CallQuickScore, EmitEvent, SetLiveMode)


@dataclass(frozen=True)
class PlayClip:
    clip_id: str


@dataclass(frozen=True)
class PlayWordClip:
    """Play the pre-made "That word is X." clip for one passage token. Always a clip."""

    word_index: int


@dataclass(frozen=True)
class SpeakLive:
    """Gemini Live speaks the exact text of this clip; the clip plays if Live is late."""

    clip_id: str
    fallback_after_ms: int = 1500


@dataclass(frozen=True)
class StartRecording:
    """index: the scripted item being answered (0 for every other turn)."""

    turn_phase: TurnPhase
    index: int = 0


@dataclass(frozen=True)
class StopRecording:
    pass


@dataclass(frozen=True)
class ShowPassage:
    passage_id: str


@dataclass(frozen=True)
class HidePassage:
    pass


@dataclass(frozen=True)
class ShowReconnecting:
    pass


@dataclass(frozen=True)
class RequestPassage:
    """Start passage generation. with_tags: use the interest chat answer."""

    with_tags: bool
    deadline_ms: int


@dataclass(frozen=True)
class UseBankPassage:
    """Pick a bank passage; the adapter answers with PassageFallback."""


@dataclass(frozen=True)
class CallQuickScore:
    """Ask grade:quick to score one turn. answered=False: the child said nothing, so the
    adapter sends an empty transcript (scored 0 without a model call)."""

    turn_phase: TurnPhase
    index: int
    answered: bool = True


@dataclass(frozen=True)
class EmitEvent:
    """Publish an event. The adapter adds the envelope and the fields it owns."""

    type: Literal["session.started", "phase1.recorded", "session.done"]
    data: dict[str, Any]


@dataclass(frozen=True)
class SetFlag:
    flag: str


@dataclass(frozen=True)
class SetLiveMode:
    mode: Literal["live", "clips"]


@dataclass(frozen=True)
class StartTimer:
    name: str
    ms: int


@dataclass(frozen=True)
class StreamClipFromStore:
    clip_id: str


@dataclass(frozen=True)
class EndSession:
    status: Literal["COMPLETE", "INCOMPLETE"]


@dataclass(frozen=True)
class Log:
    """An event the machine ignored, and why."""

    reason: str


Action = (
    PlayClip
    | PlayWordClip
    | SpeakLive
    | StartRecording
    | StopRecording
    | ShowPassage
    | HidePassage
    | ShowReconnecting
    | RequestPassage
    | UseBankPassage
    | CallQuickScore
    | EmitEvent
    | SetFlag
    | SetLiveMode
    | StartTimer
    | StreamClipFromStore
    | EndSession
    | Log
)
