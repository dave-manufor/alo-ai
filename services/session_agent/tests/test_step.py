"""State machine tests. The machine must stay at 100% line coverage (AGENTS.md rule 10)."""

import dataclasses

import pytest
from services.session_agent.machine import initial_state, step
from services.session_agent.machine import profiles as cfg
from services.session_agent.machine.types import (
    CallQuickScore,
    ChildStop,
    ClipAck,
    Disconnected,
    EmitEvent,
    EndSession,
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

ANSWERED = TurnEnd("ANSWERED")
SILENCE = TurnEnd("SILENCE")


# ---- helpers


def run(state, *events):
    actions = []
    for event in events:
        state, more = step(state, event)
        actions += more
    return state, actions


def T(state, kind):
    return Timer(f"{kind}:{state.task_seq}")


def begin(profile="standard", voice="cache_first", passage=None, live=True, listening=None):
    return run(initial_state(profile, voice), Start(passage, live, listening))


def kinds(actions):
    return [type(a) for a in actions]


def has_timer(actions, kind):
    return any(isinstance(a, StartTimer) and a.name.startswith(f"{kind}:") for a in actions)


# State builders: each returns a state sitting at the start of that task.


def at_interest(**kw):
    return begin(**kw)[0]


def at_mic(**kw):
    return begin(passage="p1", **kw)[0]


def at_mic_waiting():
    state, _ = run(at_interest(), ANSWERED)
    return run(state, MicResult(True))[0]


def at_reading(**kw):
    return run(at_mic(**kw), MicResult(True))[0]


def at_transition(**kw):
    return run(at_reading(**kw), ReadingDone(70_000))[0]


def at_retell(**kw):
    state = at_transition(**kw)
    return run(state, T(state, "transition"))[0]


def at_questions(**kw):
    return run(at_retell(**kw), ANSWERED, ANSWERED)[0]


def at_awaiting(**kw):
    state = at_questions(**kw)
    n = state.profile.n_questions
    return run(state, *([ANSWERED] * n))[0]


def at_listening_story(**kw):
    return run(at_awaiting(**kw), QuickScore(True))[0]


def at_listening_retell(**kw):
    state = at_listening_story(**kw)
    return run(state, T(state, "listening_story"))[0]


def at_listening_ask(**kw):
    return run(at_listening_retell(**kw), ANSWERED)[0]


def at_close():
    return run(at_awaiting(), QuickScore(False))[0]


# ---- start


def test_standard_start_asks_the_interest_question():
    state, actions = begin()
    assert state.phase is Phase.INTEREST_CHAT
    assert actions == [PlayClip("interest_prompt"), StartRecording("INTEREST_CHAT")]
    assert state.flags == ()


def test_demo_profile_sets_flag():
    state, actions = begin(profile="demo")
    assert state.flags == ("DEMO_PROFILE",)
    assert SetFlag("DEMO_PROFILE") in actions


def test_live_first_flags_and_speaks_through_live():
    state, actions = begin(voice="live_first")
    assert state.flags == ("LIVE_FIRST",)
    assert SpeakLive("interest_prompt") in actions


def test_live_first_without_live_uses_clips():
    _, actions = begin(voice="live_first", live=False)
    assert PlayClip("interest_prompt") in actions


def test_returning_child_skips_interest_chat():
    state, actions = begin(passage="p9", listening="l9")
    assert state.phase is Phase.MIC_CHECK
    assert state.passage_ready and state.passage_id == "p9"
    assert state.listening_passage_id == "l9"
    assert actions == [PlayClip("mic_check_prompt"), StartRecording("MIC_CHECK")]


def test_second_start_is_ignored():
    state = at_interest()
    after, actions = step(state, Start())
    assert after == state and isinstance(actions[0], Log)


def test_events_before_start_are_ignored():
    state = initial_state("standard", "cache_first")
    after, actions = step(state, ANSWERED)
    assert after == state and isinstance(actions[0], Log)


def test_stop_before_start_ends_incomplete():
    state, actions = step(initial_state("standard", "cache_first"), ChildStop())
    assert state.phase is Phase.ENDED and state.status == "INCOMPLETE"
    assert EndSession("INCOMPLETE") in actions


def test_disconnect_before_start_is_ignored():
    state = initial_state("standard", "cache_first")
    after, actions = step(state, Disconnected())
    assert not after.disconnected and isinstance(actions[0], Log)


def test_step_does_not_mutate_state():
    state = at_reading()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.phase = Phase.CLOSE  # type: ignore[misc]
    step(state, Silence(5000, 4))
    assert state.told == ()


# ---- 0a interest chat


def test_interest_answer_starts_passage_generation_and_mic_check():
    state, actions = step(at_interest(), ANSWERED)
    assert state.phase is Phase.MIC_CHECK
    assert RequestPassage(with_tags=True, deadline_ms=20_000) in actions
    assert StartTimer("passage_wait", 20_000) in actions
    assert PlayClip("mic_check_prompt") in actions


def test_interest_silence_offers_choices_then_moves_on():
    state, actions = step(at_interest(), SILENCE)
    assert state.phase is Phase.INTEREST_CHAT
    assert actions == [PlayClip("interest_fallback")]
    state, actions = step(state, SILENCE)
    assert state.phase is Phase.MIC_CHECK
    assert RequestPassage(with_tags=False, deadline_ms=20_000) in actions


def test_interest_ignores_other_events():
    state = at_interest()
    after, actions = step(state, MicResult(True))
    assert after == state and isinstance(actions[0], Log)


# ---- 0b mic check and passage arrival


def test_mic_ok_with_passage_ready_starts_reading():
    state, actions = step(at_mic(), MicResult(True))
    assert state.phase is Phase.READING
    assert actions[0] == StopRecording()
    started = next(a for a in actions if isinstance(a, EmitEvent))
    assert started.type == "session.started"
    assert started.data == {
        "passage_id": "p1",
        "voice_mode": "cache_first",
        "session_profile": "standard",
    }
    assert ShowPassage("p1") in actions
    assert StartRecording("READING") in actions
    assert any(isinstance(a, StartTimer) and a.ms == 90_000 for a in actions)


def test_demo_reading_has_the_same_90_second_cap():
    # PRD 4.1: reading is capped at 90 s; a slower reader on stage still finishes.
    _, actions = step(at_mic(profile="demo"), MicResult(True))
    assert any(isinstance(a, StartTimer) and a.ms == 90_000 for a in actions)


def test_mic_ok_without_passage_waits_with_the_cover_clip():
    state = at_mic_waiting()
    assert state.phase is Phase.MIC_CHECK and state.mic_done
    state, actions = run(at_interest(), ANSWERED, MicResult(True))
    assert PlayClip("story_almost_ready") in actions


def test_generated_passage_arriving_during_the_wait_starts_reading():
    state, actions = step(at_mic_waiting(), PassageReady("gen1", "listen1"))
    assert state.phase is Phase.READING and state.passage_id == "gen1"
    assert state.listening_passage_id == "listen1"
    assert "FALLBACK_PASSAGE" not in state.flags
    assert ShowPassage("gen1") in actions


def test_fallback_passage_sets_flag():
    state, actions = step(at_mic_waiting(), PassageFallback("bank1", "bank_listen1"))
    assert state.phase is Phase.READING and state.listening_passage_id == "bank_listen1"
    assert "FALLBACK_PASSAGE" in state.flags
    assert SetFlag("FALLBACK_PASSAGE") in actions


def test_passage_arriving_before_mic_check_finishes_does_not_start_reading():
    state, _ = run(at_interest(), ANSWERED, PassageReady("gen1"))
    assert state.phase is Phase.MIC_CHECK and state.passage_ready
    state, _ = step(state, MicResult(True))
    assert state.phase is Phase.READING


def test_late_passage_is_ignored():
    state = at_reading()
    after, actions = step(state, PassageReady("late"))
    assert after == state and isinstance(actions[0], Log)


def test_passage_wait_timer_asks_for_the_bank_passage():
    state = at_mic_waiting()
    _, actions = step(state, Timer("passage_wait"))
    assert actions == [UseBankPassage()]


def test_passage_wait_timer_after_passage_is_ready_is_ignored():
    state = at_reading()
    after, actions = step(state, Timer("passage_wait"))
    assert after == state and isinstance(actions[0], Log)


@pytest.mark.parametrize(
    ("problem", "clip"), [("quiet", "mic_closer"), ("loud", "mic_softer"), (None, "mic_softer")]
)
def test_mic_problem_gets_one_retry(problem, clip):
    state, actions = step(at_mic(), MicResult(False, problem))
    assert state.phase is Phase.MIC_CHECK and not state.mic_done
    assert actions == [PlayClip(clip)]


def test_second_mic_failure_sets_low_audio_and_continues():
    state, actions = run(at_mic(), MicResult(False, "quiet"), MicResult(False, "quiet"))
    assert state.phase is Phase.READING
    assert "LOW_AUDIO" in state.flags
    assert SetFlag("LOW_AUDIO") in actions


def test_second_mic_failure_still_waits_for_the_passage():
    state, _ = run(at_interest(), ANSWERED, MicResult(False, "loud"), MicResult(False, "loud"))
    assert state.phase is Phase.MIC_CHECK and state.mic_done
    assert "LOW_AUDIO" in state.flags


def test_mic_result_after_the_check_is_ignored():
    state = at_mic_waiting()
    after, actions = step(state, MicResult(False, "quiet"))
    assert after == state and isinstance(actions[0], Log)


def test_mic_ignores_other_events():
    state = at_mic()
    after, actions = step(state, ANSWERED)
    assert after == state and isinstance(actions[0], Log)


# ---- 1 oral reading


def test_three_seconds_on_one_word_plays_the_word_clip_once():
    state, actions = step(at_reading(), Silence(5000, 4))
    assert actions == [PlayWordClip(4)]
    assert state.told == (4,)
    state, actions = step(state, Silence(5200, 4))
    assert isinstance(actions[0], Log) and state.told == (4,)
    state, actions = step(state, Silence(5000, 9))
    assert actions == [PlayWordClip(9)] and state.told == (4, 9)


def test_short_or_wordless_silence_does_nothing():
    state = at_reading()
    assert isinstance(step(state, Silence(4999, 4))[1][0], Log)
    assert isinstance(step(state, Silence(5000, None))[1][0], Log)


def test_told_word_is_always_a_clip_even_in_live_first():
    _, actions = step(at_reading(voice="live_first"), Silence(5000, 2))
    assert actions == [PlayWordClip(2)]


def test_progress_before_the_kindness_window_does_nothing():
    state = at_reading()
    assert step(state, ReadingProgress(10_000, 0)) == (state, [])


def test_enough_words_in_the_first_30_seconds_keeps_reading():
    state, actions = step(at_reading(), ReadingProgress(30_000, 10))
    assert state.phase is Phase.READING and state.kindness_checked and actions == []
    again = step(state, ReadingProgress(40_000, 3))
    assert again == (state, [])


def test_fewer_than_ten_words_in_30_seconds_ends_kindly_and_skips_to_listening():
    told = run(at_reading(), Silence(5000, 1))[0]
    state, actions = step(told, ReadingProgress(30_000, 9))
    assert state.phase is Phase.LISTENING and state.sub == "story"
    assert state.reading_stopped_early and state.listening_run
    recorded = next(a for a in actions if isinstance(a, EmitEvent))
    assert recorded.type == "phase1.recorded"
    assert recorded.data == {"passage_id": "p1", "told_token_indices": [1]}
    assert HidePassage() in actions
    assert PlayClip("kind_end") in actions and PlayClip("listening_story") in actions


@pytest.mark.parametrize("elapsed_ms", [45_000, 80_000])
def test_finishing_the_passage_goes_to_the_transition_without_a_flag(elapsed_ms):
    # SHORT_READING is the Scorer's flag (PRD 6.1), however quickly the child read.
    state, actions = step(at_reading(), ReadingDone(elapsed_ms))
    assert state.phase is Phase.TRANSITION and state.flags == ()
    assert not any(isinstance(a, SetFlag) for a in actions)
    assert any(isinstance(a, EmitEvent) and a.type == "phase1.recorded" for a in actions)
    assert has_timer(actions, "transition")


def test_reading_cap_ends_the_reading():
    state = at_reading()
    after, actions = step(state, T(state, "reading_cap"))
    assert after.phase is Phase.TRANSITION and after.flags == ()
    assert has_timer(actions, "transition")


def test_stale_timer_is_ignored():
    state = at_reading()
    after, actions = step(state, Timer("reading_cap:999"))
    assert after == state and isinstance(actions[0], Log)


def test_reading_ignores_turn_ends():
    state = at_reading()
    assert isinstance(step(state, ANSWERED)[1][0], Log)


def test_missing_clip_is_streamed_from_the_store():
    assert step(at_reading(), ClipAck("word_x", "missing"))[1] == [StreamClipFromStore("word_x")]
    assert step(at_reading(), ClipAck("word_x", "played"))[1] == []


# ---- transition and 2A retell


def test_transition_waits_two_seconds_then_asks_for_the_retell():
    state = at_transition()
    _, actions = step(state, T(state, "transition"))
    assert PlayClip("retell_prompt") in actions
    assert StartRecording("RETELL") in actions
    assert any(isinstance(a, StartTimer) and a.ms == 45_000 for a in actions)


def test_transition_ignores_other_events():
    state = at_transition()
    assert isinstance(step(state, ANSWERED)[1][0], Log)


def test_retell_gets_one_neutral_follow_up():
    state, actions = step(at_retell(), ANSWERED)
    assert state.sub == "followup"
    assert actions == [StopRecording(), PlayClip("anything_else"), StartRecording("RETELL")]
    state, actions = step(state, ANSWERED)
    assert state.phase is Phase.QUESTIONS and state.index == 0
    assert CallQuickScore("RETELL", 0) in actions
    assert PlayClip("question:0") in actions


def test_retell_silence_gets_one_nudge_then_moves_on():
    state, actions = step(at_retell(), SILENCE)
    assert state.phase is Phase.RETELL and actions == [PlayClip("take_your_time")]
    state, actions = step(state, SILENCE)
    assert state.phase is Phase.QUESTIONS
    assert CallQuickScore("RETELL", 0, answered=False) in actions


def test_silence_after_the_follow_up_moves_on():
    state, actions = run(at_retell(), ANSWERED, SILENCE)
    assert state.phase is Phase.QUESTIONS
    assert CallQuickScore("RETELL", 0, answered=True) in actions


def test_retell_cap_moves_on():
    state = at_retell()
    after, actions = step(state, T(state, "retell_cap"))
    assert after.phase is Phase.QUESTIONS
    assert CallQuickScore("RETELL", 0, answered=True) in actions


def test_retell_ignores_repeat_requests():
    state = at_retell()
    assert isinstance(step(state, RepeatRequest())[1][0], Log)


# ---- 2B questions


def test_questions_run_in_order_and_each_answer_is_quick_scored():
    state = at_questions()
    state, actions = step(state, ANSWERED)
    assert state.index == 1
    assert actions[:2] == [StopRecording(), CallQuickScore("QUESTION", 0)]
    assert PlayClip("question:1") in actions
    state, actions = step(state, ANSWERED)
    assert state.index == 2 and PlayClip("question:2") in actions
    state, actions = step(state, ANSWERED)
    assert state.phase is Phase.QUESTIONS and state.sub == "awaiting_quick"
    assert CallQuickScore("QUESTION", 2) in actions
    assert has_timer(actions, "quick_score")


def test_demo_asks_two_questions():
    state = at_awaiting(profile="demo")
    assert state.sub == "awaiting_quick" and state.profile.n_questions == 2


def test_answer_cap_counts_as_an_answer():
    state = at_questions()
    after, actions = step(state, T(state, "answer_cap"))
    assert after.index == 1 and CallQuickScore("QUESTION", 0) in actions


def test_two_silences_move_on_and_score_the_item_as_unanswered():
    # Every item reaches grade:quick, or the listening decision never completes.
    state, actions = step(at_questions(), SILENCE)
    assert actions == [PlayClip("take_your_time")]
    state, actions = step(state, SILENCE)
    assert state.index == 1
    assert PlayClip("lets_go_next") in actions
    assert CallQuickScore("QUESTION", 0, answered=False) in actions


def test_an_unanswered_last_question_still_reaches_the_quick_score_wait():
    state = at_questions()
    last = state.profile.n_questions - 1
    state = run(state, *([ANSWERED] * last))[0]
    state, actions = run(state, SILENCE, SILENCE)
    assert state.sub == "awaiting_quick"
    assert CallQuickScore("QUESTION", last, answered=False) in actions


def test_one_repeat_per_prompt():
    state, actions = step(at_questions(), RepeatRequest())
    assert actions == [StopRecording(), PlayClip("question:0"), StartRecording("QUESTION")]
    state, actions = step(state, RepeatRequest())
    assert isinstance(actions[0], Log)
    state, actions = step(state, ANSWERED)
    assert StartRecording("QUESTION", 1) in actions  # each answer says which item it is
    _, actions = step(state, RepeatRequest())  # a new prompt allows a new repeat
    assert PlayClip("question:1") in actions
    assert StartRecording("QUESTION", 1) in actions


def test_question_phase_ignores_reading_events():
    state = at_questions()
    assert isinstance(step(state, Silence(5000, 1))[1][0], Log)


def test_the_grader_saying_no_listening_goes_to_close():
    state, actions = step(at_awaiting(), QuickScore(run_listening_module=False))
    assert state.phase is Phase.CLOSE and not state.listening_run
    assert PlayClip("close_praise") in actions


def test_the_grader_saying_listening_runs_the_listening_module():
    state, actions = step(at_awaiting(), QuickScore(run_listening_module=True))
    assert state.phase is Phase.LISTENING and state.listening_run
    assert actions[0] == PlayClip("listening_story")


def test_quick_score_timeout_runs_the_listening_module():
    state = at_awaiting()
    after, _ = step(state, T(state, "quick_score"))
    assert after.phase is Phase.LISTENING


def test_awaiting_quick_ignores_other_events():
    state = at_awaiting()
    assert isinstance(step(state, ANSWERED)[1][0], Log)


# ---- 3 listening module


def test_listening_story_is_a_clip_even_in_live_first():
    _, actions = step(at_awaiting(voice="live_first"), QuickScore(True))
    assert actions[0] == PlayClip("listening_story")


def test_listening_story_length_follows_the_profile():
    _, standard = step(at_awaiting(), QuickScore(True))
    _, demo = step(at_awaiting(profile="demo"), QuickScore(True))
    assert StartTimer(standard[1].name, 40_000) == standard[1]
    assert StartTimer(demo[1].name, 20_000) == demo[1]


def test_story_then_retell_then_items_then_close():
    state = at_listening_story()
    after, _ = step(state, ANSWERED)  # ignored while the story plays
    assert after == state
    state, actions = step(state, T(state, "listening_story"))
    assert state.sub == "retell"
    assert PlayClip("listening_retell_prompt") in actions
    assert StartRecording("LISTENING_RETELL") in actions
    state, actions = step(state, ANSWERED)
    assert state.sub == "ask" and state.index == 0
    assert PlayClip("listening_item:0") in actions
    assert StartRecording("LISTENING_QUESTION") in actions
    state, actions = step(state, ANSWERED)
    assert state.index == 1 and PlayClip("listening_item:1") in actions
    assert not any(isinstance(a, CallQuickScore) for a in actions)
    state, actions = step(state, ANSWERED)
    assert state.phase is Phase.CLOSE


def test_demo_listening_has_one_item():
    state = at_listening_ask(profile="demo")
    state, _ = step(state, ANSWERED)
    assert state.phase is Phase.CLOSE


def test_listening_retell_cap_moves_to_items():
    state = at_listening_retell()
    after, _ = step(state, T(state, "listening_retell_cap"))
    assert after.sub == "ask"


def test_listening_retell_silence_nudges_then_moves_on():
    state, actions = step(at_listening_retell(), SILENCE)
    assert actions == [PlayClip("take_your_time")]
    state, actions = step(state, SILENCE)
    assert state.sub == "ask" and PlayClip("lets_go_next") in actions


def test_listening_retell_ignores_other_events():
    state = at_listening_retell()
    assert isinstance(step(state, RepeatRequest())[1][0], Log)


def test_listening_items_allow_one_repeat_and_silence_moves_on():
    state, actions = step(at_listening_ask(), RepeatRequest())
    assert PlayClip("listening_item:0") in actions
    state, _ = run(state, SILENCE, SILENCE)
    assert state.index == 1


def test_a_kindly_ended_reading_is_reported_as_stopped_early():
    state = run(at_reading(listening="l1"), ReadingProgress(30_000, 2))[0]
    answers = [ANSWERED] * (1 + state.profile.n_listening_items)  # retell, then the items
    state = run(state, T(state, "listening_story"), *answers)[0]
    _, actions = step(state, T(state, "close"))
    done = actions[0].data
    assert done["reading_stopped_early"] is True and done["listening_module_run"] is True
    assert done["listening_passage_id"] == "l1"


# ---- 4 close and the end of the session


def test_close_ends_the_session_and_publishes_session_done():
    state = at_close()
    state, actions = step(state, T(state, "close"))
    assert state.phase is Phase.ENDED and state.status == "COMPLETE"
    done = actions[0]
    assert done.type == "session.done"
    # No listening module, so no listening passage is named.
    assert done.data == {
        "passage_id": "p1",
        "flags": [],
        "reading_stopped_early": False,
        "listening_module_run": False,
        "session_settings": {"voice_mode": "cache_first", "session_profile": "standard"},
    }
    assert actions[1] == EndSession("COMPLETE")


def test_session_done_reports_listening_and_flags():
    state = run(at_listening_ask(profile="demo", listening="l1"), ANSWERED)[0]
    _, actions = step(state, T(state, "close"))
    assert actions[0].data["listening_module_run"] is True
    assert actions[0].data["listening_passage_id"] == "l1"
    assert actions[0].data["reading_stopped_early"] is False
    assert actions[0].data["flags"] == ["DEMO_PROFILE"]


def test_close_ignores_other_events():
    state = at_close()
    assert isinstance(step(state, ANSWERED)[1][0], Log)


def test_nothing_happens_after_the_end():
    state = at_close()
    state, _ = step(state, T(state, "close"))
    assert step(state, ANSWERED) == (state, [Log("TurnEnd ignored in ENDED")])


def test_full_standard_session_emits_events_in_order():
    state = initial_state("standard", "cache_first")
    state, actions = run(
        state,
        Start(),
        ANSWERED,
        PassageReady("gen1"),
        MicResult(True),
        Silence(5000, 7),
        ReadingDone(75_000),
    )
    state, more = run(state, T(state, "transition"))
    state, more2 = run(state, ANSWERED, ANSWERED, ANSWERED, ANSWERED, ANSWERED, QuickScore(False))
    state, more3 = run(state, T(state, "close"))
    events = [a.type for a in actions + more + more2 + more3 if isinstance(a, EmitEvent)]
    assert events == ["session.started", "phase1.recorded", "session.done"]
    assert state.phase is Phase.ENDED


# ---- stop


def test_stop_during_reading_hides_the_passage_and_ends_incomplete():
    state, actions = step(at_reading(), ChildStop())
    assert state.phase is Phase.ENDED and state.status == "INCOMPLETE"
    assert actions == [
        StopRecording(),
        HidePassage(),
        PlayClip("stop_praise"),
        EndSession("INCOMPLETE"),
    ]


def test_stop_elsewhere_ends_with_praise():
    _, actions = step(at_retell(), ChildStop())
    assert actions == [StopRecording(), PlayClip("stop_praise"), EndSession("INCOMPLETE")]


# ---- Gemini Live health


def test_two_slow_turns_fall_back_to_clips():
    state = at_interest(voice="live_first")
    state, actions = step(state, LiveTurnLatency(2600))
    assert state.live_active and actions == []
    state, actions = step(state, LiveTurnLatency(2600))
    assert not state.live_active and "LIVE_FALLBACK" in state.flags
    assert actions == [SetFlag("LIVE_FALLBACK"), SetLiveMode("clips")]
    _, actions = step(state, SILENCE)
    assert actions == [PlayClip("interest_fallback")]  # clips from now on


def test_fast_turns_do_not_count():
    state = at_interest()
    state, actions = run(state, LiveTurnLatency(2500), LiveTurnLatency(100))
    assert state.live_slow_turns == 0 and actions == []


def test_live_error_falls_back_at_once_and_only_once():
    state, actions = step(at_interest(), LiveError())
    assert "LIVE_FALLBACK" in state.flags and SetLiveMode("clips") in actions
    assert step(state, LiveError()) == (state, [])


def test_live_error_without_live_changes_nothing():
    state = at_interest(live=False)
    assert step(state, LiveError()) == (state, [])


# ---- disconnect and resume

RESTARTS = {
    "interest": (at_interest, Phase.INTEREST_CHAT, ("play", "interest_prompt")),
    "mic": (at_mic, Phase.MIC_CHECK, ("play", "mic_check_prompt")),
    "mic_waiting": (at_mic_waiting, Phase.MIC_CHECK, ("play", "story_almost_ready")),
    "reading": (at_reading, Phase.TRANSITION, ("timer", "transition")),
    "transition": (at_transition, Phase.TRANSITION, ("timer", "transition")),
    "retell": (at_retell, Phase.RETELL, ("play", "retell_prompt")),
    "question": (at_questions, Phase.QUESTIONS, ("play", "question:0")),
    "awaiting": (at_awaiting, Phase.QUESTIONS, ("timer", "quick_score")),
    "listening_story": (at_listening_story, Phase.LISTENING, ("play", "listening_story")),
    "listening_retell": (
        at_listening_retell,
        Phase.LISTENING,
        ("play", "listening_retell_prompt"),
    ),
    "listening_item": (at_listening_ask, Phase.LISTENING, ("play", "listening_item:0")),
    "close": (at_close, Phase.CLOSE, ("timer", "close")),
}


@pytest.mark.parametrize("name", RESTARTS)
def test_reconnect_restarts_the_current_task(name):
    build, phase, expected = RESTARTS[name]
    state = build()
    dropped, actions = step(state, Disconnected())
    assert dropped.disconnected
    assert actions == [
        StopRecording(),
        ShowReconnecting(),
        PlayClip("wait_for_internet"),
        StartTimer("reconnect", 30_000),
    ]
    resumed, actions = step(dropped, Reconnected())
    assert not resumed.disconnected and resumed.phase is phase
    assert "RECONNECTED" in resumed.flags and SetFlag("RECONNECTED") in actions
    kind, value = expected
    if kind == "play":
        assert PlayClip(value) in actions
    else:
        assert has_timer(actions, value)


def test_an_interrupted_reading_is_not_repeated():
    state = run(at_reading(), Silence(5000, 3))[0]
    _, actions = run(state, Disconnected(), Reconnected())
    recorded = next(a for a in actions if isinstance(a, EmitEvent))
    assert recorded.data["told_token_indices"] == [3]
    assert not any(isinstance(a, ShowPassage) for a in actions)


def test_a_second_drop_does_not_repeat_the_flag():
    state, actions = run(
        at_questions(), Disconnected(), Reconnected(), Disconnected(), Reconnected()
    )
    assert state.flags == ("RECONNECTED",)
    assert actions.count(SetFlag("RECONNECTED")) == 1


def test_a_timer_from_before_the_drop_is_ignored_after_resume():
    state = at_retell()
    old_cap = T(state, "retell_cap")
    resumed, _ = run(state, Disconnected(), Reconnected())
    after, actions = step(resumed, old_cap)
    assert after == resumed and isinstance(actions[0], Log)


def test_reconnect_wait_runs_out_and_the_session_ends_incomplete():
    state, actions = run(at_questions(), Disconnected(), Timer("reconnect"))
    assert state.phase is Phase.ENDED and state.status == "INCOMPLETE"
    assert EndSession("INCOMPLETE") in actions


def test_events_while_disconnected_are_ignored():
    dropped = run(at_questions(), Disconnected())[0]
    after, actions = step(dropped, ANSWERED)
    assert after == dropped and isinstance(actions[0], Log)
    assert step(dropped, Disconnected())[0] == dropped


def test_passage_arriving_while_disconnected_is_kept_and_used_on_resume():
    state = run(at_mic_waiting(), Disconnected())[0]
    state, actions = step(state, PassageReady("gen1"))
    assert state.passage_ready and state.phase is Phase.MIC_CHECK and actions == []
    state, actions = step(state, Reconnected())
    assert state.phase is Phase.READING
    assert ShowPassage("gen1") in actions


def test_fallback_passage_while_disconnected_keeps_the_flag():
    state = run(at_mic_waiting(), Disconnected())[0]
    state, _ = step(state, PassageFallback("bank1"))
    assert "FALLBACK_PASSAGE" in state.flags


def test_passage_wait_timer_while_disconnected_still_asks_for_the_bank_passage():
    state = run(at_mic_waiting(), Disconnected())[0]
    assert step(state, Timer("passage_wait"))[1] == [UseBankPassage()]


def test_reconnected_when_not_disconnected_is_ignored():
    state = at_reading()
    assert isinstance(step(state, Reconnected())[1][0], Log)
    assert isinstance(step(state, Timer("reconnect"))[1][0], Log)


# ---- profiles


def test_profile_values_match_the_prd():
    assert cfg.STANDARD.n_questions == 3 and cfg.DEMO.n_questions == 2
    assert cfg.STANDARD.n_listening_items == 2 and cfg.DEMO.n_listening_items == 1
    assert cfg.STANDARD.reading_cap_ms == cfg.DEMO.reading_cap_ms == 90_000
    assert cfg.TOLD_WORD_MS == 5_000
    assert not hasattr(cfg, "LISTENING_RC_THRESHOLD")  # the listening decision is scoring's
