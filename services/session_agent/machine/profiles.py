"""Session profiles and protocol timings (PRD 4.1 to 4.4).

These are session timings, not scoring constants. Whether the listening module
runs is decided by aloai_scoring (PRD 6.5) and arrives from grade:quick as
run_listening_module, so no [CAL] value lives here.
"""

from .types import Profile

STANDARD = Profile(
    name="standard",
    reading_cap_ms=90_000,
    n_questions=3,
    n_listening_items=2,
    listening_story_ms=40_000,
)

# Demo: 75-word passage, 2 questions, ~50-word listening story, 1 listening item.
# Reading is capped at 90 s in both profiles (PRD 4.1); "demo: 45-60 s" is how long
# a demo reading usually takes, not a cap.
DEMO = Profile(
    name="demo",
    reading_cap_ms=90_000,
    n_questions=2,
    n_listening_items=1,
    listening_story_ms=20_000,
)

PROFILES = {STANDARD.name: STANDARD, DEMO.name: DEMO}

VOICE_MODES = ("cache_first", "live_first")

SHOWN_WAIT_MS = 20_000  # then the reading starts even if the web app never says the story is up
TOLD_WORD_MS = 5_000  # no progress on the same word before "That word is X." (PRD 4.1)
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
