"""The pure parts the worker is built from: turns, mic levels, intents, clips,
the grade:quick client and the passage bank."""

import json
import math
from array import array
from pathlib import Path

import pytest
from services.session_agent.clips.catalog import PROMPTS, ClipCatalog
from services.session_agent.clips.store import ClipStore, MemoryBucket
from services.session_agent.intents import intent
from services.session_agent.machine.profiles import DEMO, STANDARD
from services.session_agent.machine.types import ChildStop, MicResult, RepeatRequest
from services.session_agent.mic_check import MicMeter, block_dbfs
from services.session_agent.passages import DEFAULT_BANK, PassageBank, PassageError, folder_bank
from services.session_agent.quick_grade import FixtureQuickGrader, decision, request_body
from services.session_agent.turns import TurnTaker

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "fixtures" / "contracts"


# ---- turns


def run_ticks(taker, start, end, step=100):
    results = []
    for now in range(start, end + 1, step):
        result = taker.tick(now)
        if result:
            results.append((now, result))
    return results


def test_an_answer_ends_after_its_pause_and_the_turn_closes():
    t = TurnTaker()
    t.start("answer", 0)
    t.speech_started(1_000)
    assert t.tick(5_000) is None  # still speaking
    t.speech_ended(5_000)
    assert run_ticks(t, 5_000, 9_000) == [(6_500, "ANSWERED")]
    assert not t.active


def test_a_retell_waits_four_seconds_of_silence():
    t = TurnTaker()
    t.start("retell", 0)
    t.speech_started(100)
    t.speech_ended(2_000)
    assert run_ticks(t, 2_000, 7_000) == [(6_000, "ANSWERED")]


def test_no_speech_reports_silence_every_eight_seconds():
    t = TurnTaker()
    t.start("answer", 0)
    assert run_ticks(t, 0, 17_000) == [(8_000, "SILENCE"), (16_000, "SILENCE")]


def test_the_wait_restarts_when_the_prompt_finishes_but_not_after_speech():
    t = TurnTaker()
    t.start("answer", 0)
    t.prompt_finished(3_000)
    assert run_ticks(t, 0, 11_000) == [(11_000, "SILENCE")]
    t.speech_started(11_500)
    t.prompt_finished(12_000)  # a late ack changes nothing once the child spoke
    t.speech_ended(12_000)
    assert t.tick(13_500) == "ANSWERED"


def test_a_stopped_turn_reports_nothing():
    t = TurnTaker()
    assert t.tick(60_000) is None
    t.start("mic", 0)
    t.stop()
    assert t.tick(60_000) is None


# ---- mic levels


def pcm(values):
    return array("h", values).tobytes()


def sine(peak, n=16_000):
    return pcm(int(peak * math.sin(i / 8)) for i in range(n))


def test_block_level_of_silence_is_minus_infinity():
    assert block_dbfs(array("h")) == -math.inf
    assert block_dbfs(array("h", [0] * 10)) == -math.inf


@pytest.mark.parametrize(
    ("audio", "expected"),
    [
        (sine(3_000), MicResult(ok=True)),  # about -24 dBFS
        (sine(200), MicResult(ok=False, problem="quiet")),  # about -47 dBFS
        (pcm([0] * 16_000), MicResult(ok=False, problem="quiet")),  # nothing at all
        (pcm([32_767] * 100 + [0] * 15_900), MicResult(ok=False, problem="loud")),
    ],
)
def test_mic_levels(audio, expected):
    meter = MicMeter()
    meter.feed(audio)
    assert meter.result() == expected


def test_a_reset_forgets_the_first_try():
    meter = MicMeter()
    meter.feed(sine(200))
    meter.reset()
    meter.feed(sine(3_000))
    assert meter.result().ok


# ---- intents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Stop!", ChildStop()),
        ("I want to stop, Auntie", ChildStop()),
        ("I'm done", ChildStop()),
        ("Say it again please", RepeatRequest()),
        ("what?", RepeatRequest()),
        ("the bus had to stop at the market", None),  # an answer, not a request
        ("blue", None),
        ("", None),
    ],
)
def test_intents(text, expected):
    assert intent(text) == expected


# ---- clips


@pytest.fixture
def catalog():
    store = ClipStore(MemoryBucket(), "aloai-dev-clips", "vp_google_v1", "v1")
    return ClipCatalog(store, "https://storage.googleapis.com/aloai-dev-clips/")


def test_clip_ids_map_to_clip_store_objects(catalog):
    ids = {"passage_id": "p1", "listening_passage_id": "l1"}
    assert catalog.object_name("retell_prompt") == "vp_google_v1/v1/retell_prompt.mp3"
    assert catalog.object_name("question:2", **ids) == "vp_google_v1/v1/passages/p1/question_2.mp3"
    assert (
        catalog.object_name("listening_item:0", **ids) == "vp_google_v1/v1/passages/l1/item_0.mp3"
    )
    assert catalog.object_name("listening_story", **ids) == "vp_google_v1/v1/passages/l1/story.mp3"
    assert catalog.object_name("word_market") == "vp_google_v1/v1/words/market.mp3"
    assert catalog.url("close_praise") == (
        "https://storage.googleapis.com/aloai-dev-clips/vp_google_v1/v1/close_praise.mp3"
    )


@pytest.mark.parametrize("clip_id", ["question:1", "listening_story", "nonsense", "question:x"])
def test_unknown_or_passageless_clips_are_refused(catalog, clip_id):
    with pytest.raises(ValueError, match="no clip store object"):
        catalog.object_name(clip_id)


def test_session_clips_are_unique_and_include_names_with_their_ipa(catalog):
    read = json.loads((CONTRACTS / "passage.bank_p3_market_day.json").read_text())
    listening = json.loads((CONTRACTS / "passage.bank_l3_rain.json").read_text())
    clips = catalog.session_clips(read, listening, 2, 1)
    ids = [clip_id for clip_id, _ in clips]
    assert len(ids) == len(set(ids))
    assert set(PROMPTS) <= set(ids)
    assert {"question:0", "question:1", "listening_story", "listening_item:0"} <= set(ids)
    assert "word_ada~%CB%88%C9%91%CB%90d%C9%91" in ids  # a name, with its pronunciation
    alone = {clip_id for clip_id, _ in catalog.session_clips(read, None, 2, 1)}
    assert "listening_story" not in alone and "listening_item:0" not in alone


# ---- grade:quick client


def test_request_body_matches_the_contract(validate):
    body = request_body("sess_demo_001", "bank_p3_market_day", "QUESTION", 1, "")
    assert body["schema_version"] == 1 and body["transcript"] == ""
    if (ROOT / "schemas" / "grade_quick_request.schema.json").exists():
        validate("grade_quick_request.schema.json", body)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"schema_version": 1, "complete": True, "run_listening_module": True}, True),
        ({"schema_version": 1, "complete": True, "run_listening_module": False}, False),
        ({"schema_version": 1, "complete": False, "run_listening_module": None}, None),
        ({"schema_version": 1, "complete": True, "run_listening_module": None}, None),
        ({"error": {"code": "X", "message": "", "retryable": False}}, None),
    ],
)
def test_only_a_complete_decision_counts(response, expected):
    assert decision(response) is expected


def test_the_fixture_grader_completes_after_the_retell_and_every_item(tmp_path):
    (tmp_path / "p1.json").write_text('{"run_listening_module": true}')
    grader = FixtureQuickGrader(items=2, fixtures_dir=tmp_path)
    bodies = [
        request_body("s", "p1", phase, i, "") for phase, i in [("QUESTION", 0), ("RETELL", 0)]
    ]
    assert [grader.answer(b)["complete"] for b in bodies] == [False, False]
    last = grader.answer(request_body("s", "p1", "QUESTION", 1, ""))
    assert last == {"schema_version": 1, "complete": True, "run_listening_module": True}
    other = FixtureQuickGrader(items=0, fixtures_dir=tmp_path)
    assert other.answer(request_body("s", "p2", "RETELL", 0, ""))["run_listening_module"] is False


# ---- passages


def test_the_bank_loads_a_reading_passage_with_its_listening_passage():
    pair = folder_bank(CONTRACTS).pair("bank_p3_market_day", DEMO)
    assert pair.read["mode"] == "READ" and pair.listening["passage_id"] == "bank_l3_rain"


def test_the_bank_refuses_unknown_and_listening_passages():
    bank = folder_bank(CONTRACTS)
    with pytest.raises(PassageError, match="no passage"):
        bank.pair("nope", DEMO)
    with pytest.raises(PassageError, match="not READ"):
        bank.pair("bank_l3_rain", DEMO)
    lonely = {"passage_id": "p", "mode": "READ", "length_profile": "DEMO", "items": [{}, {}]}
    assert PassageBank({"p": lonely}.get).pair("p", DEMO).listening is None


@pytest.mark.parametrize("profile", [STANDARD, DEMO])
def test_each_profile_has_a_default_bank_pair_that_fits_it(profile):
    pair = folder_bank(CONTRACTS).pair(DEFAULT_BANK[profile.name], profile)
    assert len(pair.read["items"]) == profile.n_questions
    assert len(pair.listening["items"]) == profile.n_listening_items


def test_the_standard_bank_pair_is_a_whole_story_at_its_level():
    pair = folder_bank(CONTRACTS).pair("bank_p3_school_garden", STANDARD)
    read, listening = pair.read, pair.listening
    # PRD 4.5 blueprint for ARL 5-6: 120-150 words; a standard listening story is
    # about 80-120 words (PRD 4.1). Checked with the generator's code gate when written.
    assert read["arl_level"] == listening["arl_level"] == 5
    assert 120 <= read["word_count"] <= 150 and 80 <= listening["word_count"] <= 120
    assert [i["type"] for i in read["items"]] == ["LITERAL", "LITERAL", "INFERENTIAL"]
    assert [i["type"] for i in listening["items"]] == ["LITERAL", "INFERENTIAL"]
    for passage in (read, listening):
        assert " ".join(t["text"] for t in passage["tokens"]) == passage["text_content"]


def test_the_bank_refuses_passages_that_do_not_fit_the_session_profile():
    # The demo bank pair asks 2 questions and 1 listening item; a standard session asks
    # 3 and 2, so the Grader would never see the items it expects (PRD 4.5).
    with pytest.raises(PassageError, match="is a DEMO passage; this session is standard"):
        folder_bank(CONTRACTS).pair("bank_p3_market_day", STANDARD)


@pytest.mark.parametrize(
    ("read_items", "listen_items", "message"),
    [
        (1, 1, "p has 1 items; a demo session asks 2"),
        (2, 2, "l has 2 items; a demo session asks 1"),
    ],
)
def test_the_bank_refuses_a_pair_with_the_wrong_item_counts(read_items, listen_items, message):
    docs = {
        "p": {
            "passage_id": "p",
            "mode": "READ",
            "length_profile": "DEMO",
            "items": [{}] * read_items,
            "paired_listening_passage_id": "l",
        },
        "l": {
            "passage_id": "l",
            "mode": "LISTEN",
            "length_profile": "DEMO",
            "items": [{}] * listen_items,
        },
    }
    with pytest.raises(PassageError, match=message):
        PassageBank(docs.get).pair("p", DEMO)
