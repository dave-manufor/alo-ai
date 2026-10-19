"""The Session Agent state machine: step(state, event) -> (state, actions).

Pure. No I/O, no clock, no randomness, and no scores: it only branches on the
numbers it is handed (words read, a quick RC from the Grader). The adapter turns
LiveKit, speech and timer callbacks into events and runs the actions.

Timers are named "<kind>:<task_seq>". task_seq goes up every time a new task
starts, so a timer left over from an earlier task is recognised and ignored.

Prompts are said with `_say`: a clip in cache_first, or Gemini Live with a clip
fallback in live_first while Live is healthy. "That word is X." and the
listening story are always clips (PRD 4.2).
"""

from dataclasses import replace

from . import profiles as cfg
from .types import (
    Action,
    CallQuickScore,
    ChildStop,
    ClipAck,
    Disconnected,
    EmitEvent,
    EndSession,
    Event,
    HidePassage,
    LiveError,
    LiveTurnLatency,
    Log,
    MicResult,
    PassageFallback,
    PassageReady,
    Phase,
    PlayClip,
    PlayWordClip,
    QuickScore,
    ReadingDone,
    ReadingProgress,
    Reconnected,
    RepeatRequest,
    RequestPassage,
    SessionState,
    SetFlag,
    SetLiveMode,
    ShowPassage,
    ShowReconnecting,
    Silence,
    SpeakLive,
    Start,
    StartRecording,
    StartTimer,
    StopRecording,
    StreamClipFromStore,
    Timer,
    TurnEnd,
    UseBankPassage,
)

Result = tuple[SessionState, list[Action]]

# Scripted items: (clip id prefix, turn phase recorded).
_ITEMS = {
    Phase.QUESTIONS: ("question", "QUESTION"),
    Phase.LISTENING: ("listening_item", "LISTENING_QUESTION"),
}


def initial_state(profile_name: str, voice_mode: str) -> SessionState:
    return SessionState(
        phase=Phase.INIT, profile=cfg.PROFILES[profile_name], voice_mode=voice_mode
    )


# ---- helpers


def _say(state: SessionState, clip_id: str) -> Action:
    if state.voice_mode == "live_first" and state.live_active:
        return SpeakLive(clip_id)
    return PlayClip(clip_id)


def _timer(kind: str, state: SessionState, ms: int) -> StartTimer:
    return StartTimer(f"{kind}:{state.task_seq}", ms)


def _is_timer(event: Event, kind: str, state: SessionState) -> bool:
    return isinstance(event, Timer) and event.name == f"{kind}:{state.task_seq}"


def _ignored(state: SessionState, event: Event) -> Result:
    return state, [Log(f"{type(event).__name__} ignored in {state.phase.value}")]


def _with_flag(state: SessionState, flag: str) -> Result:
    if flag in state.flags:
        return state, []
    return replace(state, flags=state.flags + (flag,)), [SetFlag(flag)]


def _next_task(state: SessionState, **changes) -> SessionState:
    return replace(state, task_seq=state.task_seq + 1, silences=0, **changes)


# ---- entry point


def step(state: SessionState, event: Event) -> Result:
    if state.phase is Phase.ENDED:
        return _ignored(state, event)
    if state.disconnected:
        return _while_disconnected(state, event)

    match event:
        case Start():
            return _start(state, event)
        case ChildStop():
            return _stop(state)
        case Disconnected():
            return _disconnect(state)
        case LiveTurnLatency(ms=ms):
            return _live_latency(state, ms)
        case LiveError():
            return _live_fallback(state)
        case ClipAck(clip_id=clip_id, status="missing"):
            return state, [StreamClipFromStore(clip_id)]
        case ClipAck():
            return state, []
        case PassageReady() | PassageFallback():
            return _passage(state, event)
        case Timer(name="passage_wait"):
            return _passage_wait(state)

    return _PHASES[state.phase](state, event)


# ---- session start and end


def _start(state: SessionState, event: Start) -> Result:
    if state.phase is not Phase.INIT:
        return _ignored(state, event)
    state = replace(state, live_active=event.live_available)
    actions: list[Action] = []
    if state.profile.name == "demo":
        state, more = _with_flag(state, "DEMO_PROFILE")
        actions += more
    if state.voice_mode == "live_first":
        state, more = _with_flag(state, "LIVE_FIRST")
        actions += more
    if event.passage_id is not None:
        state = replace(
            state,
            passage_id=event.passage_id,
            listening_passage_id=event.listening_passage_id,
            passage_ready=True,
        )
        state, more = _enter_mic_check(state)
        return state, actions + more
    state = replace(state, phase=Phase.INTEREST_CHAT)
    return state, actions + [
        _say(state, "interest_prompt"),
        StartRecording("INTEREST_CHAT"),
    ]


def _stop(state: SessionState) -> Result:
    """The child said stop: praise, and mark the session incomplete (PRD 4.3)."""
    actions: list[Action] = [StopRecording()]
    if state.phase is Phase.READING:
        actions.append(HidePassage())
    actions += [_say(state, "stop_praise"), EndSession("INCOMPLETE")]
    return replace(state, phase=Phase.ENDED, status="INCOMPLETE"), actions


def _end_incomplete(state: SessionState) -> Result:
    return replace(state, phase=Phase.ENDED, status="INCOMPLETE"), [
        StopRecording(),
        EndSession("INCOMPLETE"),
    ]


# ---- passage arrival


def _passage(state: SessionState, event: PassageReady | PassageFallback) -> Result:
    if state.passage_ready:
        return state, [Log("passage already chosen; late arrival ignored")]
    state = replace(
        state,
        passage_id=event.passage_id,
        listening_passage_id=event.listening_passage_id,
        passage_ready=True,
    )
    actions: list[Action] = []
    if isinstance(event, PassageFallback):
        state, actions = _with_flag(state, "FALLBACK_PASSAGE")
    if state.phase is Phase.MIC_CHECK and state.mic_done and not state.disconnected:
        state, more = _enter_reading(state)
        actions += more
    return state, actions


def _passage_wait(state: SessionState) -> Result:
    if state.passage_ready:
        return state, [Log("passage_wait timer after the passage was ready")]
    return state, [UseBankPassage()]


# ---- Gemini Live health (PRD 4.2)


def _live_latency(state: SessionState, ms: int) -> Result:
    if ms <= cfg.LIVE_LATENCY_MS:
        return state, []
    state = replace(state, live_slow_turns=state.live_slow_turns + 1)
    if state.live_slow_turns >= cfg.LIVE_SLOW_TURNS:
        return _live_fallback(state)
    return state, []


def _live_fallback(state: SessionState) -> Result:
    if not state.live_active:
        return state, []
    state = replace(state, live_active=False)
    state, actions = _with_flag(state, "LIVE_FALLBACK")
    return state, actions + [SetLiveMode("clips")]


# ---- connection loss and resume (PRD 4.4)


def _disconnect(state: SessionState) -> Result:
    if state.phase is Phase.INIT:
        return _ignored(state, Disconnected())
    return replace(state, disconnected=True), [
        StopRecording(),
        ShowReconnecting(),
        PlayClip("wait_for_internet"),
        StartTimer("reconnect", cfg.RECONNECT_WAIT_MS),
    ]


def _while_disconnected(state: SessionState, event: Event) -> Result:
    match event:
        case Reconnected():
            return _resume(state)
        case Timer(name="reconnect"):
            return _end_incomplete(state)
        case PassageReady() | PassageFallback():
            return _passage(state, event)
        case Timer(name="passage_wait"):
            return _passage_wait(state)
    return state, [Log(f"{type(event).__name__} ignored while disconnected")]


def _resume(state: SessionState) -> Result:
    """Restart the current task from its start. A broken reading is not repeated."""
    state, actions = _with_flag(replace(state, disconnected=False), "RECONNECTED")
    state, more = _restart_task(state)
    return state, actions + more


def _restart_task(state: SessionState) -> Result:
    match state.phase:
        case Phase.INTEREST_CHAT:
            return state, [_say(state, "interest_prompt"), StartRecording("INTEREST_CHAT")]
        case Phase.MIC_CHECK:
            if state.mic_done and state.passage_ready:
                return _enter_reading(state)
            if state.mic_done:
                return state, [_say(state, "story_almost_ready")]
            return state, [_say(state, "mic_check_prompt"), StartRecording("MIC_CHECK")]
        case Phase.READING:
            return _finish_reading(state, kindly=False)
        case Phase.TRANSITION:
            state = _next_task(state)
            return state, [_timer("transition", state, cfg.TRANSITION_MS)]
        case Phase.RETELL:
            return _enter_retell(state)
        case Phase.QUESTIONS:
            if state.sub == "ask":
                return _ask_item(state, Phase.QUESTIONS, state.index)
            return _await_quick_score(state)
        case Phase.LISTENING:
            if state.sub == "story":
                return _enter_listening(state)
            if state.sub == "retell":
                return _enter_listening_retell(state)
            return _ask_item(state, Phase.LISTENING, state.index)
    # Phase.CLOSE: the only phase left once the others have returned.
    state = _next_task(state)
    return state, [_timer("close", state, cfg.CLOSE_MS)]


# ---- 0a. interest chat


def _interest_chat(state: SessionState, event: Event) -> Result:
    match event:
        case TurnEnd(reason="ANSWERED"):
            return _request_passage(state, with_tags=True)
        case TurnEnd(reason="SILENCE"):
            state = replace(state, silences=state.silences + 1)
            if state.silences < cfg.MAX_SILENCES:
                return state, [_say(state, "interest_fallback")]
            return _request_passage(state, with_tags=False)
    return _ignored(state, event)


def _request_passage(state: SessionState, *, with_tags: bool) -> Result:
    actions: list[Action] = [
        StopRecording(),
        RequestPassage(with_tags=with_tags, deadline_ms=cfg.PASSAGE_WAIT_MS),
        StartTimer("passage_wait", cfg.PASSAGE_WAIT_MS),
    ]
    state, more = _enter_mic_check(state)
    return state, actions + more


# ---- 0b. setup and mic check


def _enter_mic_check(state: SessionState) -> Result:
    state = replace(
        state, phase=Phase.MIC_CHECK, mic_retries=0, mic_done=False, silences=0
    )
    return state, [_say(state, "mic_check_prompt"), StartRecording("MIC_CHECK")]


def _mic_check(state: SessionState, event: Event) -> Result:
    if not isinstance(event, MicResult) or state.mic_done:
        return _ignored(state, event)
    if event.ok:
        return _mic_done(state)
    if state.mic_retries == 0:
        clip = "mic_closer" if event.problem == "quiet" else "mic_softer"
        return replace(state, mic_retries=1), [_say(state, clip)]
    state, actions = _with_flag(state, "LOW_AUDIO")
    state, more = _mic_done(state)
    return state, actions + more


def _mic_done(state: SessionState) -> Result:
    state = replace(state, mic_done=True)
    if state.passage_ready:
        state, actions = _enter_reading(state)
        return state, [StopRecording()] + actions
    return state, [StopRecording(), _say(state, "story_almost_ready")]


# ---- 1. oral reading


def _enter_reading(state: SessionState) -> Result:
    state = _next_task(state, phase=Phase.READING, sub="", told=(), kindness_checked=False)
    return state, [
        EmitEvent(
            "session.started",
            {
                "passage_id": state.passage_id,
                "voice_mode": state.voice_mode,
                "session_profile": state.profile.name,
            },
        ),
        ShowPassage(state.passage_id),
        StartRecording("READING"),
        _timer("reading_cap", state, state.profile.reading_cap_ms),
    ]


def _reading(state: SessionState, event: Event) -> Result:
    match event:
        case Silence(ms=ms, word_index=word_index):
            if word_index is None or ms < cfg.TOLD_WORD_MS:
                return state, [Log("silence too short or not on a word")]
            if word_index in state.told:
                return state, [Log("word already told")]
            return replace(state, told=state.told + (word_index,)), [
                PlayWordClip(word_index)
            ]
        case ReadingProgress(elapsed_ms=elapsed_ms, words_read=words_read):
            if state.kindness_checked or elapsed_ms < cfg.KINDNESS_WINDOW_MS:
                return state, []
            state = replace(state, kindness_checked=True)
            if words_read < cfg.KINDNESS_MIN_WORDS:
                return _finish_reading(state, kindly=True)
            return state, []
        case ReadingDone():
            # SHORT_READING is the Scorer's flag, from forced alignment (PRD 6.1).
            return _finish_reading(state, kindly=False)
        case Timer() if _is_timer(event, "reading_cap", state):
            return _finish_reading(state, kindly=False)
    return _ignored(state, event)


def _finish_reading(state: SessionState, *, kindly: bool) -> Result:
    actions: list[Action] = [
        StopRecording(),
        HidePassage(),
        EmitEvent(
            "phase1.recorded",
            {"passage_id": state.passage_id, "told_token_indices": list(state.told)},
        ),
    ]
    if kindly:
        # Fewer than 10 words in 30 s: stop kindly and go to listening. aloai_scoring sets
        # the next passage level from reading_stopped_early (PRD 4.3, 6.6).
        state = replace(state, reading_stopped_early=True)
        actions.append(_say(state, "kind_end"))
        state, more = _enter_listening(state)
        return state, actions + more
    state = _next_task(state, phase=Phase.TRANSITION)
    return state, actions + [_timer("transition", state, cfg.TRANSITION_MS)]


# ---- transition, 2A. retell


def _transition(state: SessionState, event: Event) -> Result:
    if _is_timer(event, "transition", state):
        return _enter_retell(state)
    return _ignored(state, event)


def _enter_retell(state: SessionState) -> Result:
    state = _next_task(state, phase=Phase.RETELL, sub="main")
    return state, [
        _say(state, "retell_prompt"),
        StartRecording("RETELL"),
        _timer("retell_cap", state, cfg.RETELL_CAP_MS),
    ]


def _retell(state: SessionState, event: Event) -> Result:
    match event:
        case Timer() if _is_timer(event, "retell_cap", state):
            return _finish_retell(state)
        case TurnEnd(reason="ANSWERED"):
            if state.sub == "main":
                # One neutral follow-up, then done.
                return replace(state, sub="followup", silences=0), [
                    StopRecording(),
                    _say(state, "anything_else"),
                    StartRecording("RETELL"),
                ]
            return _finish_retell(state)
        case TurnEnd(reason="SILENCE"):
            state = replace(state, silences=state.silences + 1)
            if state.sub == "main" and state.silences < cfg.MAX_SILENCES:
                return state, [_say(state, "take_your_time")]
            return _finish_retell(state)
    return _ignored(state, event)


def _finish_retell(state: SessionState) -> Result:
    state, actions = _ask_item(state, Phase.QUESTIONS, 0)
    return state, [StopRecording(), CallQuickScore("RETELL", 0)] + actions


# ---- 2B. scripted items and 3. listening items (shared)


def _ask_item(state: SessionState, phase: Phase, index: int) -> Result:
    prefix, record = _ITEMS[phase]
    state = _next_task(state, phase=phase, sub="ask", index=index, repeat_used=False)
    return state, [
        _say(state, f"{prefix}:{index}"),
        StartRecording(record, index),  # type: ignore[arg-type]
        _timer("answer_cap", state, cfg.ANSWER_CAP_MS),
    ]


def _item_event(state: SessionState, event: Event) -> Result:
    prefix, record = _ITEMS[state.phase]
    match event:
        case TurnEnd(reason="ANSWERED"):
            return _item_done(state, answered=True)
        case Timer() if _is_timer(event, "answer_cap", state):
            return _item_done(state, answered=True)
        case TurnEnd(reason="SILENCE"):
            state = replace(state, silences=state.silences + 1)
            if state.silences < cfg.MAX_SILENCES:
                return state, [_say(state, "take_your_time")]
            return _item_done(state, answered=False)
        case RepeatRequest():
            if state.repeat_used:
                return state, [Log("repeat already used for this prompt")]
            state = replace(state, repeat_used=True)
            return state, [
                StopRecording(),
                _say(state, f"{prefix}:{state.index}"),
                StartRecording(record, state.index),  # type: ignore[arg-type]
            ]
    return _ignored(state, event)


def _item_done(state: SessionState, *, answered: bool) -> Result:
    actions: list[Action] = [StopRecording()]
    if not answered:
        actions.append(_say(state, "lets_go_next"))
    scored = state.phase is Phase.QUESTIONS
    if answered and scored:
        actions.append(CallQuickScore("QUESTION", state.index))
    count = state.profile.n_questions if scored else state.profile.n_listening_items
    if state.index + 1 < count:
        state, more = _ask_item(state, state.phase, state.index + 1)
    elif scored:
        state, more = _await_quick_score(state)
    else:
        state, more = _enter_close(state)
    return state, actions + more


# ---- questions: waiting for the quick RC


def _await_quick_score(state: SessionState) -> Result:
    state = _next_task(state, phase=Phase.QUESTIONS, sub="awaiting_quick")
    return state, [_timer("quick_score", state, cfg.QUICK_SCORE_TIMEOUT_MS)]


def _questions(state: SessionState, event: Event) -> Result:
    if state.sub == "ask":
        return _item_event(state, event)
    match event:
        case QuickScore(quick_rc=quick_rc):
            if quick_rc is not None and quick_rc >= cfg.LISTENING_RC_THRESHOLD:
                return _enter_close(state)
            return _enter_listening(state)
        case Timer() if _is_timer(event, "quick_score", state):
            return _enter_listening(state)  # no answer from the Grader in 6 s
    return _ignored(state, event)


# ---- 3. listening module


def _enter_listening(state: SessionState) -> Result:
    state = _next_task(state, phase=Phase.LISTENING, sub="story", listening_run=True)
    return state, [
        PlayClip("listening_story"),  # always a clip
        _timer("listening_story", state, state.profile.listening_story_ms),
    ]


def _enter_listening_retell(state: SessionState) -> Result:
    state = _next_task(state, sub="retell")
    return state, [
        _say(state, "listening_retell_prompt"),
        StartRecording("LISTENING_RETELL"),
        _timer("listening_retell_cap", state, cfg.LISTENING_RETELL_CAP_MS),
    ]


def _listening(state: SessionState, event: Event) -> Result:
    if state.sub == "ask":
        return _item_event(state, event)
    if state.sub == "story":
        if _is_timer(event, "listening_story", state):
            return _enter_listening_retell(state)
        return _ignored(state, event)
    # sub == "retell"
    match event:
        case TurnEnd(reason="ANSWERED"):
            return _listening_retell_done(state, answered=True)
        case Timer() if _is_timer(event, "listening_retell_cap", state):
            return _listening_retell_done(state, answered=True)
        case TurnEnd(reason="SILENCE"):
            state = replace(state, silences=state.silences + 1)
            if state.silences < cfg.MAX_SILENCES:
                return state, [_say(state, "take_your_time")]
            return _listening_retell_done(state, answered=False)
    return _ignored(state, event)


def _listening_retell_done(state: SessionState, *, answered: bool) -> Result:
    actions: list[Action] = [StopRecording()]
    if not answered:
        actions.append(_say(state, "lets_go_next"))
    state, more = _ask_item(state, Phase.LISTENING, 0)
    return state, actions + more


# ---- 4. close


def _enter_close(state: SessionState) -> Result:
    state = _next_task(state, phase=Phase.CLOSE, sub="")
    return state, [_say(state, "close_praise"), _timer("close", state, cfg.CLOSE_MS)]


def _close(state: SessionState, event: Event) -> Result:
    if not _is_timer(event, "close", state):
        return _ignored(state, event)
    data = {
        "passage_id": state.passage_id,
        "flags": list(state.flags),
        "reading_stopped_early": state.reading_stopped_early,
        "listening_module_run": state.listening_run,
        "session_settings": {
            "voice_mode": state.voice_mode,
            "session_profile": state.profile.name,
        },
    }
    actions: list[Action] = []
    if state.listening_run:
        if state.listening_passage_id is None:
            # A READ passage must name its pairing (passage schema), so this is a bug upstream.
            actions.append(
                Log("listening ran without a listening passage; session.done is invalid")
            )
        data["listening_passage_id"] = state.listening_passage_id
    done = EmitEvent("session.done", data)
    return replace(state, phase=Phase.ENDED, status="COMPLETE"), actions + [
        done,
        EndSession("COMPLETE"),
    ]


def _init(state: SessionState, event: Event) -> Result:
    return _ignored(state, event)


_PHASES = {
    Phase.INIT: _init,
    Phase.INTEREST_CHAT: _interest_chat,
    Phase.MIC_CHECK: _mic_check,
    Phase.READING: _reading,
    Phase.TRANSITION: _transition,
    Phase.RETELL: _retell,
    Phase.QUESTIONS: _questions,
    Phase.LISTENING: _listening,
    Phase.CLOSE: _close,
}
