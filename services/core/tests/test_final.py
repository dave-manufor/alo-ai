"""Final grading (PRD 7.2): transcripts, two Pro passes, a third when they disagree."""

import json
from pathlib import Path

import pytest
from aloai_events import MemoryPublisher
from services.core.grader import paths
from services.core.grader.asr import FixtureTranscriber
from services.core.grader.final import FinalGrader, TurnMismatch
from services.core.tests.support import (
    LISTEN_ID,
    PASSAGE_ID,
    RECORDED,
    SESSION_ID,
    RecordedModel,
    ScriptedModel,
    assembler,
    grader_output,
    seeded_store,
    session_done,
    turn,
)

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


def reading_only(**changes) -> dict:
    """session.done for the demo session without its listening module."""
    done = session_done(listening_module_run=False, **changes)
    done.pop("listening_passage_id")
    done["turn_audio_uris"] = [
        t for t in done["turn_audio_uris"] if not t["phase"].startswith("LISTENING")
    ]
    return done


def test_two_passes_that_agree_are_combined_without_a_third():
    store, model = seeded_store(), RecordedModel()
    final_grader(store, model).handle(session_done())
    assert sorted(model.keys) == [
        f"{LISTEN_ID}/pass1",
        f"{LISTEN_ID}/pass2",
        f"{PASSAGE_ID}/pass1",
        f"{PASSAGE_ID}/pass2",
    ]
    grading = store.get(paths.grading(SESSION_ID))
    assert grading["read"] == {
        "passage_id": PASSAGE_ID,
        "total_weight": 6,
        "weighted_credit": 5.5,
        "item_points": [2, 0],
        "disagreement": False,
    }
    assert grading["listen"] == {
        "passage_id": LISTEN_ID,
        "total_weight": 6,
        "weighted_credit": 3.0,
        "item_points": [2],
        "disagreement": False,
    }
    assert (grading["reading_stopped_early"], grading["session_flags"]) == (False, ["DEMO_PROFILE"])


def test_the_grader_hears_the_whole_retell_with_unsure_words_marked():
    store = seeded_store()
    model = same_passes(
        grader_output({"p1": 1, "p2": 1, "p3": 1, "p4": 1}, {f"{PASSAGE_ID}_q1": 2})
    )
    final_grader(store, model).handle(reading_only())
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
    final_grader(store, model).handle(reading_only())
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
    turns = [
        turn(1, "READING"),
        turn(15, "LISTENING_RETELL"),
        turn(16, "LISTENING_QUESTION"),
    ]
    spoken = Transcripts({15: "it rained on the farm", 16: "because of the rain"})
    model = same_passes(
        grader_output({"p1": 1, "p2": 0, "p3": 0, "p4": 0}, {f"{LISTEN_ID}_q1": 2}, LISTEN_ID),
        LISTEN_ID,
    )
    done = session_done(reading_stopped_early=True, turn_audio_uris=turns)
    final_grader(store, model, spoken).handle(done)
    grading = store.get(paths.grading(SESSION_ID))
    assert grading["reading_stopped_early"] is True
    assert grading["read"] is None
    assert grading["listen"]["weighted_credit"] == 1.0
    assert grading["listen"]["item_points"] == [2]


def test_the_listening_passage_is_the_one_the_event_names():
    store = seeded_store()
    other = store.get(paths.passage(LISTEN_ID)) | {"passage_id": "bank_l3_other"}
    store.set(paths.passage("bank_l3_other"), other)
    recorded = json.loads((RECORDED / "grader" / f"{SESSION_ID}.json").read_text())
    for number in (1, 2):
        recorded[f"bank_l3_other/pass{number}"] = recorded[f"{LISTEN_ID}/pass{number}"] | {
            "passage_id": "bank_l3_other"
        }
    model = ScriptedModel(recorded)
    final_grader(store, model).handle(session_done(listening_passage_id="bank_l3_other"))
    assert store.get(paths.grading(SESSION_ID))["listen"]["passage_id"] == "bank_l3_other"


def test_the_parts_of_an_answer_are_heard_together_in_order():
    store = seeded_store()
    done = reading_only()
    done["turn_audio_uris"].insert(3, turn(18, "QUESTION", index=0, part=1))
    spoken = Transcripts({11: "ada went to market", 13: "say it again", 18: "it was red"})
    model = same_passes(
        grader_output({"p1": 1, "p2": 0, "p3": 0, "p4": 0}, {f"{PASSAGE_ID}_q1": 2})
    )
    final_grader(store, model, spoken).handle(done)
    assert dict(model.tasks[0].answers) == {f"{PASSAGE_ID}_q1": "say it again it was red"}


@pytest.mark.parametrize(
    "change",
    [
        lambda turns: turns.append(turn(18, "QUESTION", index=2)),
        lambda turns: turns.remove(next(t for t in turns if t["turn_id"] == "turn_014")),
    ],
    ids=["an item the passage lacks", "an item with no answer"],
)
def test_answer_turns_that_cannot_be_matched_to_items_are_refused(change):
    store = seeded_store()
    done = session_done()
    change(done["turn_audio_uris"])
    with pytest.raises(TurnMismatch):
        final_grader(store, RecordedModel()).handle(done)
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
    assert len(model.keys) == 4
