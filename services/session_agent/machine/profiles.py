"""Session profiles and protocol timings (PRD 4.1 to 4.4).

These are session timings, not scoring constants. The one exception is
LISTENING_RC_THRESHOLD, which mirrors the [CAL] value in PRD 6.5 owned by W3;
change it only with W3 (alo-scoring-change).
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
# The 60 s reading cap is our reading of "demo: 45-60 s" in PRD 4.1.
DEMO = Profile(
    name="demo",
    reading_cap_ms=60_000,
    n_questions=2,
    n_listening_items=1,
    listening_story_ms=20_000,
)

PROFILES = {STANDARD.name: STANDARD, DEMO.name: DEMO}

VOICE_MODES = ("cache_first", "live_first")

TOLD_WORD_MS = 3_000  # silence on the same word before "That word is X."
KINDNESS_WINDOW_MS = 30_000  # first 30 s of reading
KINDNESS_MIN_WORDS = 10  # fewer than this in the window ends the reading kindly
SHORT_READING_MS = 60_000  # reading shorter than this carries SHORT_READING
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
LISTENING_RC_THRESHOLD = 78  # [CAL] PRD 6.5; quick RC below this runs the listening module
