"""Session profiles and protocol timings (PRD 4.1 to 4.4).

These are session timings, not scoring constants. Whether the listening module
runs is decided by aloai_scoring (PRD 6.5) and arrives from grade:quick as
run_listening_module, so no [CAL] value lives here.
"""

from .types import Profile

VOICE_MODES = ("cache_first", "live_first")

SHOWN_WAIT_MS = 20_000  # then the reading starts even if the web app never says the story is up
TOLD_WORD_MS = 2_500  # no progress on the same word before "That word is X." (PRD 4.1)
FIRST_WORD_EXTRA_MS = 3_000  # [CAL] the first word gets this long on top: the child is settling in
# The reading also ends when the child has stopped, not only at the story's last word (which
# speech to text often misses) or the 90 s cap [CAL]. Until now a reader who finished but whose
# last words were not recognised waited out the cap (a live session waited about 40 s).
READING_DONE_FRACTION = 0.8  # this much of the story followed...
READING_DONE_QUIET_MS = 8_000  # ...and this long since the child last spoke: they have finished
READING_GAVE_UP_QUIET_MS = 15_000  # 10+ words read, then this long quiet: they have stopped
KINDNESS_WINDOW_MS = 30_000  # first 30 s of reading
KINDNESS_MIN_WORDS = 10  # fewer than this in the window ends the reading kindly
TRANSITION_MS = 2_000
RETELL_CAP_MS = 45_000
LISTENING_RETELL_CAP_MS = 30_000
ANSWER_CAP_MS = 20_000
PASSAGE_WAIT_MS = 20_000  # then the bank passage is used
QUICK_SCORE_TIMEOUT_MS = 6_000
RECONNECT_WAIT_MS = 30_000
CLOSE_MS = 5_000
MAX_SILENCES = 2  # two 8 s silences on one prompt: move on
LIVE_LATENCY_MS = 2_500
LIVE_SLOW_TURNS = 2

STANDARD = Profile(
    name="standard",
    reading_cap_ms=90_000,
    n_questions=3,
    n_listening_items=2,
    listening_story_ms=40_000,
    listening_module=True,
    retell_follow_up=True,
    retell_cap_ms=RETELL_CAP_MS,
    transition_ms=TRANSITION_MS,
    close_ms=CLOSE_MS,
    reading_done_quiet_ms=READING_DONE_QUIET_MS,
)

# Demo: a 50-word passage that matches the child's interest, 2 questions, and no listening
# module, so a session runs in under two minutes (PRD 4.1). The retell has no follow-up and a
# shorter cap, and the waits between stages are shorter. The listening fields are unused.
# Reading is capped at 90 s in both profiles (PRD 4.1); that cap, "That word is X." after
# TOLD_WORD_MS, and the answer rules are the same, so a demo reading is read the same way.
DEMO = Profile(
    name="demo",
    reading_cap_ms=90_000,
    n_questions=2,
    n_listening_items=1,
    listening_story_ms=20_000,
    listening_module=False,
    retell_follow_up=False,
    retell_cap_ms=25_000,
    transition_ms=1_000,
    close_ms=2_000,
    reading_done_quiet_ms=3_000,
)

PROFILES = {STANDARD.name: STANDARD, DEMO.name: DEMO}
