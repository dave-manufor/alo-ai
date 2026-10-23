from services.session_agent.turns import (
    ANSWER_END_MS,
    ECHO_TAIL_MS,
    MIC_END_MS,
    MIC_MIN_VOICED_MS,
    MIC_SHORT_END_MS,
    PLAY_SAFETY_MS,
    RETELL_END_MS,
    SILENCE_MS,
    TurnTaker,
)


def started(kind="answer", at=0) -> TurnTaker:
    turns = TurnTaker()
    turns.start(kind, at)
    return turns


def test_a_turn_with_no_speech_reports_silence_every_eight_seconds():
    turns = started()
    assert turns.tick(SILENCE_MS - 1) is None
    assert turns.tick(SILENCE_MS) == "SILENCE"
    assert turns.tick(SILENCE_MS + 1) is None
    assert turns.tick(2 * SILENCE_MS) == "SILENCE"


def test_silence_is_not_counted_while_the_prompt_is_still_playing():
    # The agent sent the prompt at 0; the phone was still downloading and playing it.
    turns = started(at=0)
    turns.prompt_started(0)
    assert turns.tick(30_000) is None  # no SILENCE however long it takes
    turns.prompt_finished(30_000)  # the ack: the child's wait starts now
    assert turns.tick(30_000 + SILENCE_MS - 1) is None
    assert turns.tick(30_000 + SILENCE_MS) == "SILENCE"


def test_a_prompt_that_never_acks_stops_blocking_after_the_safety_limit():
    turns = started(at=0)
    turns.prompt_started(0)
    assert turns.tick(PLAY_SAFETY_MS - 1) is None
    assert turns.tick(PLAY_SAFETY_MS) == "SILENCE"


def test_kemis_voice_in_the_room_is_not_the_childs_answer():
    turns = started()
    turns.prompt_started(100)
    assert turns.ignoring(200)
    assert turns.speech_started(200) is False  # the VAD heard the clip coming back
    assert turns.speech_ended(900) is False  # and its end is ignored too
    turns.prompt_finished(1_000)
    assert turns.tick(1_000 + SILENCE_MS) == "SILENCE"  # still nobody has answered


def test_the_end_of_the_clip_still_in_the_room_is_ignored_for_a_moment():
    turns = started()
    turns.prompt_started(0)
    turns.prompt_finished(1_000)
    assert turns.ignoring(1_000 + ECHO_TAIL_MS - 1)
    assert not turns.ignoring(1_000 + ECHO_TAIL_MS)
    assert turns.speech_started(1_000 + ECHO_TAIL_MS) is True
    assert turns.speech_ended(2_000) is True


def test_an_answer_ends_after_the_pause_for_its_kind():
    for kind, end in (("answer", ANSWER_END_MS), ("retell", RETELL_END_MS)):
        turns = started(kind)
        assert turns.speech_started(100)
        assert turns.speech_ended(1_100)
        assert turns.tick(1_100 + end - 1) is None
        assert turns.tick(1_100 + end) == "ANSWERED"
        assert turns.tick(99_999) is None  # over


def test_no_end_while_the_child_is_still_speaking():
    turns = started()
    turns.speech_started(0)
    assert turns.tick(60_000) is None


def test_a_full_count_ends_after_two_seconds_of_quiet():
    turns = started("mic")
    turns.speech_started(100)
    turns.speech_ended(100 + MIC_MIN_VOICED_MS)  # counted for about two seconds
    last = 100 + MIC_MIN_VOICED_MS
    assert turns.tick(last + MIC_END_MS - 1) is None
    assert turns.tick(last + MIC_END_MS) == "ANSWERED"


def test_a_pause_between_numbers_does_not_end_the_count():
    turns = started("mic")
    turns.speech_started(0)
    turns.speech_ended(800)  # "one, two"
    assert turns.tick(800 + 1_500) is None  # a breath: the count goes on
    turns.speech_started(2_400)
    turns.speech_ended(3_400)  # "three, four, five": 1.8 s in all
    turns.speech_started(3_800)
    turns.speech_ended(4_200)
    assert turns.tick(4_200 + MIC_END_MS) == "ANSWERED"  # 2.2 s voiced in all


def test_a_very_short_count_waits_longer_before_it_is_called_over():
    turns = started("mic")
    turns.speech_started(0)
    turns.speech_ended(500)  # half a second: "one"
    assert turns.tick(500 + MIC_END_MS) is None
    assert turns.tick(500 + MIC_SHORT_END_MS) == "ANSWERED"


def test_speech_when_no_turn_is_open_is_accepted_for_the_lights_but_ends_nothing():
    turns = TurnTaker()
    assert turns.speech_started(10) is True
    assert turns.speech_ended(900) is True
    assert turns.tick(60_000) is None
