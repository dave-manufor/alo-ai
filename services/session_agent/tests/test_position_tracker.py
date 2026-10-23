from services.session_agent.machine.types import ReadingDone, ReadingProgress, Silence
from services.session_agent.position_tracker import PositionTracker

PASSAGE = ["The", "cat", "sat", "on", "the", "mat."]


def tracker(tokens=PASSAGE, started_at=0):
    t = PositionTracker(tokens)
    t.start(started_at)
    return t


def test_follows_the_child_through_partials_that_grow():
    t = tracker()
    t.on_partial("the", 500)
    assert (t.position, t.words_read) == (1, 1)
    t.on_partial("the cat sat", 1500)
    assert (t.position, t.words_read) == (3, 3)


def test_a_revised_partial_does_not_move_the_child_back():
    t = tracker()
    t.on_partial("the cat sat", 1500)
    t.on_partial("the cat", 1600)
    assert t.position == 3


def test_close_enough_words_match():
    t = tracker()
    t.on_partial("the cats sat", 1000)  # "cats" for "cat"
    assert t.position == 3


def test_a_child_may_skip_a_word_but_it_is_not_counted_as_read():
    t = tracker()
    t.on_partial("the sat", 1000)
    assert t.position == 3 and t.words_read == 2


def test_words_far_ahead_or_unrelated_are_ignored():
    t = tracker()
    t.on_partial("banana the mat", 1000)  # "mat" is beyond the lookahead from "cat"
    assert (t.position, t.words_read) == (1, 1)


def test_a_final_result_starts_the_next_utterance_from_the_new_position():
    t = tracker()
    t.on_final("the cat", 1000)
    t.on_partial("sat on", 2000)
    assert t.position == 4


def test_noise_and_punctuation_in_the_transcript_are_skipped():
    t = tracker()
    t.on_partial("- the ... cat", 1000)
    assert t.position == 2


def test_stray_punctuation_tokens_are_stepped_over():
    t = tracker(["—", "The", "cat", "—", "sat"])
    assert t.position == 1
    t.on_partial("the cat sat", 1000)
    assert t.position == 5 and t.words_read == 3 and t.done_reached


def test_the_first_word_waits_longer_and_is_reported_once():
    t = tracker()
    assert t.stall(2500) is None  # the usual wait is not enough for the first word
    assert t.stall(5499) is None
    assert t.stall(5500) == Silence(ms=5500, word_index=0)  # 2.5 s plus 3 s to settle in
    assert t.stall(15_000) is None  # already reported for this word


def test_sounding_a_word_out_without_progress_still_stalls_after_two_and_a_half_seconds():
    t = tracker()
    t.on_partial("the", 500)
    t.on_partial("the c c", 3000)  # speech, but no new word matched
    assert t.stall(2999) is None
    assert t.stall(3000) == Silence(ms=2500, word_index=1)


def test_progress_resets_the_stall_clock_and_the_next_word_can_stall():
    t = tracker()
    t.on_partial("the cat", 1000)
    assert t.stall(3499) is None
    assert t.stall(3500) == Silence(ms=2500, word_index=2)


def test_no_stall_before_the_reading_starts_or_after_it_ends():
    t = PositionTracker(PASSAGE)
    assert t.stall(10_000) is None
    t.start(0)
    t.on_partial("the cat sat on the mat", 1000)
    assert t.stall(20_000) is None


def test_progress_reports_elapsed_time_and_words_read():
    t = tracker(started_at=1000)
    t.on_partial("the cat", 2000)
    assert t.progress(31_000) == ReadingProgress(elapsed_ms=30_000, words_read=2)
    assert PositionTracker(PASSAGE).progress(5000) == ReadingProgress(0, 0)


def test_words_the_child_was_told_do_not_count_for_the_kindness_rule():
    t = tracker()
    t.on_partial("the cat sat", 1000)
    # "cat" was told and then repeated; "on" (3) was told but never said.
    assert t.progress(30_000, told=(1, 3)) == ReadingProgress(elapsed_ms=30_000, words_read=2)
    assert t.words_read == 3  # the position counter itself is unchanged


def test_done_when_the_last_word_is_reached():
    t = tracker(started_at=1000)
    assert t.done(5000) is None
    t.on_partial("the cat sat on the mat", 4000)
    assert t.done(61_000) == ReadingDone(elapsed_ms=60_000)


def test_the_first_word_waits_from_when_kemi_stops_speaking():
    t = tracker()
    t.hold(4000)  # her line was still playing at 4 s
    assert t.stall(4000 + 5499) is None
    assert t.stall(4000 + 5500) == Silence(ms=5500, word_index=0)


def test_holding_does_nothing_once_the_child_has_started_reading():
    t = tracker()
    t.on_partial("the cat", 1000)
    t.hold(2000)  # the told word's clip, say: the next word's wait is the usual one
    assert t.stall(3499) is None  # not held: counted from the last word read, at 1 s
    assert t.stall(3500) == Silence(ms=2500, word_index=2)


def test_the_extra_wait_is_for_the_first_word_only_even_after_leading_blanks():
    t = tracker(["—", "The", "cat"])  # a blank token is skipped: "The" is the first word
    assert t.stall(5499) is None
    assert t.stall(5500) == Silence(ms=5500, word_index=1)
