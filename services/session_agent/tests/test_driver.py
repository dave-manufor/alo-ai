"""The driver runs whole sessions through fake ports: no LiveKit, no cloud, no clock."""

import math
import uuid
from array import array
from datetime import UTC, datetime
from pathlib import Path

import pytest
from services.session_agent import session_store
from services.session_agent.clips.catalog import ClipCatalog
from services.session_agent.clips.store import ClipStore, MemoryBucket
from services.session_agent.driver import Driver, Ports
from services.session_agent.events import MemoryPublisher, SessionContext
from services.session_agent.machine.profiles import DEMO
from services.session_agent.machine.types import Phase, Timer
from services.session_agent.passages import folder_bank
from services.session_agent.quick_grade import FixtureQuickGrader
from services.session_agent.recording import AudioLog

ROOT = Path(__file__).resolve().parents[3]
BANK = folder_bank(ROOT / "fixtures" / "contracts")
PAIR = BANK.pair("bank_p3_market_day", DEMO)
SESSION_UUID = "3f2b9c1e-7d44-4c0b-8a52-0e6f1d9a7b10"
CTX = SessionContext("sess_demo_001", "child_demo_001", "SCHOOL", "vp_google_v1", "LIVE")


def tone(dbfs: float, ms: int) -> bytes:
    """A 16 kHz sine at the given level, as 16-bit PCM."""
    amplitude = 32_767 * 10 ** (dbfs / 20) * math.sqrt(2)
    n = 16 * ms
    return array("h", (int(amplitude * math.sin(i / 8)) for i in range(n))).tobytes()


class Channel:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)

    def plays(self):
        return [m["clip_id"] for m in self.sent if m["cmd"] == "play"]


class Recorder:
    def __init__(self):
        self.turns, self.bytes, self.stops = [], 0, 0

    def start(self, turn):
        self.turns.append(turn)

    def feed(self, pcm):
        self.bytes += len(pcm)

    def stop(self):
        self.stops += 1


class Timers:
    def __init__(self):
        self.started = []

    def start(self, name, ms):
        self.started.append((name, ms))

    def last(self, kind):
        return next(n for n, _ in reversed(self.started) if n.split(":")[0] == kind)


class Grader:
    def __init__(self):
        self.bodies = []

    def request(self, body):
        self.bodies.append(body)


class Passages:
    def __init__(self):
        self.calls = []

    def generate(self, interest, deadline_ms):
        self.calls.append(("generate", interest, deadline_ms))

    def bank(self):
        self.calls.append(("bank",))


class Clock:
    def __init__(self):
        self.ms = 0

    def __call__(self):
        return self.ms


def make_driver(profile="demo"):
    clock = Clock()
    ports = Ports(
        Channel(),
        Recorder(),
        Timers(),
        Grader(),
        Passages(),
        MemoryPublisher(),
        session_store.MemoryDocuments(),
    )
    store = ClipStore(MemoryBucket(), "aloai-dev-clips", "vp_google_v1", "v1")
    ended = []
    count = iter(range(1, 1000))
    driver = Driver(
        ctx=CTX,
        child_id="child_demo_001",
        profile=profile,
        voice_mode="cache_first",
        audio=AudioLog(
            "aloai-dev-audio",
            SESSION_UUID,
            lambda: uuid.UUID(f"a1b2c3d4-0000-4000-8000-{next(count):012d}"),
        ),
        catalog=ClipCatalog(store, "https://storage.googleapis.com/aloai-dev-clips"),
        ports=ports,
        clock_ms=clock,
        wall=lambda: datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
        on_end=ended.append,
    )
    return driver, ports, clock, ended


def speak(driver, clock, text, *, then_quiet_ms):
    """The child says `text` (one VAD speech segment), then stays quiet."""
    driver.on_speech_started()
    clock.ms += 1_000
    driver.on_transcript(text, final=True)
    driver.on_speech_ended()
    wait(driver, clock, then_quiet_ms)


def wait(driver, clock, ms, step=250):
    for _ in range(ms // step):
        clock.ms += step
        driver.tick()


def fire(driver, timers, kind):
    driver.handle(Timer(timers.last(kind)))


def to_reading(driver, ports, clock):
    driver.start()
    speak(driver, clock, "i like football", then_quiet_ms=1_500)
    assert ports.passages.calls == [("generate", "i like football", 20_000)]
    driver.passage_arrived(PAIR, fallback=False)
    driver.on_audio(tone(-20, 2_000))
    speak(driver, clock, "one two three four five", then_quiet_ms=1_000)
    assert driver.state.phase is Phase.READING


def read_passage(driver, clock):
    driver.on_transcript(PAIR.read["text_content"], final=False)
    clock.ms += 250
    driver.tick()


# ---- the clip lists


def test_the_session_clip_list_is_sent_after_the_prompts_words_first_and_small():
    from services.session_agent import protocol

    driver, ports, clock, _ = make_driver()
    driver.start(returning=PAIR)
    lists = [m for m in ports.channel.sent if m["cmd"] == "clip_list"]
    assert len(lists) >= 2  # the prompts, then the session's clips (cut up if they are many)
    assert all(len(protocol.encode(m)) <= protocol.CLIP_LIST_MAX_BYTES for m in lists)
    assert lists[0]["clips"][0]["clip_id"] == "interest_prompt"
    assert lists[1]["clips"][0]["clip_id"].startswith("word_")


# ---- a whole session


def run_demo_session(driver, ports, clock):
    """A whole demo-profile session in which the listening module runs."""
    to_reading(driver, ports, clock)
    read_passage(driver, clock)
    fire(driver, ports.timers, "transition")
    speak(driver, clock, "ada went to the market and saw a red hat", then_quiet_ms=4_000)
    speak(driver, clock, "she got a blue one", then_quiet_ms=4_000)
    speak(driver, clock, "it was red", then_quiet_ms=1_500)
    wait(driver, clock, 16_000)
    grader = FixtureQuickGrader(items=2, default=True)
    for body in ports.grader.bodies:
        driver.on_quick_response(grader.answer(body))
    fire(driver, ports.timers, "listening_story")
    speak(driver, clock, "it rained and tunde got the goats", then_quiet_ms=4_000)
    speak(driver, clock, "because of the rain", then_quiet_ms=1_500)
    fire(driver, ports.timers, "close")


def test_the_web_app_can_follow_a_whole_session_from_the_protocol_alone(validate):
    driver, ports, clock, ended = make_driver()
    run_demo_session(driver, ports, clock)
    assert ended == ["COMPLETE"]
    sent = ports.channel.sent
    for message in sent:
        validate("session_protocol.schema.json", message)

    steps = [m["step"] for m in sent if m["cmd"] == "step"]
    assert steps == [
        "INTEREST_CHAT",
        "MIC_CHECK",
        "READING",
        "RETELL",
        "QUESTIONS",
        "LISTENING",
        "CLOSE",
        "ENDED",
    ]
    reading = next(i for i, m in enumerate(sent) if m.get("step") == "READING")
    shown = sent[reading + 1]
    assert shown["cmd"] == "show_passage" and shown["passage_id"] == "bank_p3_market_day"
    assert " ".join(shown["sentences"]) == PAIR.read["text_content"]

    texts = {c["clip_id"]: c["text"] for m in sent if m["cmd"] == "clip_list" for c in m["clips"]}
    played = ports.channel.plays()
    assert "listening_story" in played and texts["listening_story"] is None
    assert all(texts[clip_id] for clip_id in played if clip_id != "listening_story")


def test_a_reconnect_tells_the_web_app_which_step_it_is_back_in():
    driver, ports, _clock, _ = make_driver()
    driver.start()
    driver.on_disconnected()
    driver.on_reconnected()
    after = ports.channel.sent[
        ports.channel.sent.index({"schema_version": 3, "cmd": "reconnecting"}) :
    ]
    assert {"schema_version": 3, "cmd": "step", "step": "INTEREST_CHAT"} in after


def test_a_demo_session_runs_end_to_end_and_publishes_valid_events(validate):
    driver, ports, clock, ended = make_driver()
    to_reading(driver, ports, clock)
    read_passage(driver, clock)
    assert driver.state.phase is Phase.TRANSITION
    fire(driver, ports.timers, "transition")

    speak(driver, clock, "ada went to the market and saw a red hat", then_quiet_ms=4_000)
    speak(driver, clock, "she got a blue one", then_quiet_ms=4_000)
    assert driver.state.phase is Phase.QUESTIONS
    speak(driver, clock, "it was red", then_quiet_ms=1_500)
    wait(driver, clock, 16_000)  # two 8 s silences on the second question

    assert [(b["turn_phase"], b["index"], b["transcript"]) for b in ports.grader.bodies] == [
        ("RETELL", 0, "ada went to the market and saw a red hat she got a blue one"),
        ("QUESTION", 0, "it was red"),
        ("QUESTION", 1, ""),
    ]
    grader = FixtureQuickGrader(items=2, default=True)
    for body in ports.grader.bodies:
        driver.on_quick_response(grader.answer(body))
    assert driver.state.phase is Phase.LISTENING

    fire(driver, ports.timers, "listening_story")
    speak(driver, clock, "it rained and tunde got the goats", then_quiet_ms=4_000)
    speak(driver, clock, "because of the rain", then_quiet_ms=1_500)
    fire(driver, ports.timers, "close")

    assert ended == ["COMPLETE"]
    events = ports.publisher.events
    assert [e["type"] for e in events] == ["session.started", "phase1.recorded", "session.done"]
    for event in events:
        validate("event_envelope.schema.json", event)
    done = events[-1]["data"]
    assert done["listening_passage_id"] == "bank_l3_rain" and done["reading_stopped_early"] is False
    phases = [(t["phase"], t["index"], t["part"]) for t in done["turn_audio_uris"]]
    assert phases[3:] == [
        ("RETELL", 0, 0),
        ("RETELL", 0, 1),
        ("QUESTION", 0, 0),
        ("QUESTION", 1, 0),
        ("LISTENING_RETELL", 0, 0),
        ("LISTENING_QUESTION", 0, 0),
    ]
    for path, doc in ports.documents.docs.items():
        validate("session_record.schema.json", doc)
    record = ports.documents.docs["sessions/sess_demo_001"]
    assert record["status"] == "COMPLETE" and record["flags"] == ["DEMO_PROFILE"]
    assert ports.recorder.stops == len(ports.recorder.turns) == len(done["turn_audio_uris"])


def test_the_clip_lists_cover_every_clip_the_session_plays(validate):
    driver, ports, clock, _ = make_driver()
    to_reading(driver, ports, clock)
    lists = [m for m in ports.channel.sent if m["cmd"] == "clip_list"]
    cached = {c["clip_id"] for m in lists for c in m["clips"]}
    for message in ports.channel.sent:
        validate("session_protocol.schema.json", message)
    assert set(ports.channel.plays()) <= cached
    assert "word_market" in cached and "question:1" in cached and "listening_story" in cached


# ---- reading


def test_a_stall_plays_the_word_clip_and_a_quick_finish_moves_on():
    driver, ports, clock, _ = make_driver()
    to_reading(driver, ports, clock)
    driver.on_transcript("ada and", final=False)
    wait(driver, clock, 5_000)
    assert ports.channel.plays()[-1] == "word_mama"
    assert driver.state.told == (2,)
    read_passage(driver, clock)
    assert driver.state.phase is Phase.TRANSITION


def test_the_kindness_rule_ends_a_hard_reading_and_goes_to_listening():
    driver, ports, clock, _ = make_driver()
    to_reading(driver, ports, clock)
    driver.on_transcript("ada and mama", final=False)
    wait(driver, clock, 30_000)
    assert driver.state.phase is Phase.LISTENING and driver.state.reading_stopped_early


# ---- turns, mic and intents


def test_a_quiet_mic_check_gets_one_retry_then_low_audio():
    driver, ports, clock, _ = make_driver()
    driver.start()
    speak(driver, clock, "football", then_quiet_ms=1_500)
    driver.passage_arrived(PAIR, fallback=False)
    driver.on_audio(tone(-55, 2_000))
    speak(driver, clock, "one two three", then_quiet_ms=1_000)
    assert ports.channel.plays()[-1] == "mic_closer"
    wait(driver, clock, 8_000)  # nothing at all on the retry
    assert "LOW_AUDIO" in driver.state.flags and driver.state.phase is Phase.READING


def test_a_loud_mic_check_asks_for_softer():
    driver, ports, clock, _ = make_driver()
    driver.start()
    speak(driver, clock, "football", then_quiet_ms=1_500)
    driver.passage_arrived(PAIR, fallback=False)
    driver.on_audio(array("h", [32_767] * 16_000).tobytes())
    speak(driver, clock, "one two three", then_quiet_ms=1_000)
    assert ports.channel.plays()[-1] == "mic_softer"


def test_saying_stop_ends_the_session_incomplete():
    driver, ports, clock, ended = make_driver()
    driver.start()
    driver.on_transcript("I want to stop", final=True)
    assert ended == ["INCOMPLETE"] and ports.channel.plays()[-1] == "stop_praise"
    assert "sessions/sess_demo_001" not in ports.documents.docs  # no passage, no record


def test_say_it_again_repeats_a_question_once():
    driver, ports, clock, _ = make_driver()
    to_reading(driver, ports, clock)
    read_passage(driver, clock)
    fire(driver, ports.timers, "transition")
    speak(driver, clock, "a red hat", then_quiet_ms=4_000)
    wait(driver, clock, 16_000)  # no follow-up
    driver.on_transcript("say it again", final=True)
    assert ports.channel.plays()[-1] == "question:0"
    assert [t.part for t in ports.recorder.turns if t.phase == "QUESTION"] == [0, 1]


def test_the_wait_for_an_answer_starts_when_the_prompt_has_played():
    driver, ports, clock, _ = make_driver()
    driver.start()
    wait(driver, clock, 6_000)
    driver.on_client_message(b'{"schema_version":1,"cmd":"played","clip_id":"interest_prompt"}')
    wait(driver, clock, 6_000)
    assert driver.state.silences == 0
    wait(driver, clock, 2_000)
    assert driver.state.silences == 1


def test_a_missing_clip_is_sent_again_from_the_store():
    driver, ports, clock, _ = make_driver()
    driver.start()
    driver.on_client_message(b'{"schema_version":1,"cmd":"missing","clip_id":"interest_prompt"}')
    assert ports.channel.sent[-2]["cmd"] == "clip_list"
    assert ports.channel.sent[-2]["clips"] == [
        {
            "clip_id": "interest_prompt",
            "url": "https://storage.googleapis.com/aloai-dev-clips/vp_google_v1/v1/interest_prompt.mp3",
            "text": "Before we read, tell me: what kind of stories do you like?",
        }
    ]
    assert ports.channel.sent[-1] == {
        "schema_version": 3,
        "cmd": "play",
        "clip_id": "interest_prompt",
    }
    driver.on_client_message(b"not json")  # ignored


def test_the_web_app_is_told_when_the_child_starts_and_stops_speaking():
    driver, ports, clock, _ = make_driver()
    driver.start()
    ports.channel.sent.clear()
    driver.on_speech_started()
    clock.ms += 500
    driver.on_speech_ended()
    signals = [m for m in ports.channel.sent if m["cmd"] == "child_speaking"]
    assert [m["speaking"] for m in signals] == [True, False]
    assert all(set(m) == {"schema_version", "cmd", "speaking"} for m in signals)


def test_an_answer_heard_only_as_an_interim_transcript_is_still_scored():
    driver, ports, clock, _ = make_driver()
    to_reading(driver, ports, clock)
    read_passage(driver, clock)
    fire(driver, ports.timers, "transition")
    driver.on_speech_started()
    driver.on_transcript("a red", final=False)
    driver.on_transcript("a red hat", final=False)  # no final before the turn ends
    driver.on_speech_ended()
    wait(driver, clock, 4_000)
    wait(driver, clock, 16_000)
    assert ports.grader.bodies[0]["transcript"] == "a red hat"


# ---- passages, grader, connection


def test_only_the_interest_chat_answer_goes_to_the_story_request():
    driver, ports, clock, _ = make_driver()
    driver.start()
    speak(driver, clock, "i like goats and space", then_quiet_ms=1_500)
    ((_, interest, deadline_ms),) = ports.passages.calls
    assert (interest, deadline_ms) == ("i like goats and space", 20_000)


def test_a_child_who_says_nothing_still_gets_a_story_with_no_interest():
    driver, ports, clock, _ = make_driver()
    driver.start()
    for _ in range(4):
        wait(driver, clock, 8_000)
        if ports.passages.calls:
            break
    assert ports.passages.calls == [("generate", None, 20_000)]


def test_a_bank_fallback_flags_the_session_and_a_late_story_is_ignored():
    driver, ports, clock, _ = make_driver()
    driver.start()
    speak(driver, clock, "football", then_quiet_ms=1_500)
    fire(driver, ports.timers, "passage_wait")
    assert ports.passages.calls[-1] == ("bank",)
    driver.passage_arrived(PAIR, fallback=True)
    driver.passage_arrived(BANK.pair("bank_p3_market_day", DEMO), fallback=False)
    assert "FALLBACK_PASSAGE" in driver.state.flags


def test_a_returning_child_starts_at_the_mic_check_with_the_passage():
    driver, ports, clock, _ = make_driver()
    driver.start(returning=PAIR)
    assert driver.state.phase is Phase.MIC_CHECK
    assert driver.state.listening_passage_id == "bank_l3_rain"


@pytest.mark.parametrize(
    "response",
    [
        {"schema_version": 1, "complete": False, "run_listening_module": None},
        {"error": {"code": "INTERNAL", "message": "x", "retryable": True}},
    ],
)
def test_incomplete_or_failed_quick_responses_do_not_reach_the_machine(response):
    driver, ports, clock, _ = make_driver()
    driver.start()
    before = driver.state
    driver.on_quick_response(response)
    assert driver.state == before


def test_a_dropped_connection_stops_the_turn_and_resumes_it():
    driver, ports, clock, _ = make_driver()
    driver.start()
    driver.on_disconnected()
    assert ports.channel.sent[-1]["cmd"] in ("play", "reconnecting")
    driver.on_reconnected()
    assert "RECONNECTED" in driver.state.flags
    assert ports.recorder.turns[-1].phase == "INTEREST_CHAT" and ports.recorder.turns[-1].part == 1
