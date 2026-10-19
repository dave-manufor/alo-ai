"""Final grading (PRD 7.2): transcripts, two Pro passes, a third when they disagree."""

from pathlib import Path

import pytest
from aloai_events import MemoryPublisher
from services.core.grader import paths
from services.core.grader.asr import FixtureTranscriber
from services.core.grader.final import FinalGrader, TurnMismatch, reading_stopped_early
from services.core.tests.support import (
    PASSAGE_ID,
    RECORDED,
    SESSION_ID,
    RecordedModel,
    ScriptedModel,
    assembler,
    contract,
    grader_output,
    seeded_store,
    session_done,
    turn,
)

LISTEN_ID = "bank_l3_rain"
FULL_RETELL = (
    "ada and her [?mama?] went to the market and she saw a red hat "
    "it was too much money so she took the blue one"
)


class Transcripts:
    """Words for each recorded turn, by turn number; the other turns are silent."""

    def __init__(self, spoken: dict[int, str] | None = None) -> None:
        self._spoken = spoken or {}

    def words(self, audio_uri: str) -> list[tuple[str, float]]:
        number = int(Path(audio_uri).stem.rsplit("-", 1)[1])
        return [(word, 0.95) for word in self._spoken.get(number, "").split()]


def final_grader(store, model, transcriber=None) -> FinalGrader:
    return FinalGrader(
        store,
        model,
        transcriber or FixtureTranscriber(RECORDED / "asr"),
        assembler(store, MemoryPublisher()),
    )


def same_passes(output: dict, passage_id: str = PASSAGE_ID) -> ScriptedModel:
    return ScriptedModel({f"{passage_id}/pass1": output, f"{passage_id}/pass2": output})


def add_listening_passage(store) -> None:
    listen = contract("passage.bank_p3_market_day.json") | {
        "passage_id": LISTEN_ID,
        "mode": "LISTEN",
    }
    for number, item in enumerate(listen["items"], start=1):
        item["item_id"] = f"{LISTEN_ID}_q{number}"
    store.set(paths.passage(LISTEN_ID), listen)
    store.merge(paths.passage(PASSAGE_ID), {"paired_listening_passage_id": LISTEN_ID})


def test_two_passes_that_agree_are_combined_without_a_third():
    store, model = seeded_store(), RecordedModel()
    final_grader(store, model).handle(session_done())
    assert sorted(model.keys) == [f"{PASSAGE_ID}/pass1", f"{PASSAGE_ID}/pass2"]
    grading = store.get(paths.grading(SESSION_ID))
    assert grading["read"] == {
        "passage_id": PASSAGE_ID,
        "total_weight": 6,
        "weighted_credit": 5.5,
        "item_points": [2, 0],
        "disagreement": False,
    }
    assert grading["listen"] is None
    assert (grading["reading_stopped_early"], grading["session_flags"]) == (False, ["DEMO_PROFILE"])


def test_the_grader_hears_the_whole_retell_with_unsure_words_marked():
    store = seeded_store()
    model = same_passes(
        grader_output({"p1": 1, "p2": 1, "p3": 1, "p4": 1}, {f"{PASSAGE_ID}_q1": 2})
    )
    final_grader(store, model).handle(session_done())
    task = model.tasks[0]
    assert task.retell == FULL_RETELL
    assert dict(task.answers) == {f"{PASSAGE_ID}_q1": "it was red"}
    assert (task.model, task.primary_class) == ("gemini-2.5-pro", 2)
    assert store.get(paths.turn(SESSION_ID, "turn_013")) == {"asr_transcript": "it was red"}


def test_passes_that_disagree_get_a_third_and_are_flagged():
    store = seeded_store()
    q1 = f"{PASSAGE_ID}_q1"
    model = ScriptedModel(
        {
            f"{PASSAGE_ID}/pass1": grader_output({"p1": 1, "p2": 1, "p3": 1, "p4": 1}, {q1: 2}),
            f"{PASSAGE_ID}/pass2": grader_output({"p1": 0, "p2": 0, "p3": 0, "p4": 0}, {q1: 0}),
            f"{PASSAGE_ID}/pass3": grader_output({"p1": 1, "p2": 1, "p3": 0.5, "p4": 0}, {q1: 1}),
        }
    )
    final_grader(store, model).handle(session_done())
    read = store.get(paths.grading(SESSION_ID))["read"]
    assert (read["weighted_credit"], read["item_points"], read["disagreement"]) == (
        3.0,
        [1, 0],
        True,
    )
    assert len(model.tasks) == 3


def test_nothing_said_needs_no_model_call():
    store, model = seeded_store(), ScriptedModel({})
    final_grader(store, model, Transcripts()).handle(session_done())
    read = store.get(paths.grading(SESSION_ID))["read"]
    assert (read["weighted_credit"], read["item_points"], read["disagreement"]) == (
        0,
        [0, 0],
        False,
    )
    assert model.tasks == []


def test_a_reading_stopped_early_grades_only_the_listening_passage():
    store = seeded_store()
    add_listening_passage(store)
    turns = [
        turn(1, "READING"),
        turn(15, "LISTENING_RETELL"),
        turn(16, "LISTENING_QUESTION"),
        turn(17, "LISTENING_QUESTION"),
    ]
    spoken = Transcripts({15: "ada and mama went to the market", 16: "a red one"})
    model = same_passes(
        grader_output({"p1": 1, "p2": 0, "p3": 0, "p4": 0}, {f"{LISTEN_ID}_q1": 2}, LISTEN_ID),
        LISTEN_ID,
    )
    final_grader(store, model, spoken).handle(session_done(turn_audio_uris=turns))
    grading = store.get(paths.grading(SESSION_ID))
    assert grading["reading_stopped_early"] is True
    assert grading["read"] is None
    assert grading["listen"]["weighted_credit"] == 1.0
    assert grading["listen"]["item_points"] == [2, 0]


def test_the_listening_passage_is_graded_beside_the_read_one():
    store = seeded_store()
    add_listening_passage(store)
    turns = session_done()["turn_audio_uris"] + [turn(17, "LISTENING_QUESTION")]
    spoken = Transcripts({11: "ada went to the market", 13: "red", 15: "ada saw a hat", 16: "red"})
    read = grader_output({"p1": 1, "p2": 0, "p3": 0, "p4": 0}, {f"{PASSAGE_ID}_q1": 2})
    listen = grader_output({"p1": 1, "p2": 1, "p3": 1, "p4": 1}, {f"{LISTEN_ID}_q1": 2}, LISTEN_ID)
    model = ScriptedModel(
        {
            f"{PASSAGE_ID}/pass1": read,
            f"{PASSAGE_ID}/pass2": read,
            f"{LISTEN_ID}/pass1": listen,
            f"{LISTEN_ID}/pass2": listen,
        }
    )
    final_grader(store, model, spoken).handle(session_done(turn_audio_uris=turns))
    grading = store.get(paths.grading(SESSION_ID))
    assert (grading["read"]["weighted_credit"], grading["listen"]["weighted_credit"]) == (1.0, 6.0)
    assert grading["listen"]["item_points"] == [2, 0]


def test_answer_turns_that_cannot_be_matched_to_items_are_refused():
    store = seeded_store()
    turns = session_done()["turn_audio_uris"] + [turn(18, "QUESTION")]
    with pytest.raises(TurnMismatch):
        final_grader(store, RecordedModel()).handle(session_done(turn_audio_uris=turns))
    assert store.get(paths.grading(SESSION_ID)) is None


def test_a_session_without_its_record_cannot_be_graded():
    store = seeded_store()
    del store.docs[paths.session(SESSION_ID)]
    with pytest.raises(LookupError):
        final_grader(store, RecordedModel()).handle(session_done())


def test_a_redelivered_session_done_is_not_graded_again():
    store, model = seeded_store(), RecordedModel()
    grader = final_grader(store, model)
    grader.handle(session_done())
    grader.handle(session_done())
    assert len(model.keys) == 2


@pytest.mark.parametrize(
    "phases, listening, stopped",
    [
        (["READING", "LISTENING_RETELL"], True, True),
        (["READING", "RETELL", "QUESTION", "LISTENING_RETELL"], True, False),
        (["READING", "RETELL", "QUESTION"], False, False),
    ],
)
def test_a_kindness_stop_is_a_listening_module_without_a_retell(phases, listening, stopped):
    turns = [turn(number, phase) for number, phase in enumerate(phases, start=1)]
    assert reading_stopped_early(turns, listening) is stopped
