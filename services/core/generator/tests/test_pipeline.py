"""The Writer + Critic loop: one retry, the deadline, and the passage it builds (PRD 4.5)."""

import json
import re
from datetime import UTC, datetime

import httpx
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from services.core.generator import clips, critic, gate, pipeline, writer
from services.core.generator.models import FixtureModel, ModelError
from services.core.generator.pipeline import DeadlineExceeded, GateFailed, Generator, Request

from .fakes import CONTRACTS, RECORDED, ROOT, Clock, ScriptedModel, demo, demo_responses

SCHEMA = json.loads((ROOT / "schemas" / "passage.schema.json").read_text(encoding="utf-8"))
CONTRACT_REQUEST = json.loads((CONTRACTS / "passage_generate.request.json").read_text())
CLIP_URI = clips.word_clip_uri("aloai-dev-clips", "vp_google_v1", "v1")
NOW = datetime(2026, 10, 21, 9, 30, tzinfo=UTC)
ALL_CHECKS = {
    "blueprint",
    "difficulty",
    "safety",
    "names",
    "propositions",
    "inference_is_real",
    "items_shape",
    "plain_text",
    "no_ambiguous_words",
    "items_answerable",
    "items_not_guessable",
}


@pytest.fixture
def clock():
    return Clock()


def generator(model, nlp, clock=None):
    return Generator(
        model=model,
        nlp=nlp,
        clips_bucket="aloai-dev-clips",
        tts_version="v1",
        monotonic=clock or Clock(),
        now=lambda: NOW,
    )


def request(**changes) -> Request:
    return Request.from_contract({**CONTRACT_REQUEST, **changes})


def run(model, nlp, clock=None, **changes):
    return generator(model, nlp, clock).generate(
        request(**changes), "gen_sess_demo_001", "bank_l3_rain"
    )


def blocked_story():
    story = demo("writer/1")
    story["sentences"][6] = "The teacher laughed and gave Femi a long gun."
    return story


def test_the_recorded_demo_session_gives_a_valid_passage(nlp):
    model = FixtureModel(RECORDED)
    generated = run(model, nlp)
    passage = generated.passage
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(passage)
    assert (generated.attempts, generated.estimated_arl) == (1, 3.88)
    assert passage["passage_id"] == "gen_sess_demo_001"
    assert passage["source"] == "GENERATED" and passage["mode"] == "READ"
    assert passage["paired_listening_passage_id"] == "bank_l3_rain"
    assert passage["topic_tags"] == ["animals", "adventure"]
    assert passage["genre"] == "NARRATIVE"  # adventure is a story tag
    assert passage["arl_level"] == 4 and passage["length_profile"] == "DEMO"
    assert passage["word_count"] == 72 == len(passage["tokens"])
    assert passage["generation"] == {
        "model": writer.MODEL,
        "prompt_version": "writer_v1+critic_v1",
        "target_arl": 4,
        "estimated_arl": 3.88,
        "attempts": 1,
        "gate_results": dict.fromkeys(ALL_CHECKS, True),
        "created_at": "2026-10-21T09:30:00Z",
    }
    assert [item["max_points"] for item in passage["items"]] == [2, 2]
    femi = next(t for t in passage["tokens"] if t["clean_text"] == "femi")
    assert femi["name_ipa"] == "ˈfɛmi"
    assert femi["word_clip_gcs_uri"] == CLIP_URI("femi", "ˈfɛmi")


def test_a_story_that_fails_a_code_check_is_rewritten_once_with_the_reasons(nlp):
    model = ScriptedModel({**demo_responses(attempts=2), "writer/1": blocked_story()})
    generated = run(model, nlp)
    assert generated.attempts == 2
    assert generated.passage["generation"]["attempts"] == 2
    # the Critic only runs on a story that passed the code checks
    assert model.keys()[0] == "writer/1" and model.keys()[1] == "writer/2"
    assert "- safety: uses gun" in model.prompt("writer/2")


def test_a_story_the_critic_fails_twice_fails_the_gate(nlp):
    guessable = {
        "scores": [{"answer_set": s, "item_id": i, "points": 2} for s in "AB" for i in ("q1", "q2")]
    }
    responses = demo_responses(attempts=2)
    responses["critic_c/1"] = responses["critic_c/2"] = guessable
    model = ScriptedModel(responses)
    with pytest.raises(GateFailed) as failed:
        run(model, nlp)
    assert failed.value.attempts == 2
    assert gate.results(failed.value.checks)["items_not_guessable"] is False
    assert "items_not_guessable" in model.prompt("writer/2")


def test_unusable_writer_output_counts_as_a_failed_attempt(nlp):
    model = ScriptedModel({**demo_responses(attempts=2), "writer/1": {"title": "Half"}})
    assert run(model, nlp).attempts == 2
    assert "- writer_output: writer/1 broke the output schema" in model.prompt("writer/2")


def test_an_unusable_critic_answer_counts_as_a_failed_attempt(nlp):
    responses = demo_responses(attempts=2)
    responses["critic_b/1"] = ModelError("no recorded response critic_b/1")
    model = ScriptedModel(responses)
    assert run(model, nlp).attempts == 2
    assert "- critic_output: the questions were not checked" in model.prompt("writer/2")


def test_no_retry_without_time_for_a_whole_second_attempt(nlp, clock):
    # 20 s deadline, 3 s kept for the clips: 17 s. The first attempt takes 8 s; 9 s is left.
    model = ScriptedModel(
        {**demo_responses(attempts=2), "writer/1": blocked_story()},
        clock,
        seconds={"writer": 8.0},
    )
    with pytest.raises(GateFailed) as failed:
        run(model, nlp, clock)
    assert failed.value.attempts == 1
    assert model.keys() == ["writer/1"]


def test_each_call_gets_at_most_the_time_left(nlp, clock):
    model = ScriptedModel(
        {**demo_responses(attempts=2), "writer/1": blocked_story()},
        clock,
        seconds={"writer": 6.0, "critic_a": 0.5, "critic_b": 0.5},
    )
    run(model, nlp, clock)
    timeouts = {call.key: call.timeout_s for call in model.calls}
    assert timeouts["writer/1"] == pipeline.WRITER_TIMEOUT_S  # 17 s left, capped at 12
    assert timeouts["writer/2"] == 11.0  # 17 - 6
    # the second Writer took 6 s: 5 s left, and each Critic call reads the clock as it starts
    assert timeouts["critic_a/2"] == timeouts["critic_b/2"] == pipeline.CRITIC_TIMEOUT_S
    assert timeouts["critic_c/2"] == 4.0  # A and B moved the clock on by 1 s


def test_a_call_that_would_start_after_the_deadline_is_not_made(nlp, clock):
    model = ScriptedModel(demo_responses(), clock, seconds={"writer": 17.0})
    with pytest.raises(DeadlineExceeded):
        run(model, nlp, clock)
    assert model.keys() == ["writer/1"]


def test_a_model_timeout_past_the_deadline_is_a_deadline(nlp, clock):
    class TimesOut(ScriptedModel):
        def call(self, call):
            clock.t += call.timeout_s
            raise httpx.ReadTimeout("timed out")

    with pytest.raises(DeadlineExceeded):
        run(TimesOut({}), nlp, clock, deadline_ms=10_000)


def test_vertex_failing_inside_the_deadline_is_passed_on(nlp):
    model = ScriptedModel({"writer/1": httpx.ConnectError("refused")})
    with pytest.raises(httpx.ConnectError):
        run(model, nlp)


def test_a_pre_generated_story_has_no_deadline(nlp, clock):
    model = ScriptedModel(
        {**demo_responses(attempts=2), "writer/1": blocked_story()},
        clock,
        seconds={"writer": 30.0},
    )
    generated = generator(model, nlp, clock).generate(
        Request("sess_demo_001", 4, ("animals",), "DEMO", "vp_google_v1", None),
        "gen_next_sess_demo_001",
        "bank_l3_rain",
    )
    assert generated.attempts == 2
    assert all(
        call.timeout_s in (pipeline.WRITER_TIMEOUT_S, pipeline.CRITIC_TIMEOUT_S)
        for call in model.calls
    )


def test_an_unsafe_detail_never_reaches_the_writer(nlp):
    model = ScriptedModel(demo_responses())
    run(model, nlp, details=["gun"])
    assert not re.search(r"\bgun\b", model.prompt("writer/1"))  # "Segun" is a listed name
    assert "in the story." not in model.prompt("writer/1")


def test_factual_tags_make_an_expository_text(nlp):
    model = ScriptedModel(demo_responses())
    passage = run(model, nlp, tags=["animals", "space"], genre_hint=None).passage
    assert passage["genre"] == "EXPOSITORY"
    assert "a short factual text" in model.prompt("writer/1")


def test_a_genre_hint_wins(nlp):
    passage = run(ScriptedModel(demo_responses()), nlp, genre_hint="EXPOSITORY").passage
    assert passage["genre"] == "EXPOSITORY"


def test_the_contract_request_is_read_whole():
    assert request() == Request(
        session_id="sess_demo_001",
        target_arl=4,
        tags=("animals", "adventure"),
        length_profile="DEMO",
        voice_profile_id="vp_google_v1",
        deadline_ms=20000,
        details=("goat", "football", "red car"),
        genre_hint="NARRATIVE",
    )


def test_the_default_lists_and_clock_are_the_real_ones(nlp):
    built = Generator(ScriptedModel({}), nlp, "aloai-dev-clips", "v1")
    assert "femi" in built.names and built.blocklist.hits("gun") == ["gun"]
    assert built.now().tzinfo is UTC
    assert critic.CHECK_NAMES == ("items_answerable", "items_not_guessable")


BANK = [
    {"passage_id": "bank_l3_rain", "mode": "LISTEN", "arl_level": 3, "length_profile": "DEMO"},
    {"passage_id": "bank_l5_rain", "mode": "LISTEN", "arl_level": 5, "length_profile": "DEMO"},
    {"passage_id": "bank_l4_std", "mode": "LISTEN", "arl_level": 4, "length_profile": "STANDARD"},
    {"passage_id": "bank_p4_read", "mode": "READ", "arl_level": 4, "length_profile": "DEMO"},
]


@pytest.mark.parametrize(
    ("arl", "profile", "chosen"),
    [
        (3, "DEMO", "bank_l3_rain"),
        (4, "DEMO", "bank_l3_rain"),  # a tie goes to the easier story
        (6, "DEMO", "bank_l5_rain"),
        (9, "STANDARD", "bank_l4_std"),
    ],
)
def test_the_listening_story_has_the_same_profile_and_the_nearest_level(arl, profile, chosen):
    assert pipeline.choose_listening(BANK, arl, profile) == chosen


def test_no_listening_story_for_the_profile():
    with pytest.raises(LookupError):
        pipeline.choose_listening(BANK[:2], 4, "STANDARD")


def test_every_safe_interest_reaches_the_writer_and_an_unsafe_one_is_dropped_alone(nlp):
    model = ScriptedModel(demo_responses())
    run(model, nlp, details=["goat", "gun", "ball"])
    prompt = model.prompt("writer/1")
    assert "Include goat and ball in the story." in prompt
    assert not re.search(r"\bgun\b", prompt)  # "Segun" is a listed name


def test_the_older_single_detail_is_still_accepted():
    body = {key: value for key, value in CONTRACT_REQUEST.items() if key != "details"}
    assert Request.from_contract({**body, "detail": "goat"}).details == ("goat",)
    both = Request.from_contract({**body, "details": ["ball"], "detail": "goat"})
    assert both.details == ("ball", "goat")
    assert Request.from_contract({**body, "details": ["goat"], "detail": "goat"}).details == (
        "goat",
    )
