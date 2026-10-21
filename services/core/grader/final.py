"""Final grading on session.done (PRD 7.2, SDD 7 steps 1 to 3).

Chirp 3 transcribes each retell and answer. Each passage is then graded by two
independent Gemini 2.5 Pro passes, with a third when they disagree, and the
reconciled credits and points are stored for report assembly. Grading already
stored is not redone, so a redelivered event changes nothing.

session.done (schema_version 2) names the passages, says whether the kindness rule
ended the reading, and gives each turn the item it answers (index) and its place among
that item's recordings (part); the parts of a retell or an answer are heard together.
"""

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import aloai_scoring as scoring
from aloai_store import Store, require

from . import paths
from .asr import Transcriber, transcript
from .assembly import ReportAssembler
from .models import GRADER_MODEL, GradingModel, GradingTask, grade
from .passages import ordered_items, total_weight, weights

MAX_PARALLEL_TRANSCRIPTS = 8


class TurnMismatch(ValueError):
    pass


@dataclass(frozen=True)
class PassScore:
    credit: float
    points: tuple[int, ...]


def answer_turns(passage: dict, turns: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """The turns that answer each item, by item_id, in part order. A turn for an item the
    passage does not have, or an item with no turn, means the event is wrong."""
    items = ordered_items(passage)
    answers: dict[str, list[str]] = {item["item_id"]: [] for item in items}
    for turn in sorted(turns, key=lambda turn: (turn["index"], turn["part"])):
        if turn["index"] >= len(items):
            raise TurnMismatch(
                f"{turn['turn_id']} answers item {turn['index']}, "
                f"but {passage['passage_id']} has {len(items)}"
            )
        answers[items[turn["index"]]["item_id"]].append(turn["turn_id"])
    unanswered = [item_id for item_id, turn_ids in answers.items() if not turn_ids]
    if unanswered:
        raise TurnMismatch(f"no answer turn for {', '.join(unanswered)}")
    return answers


@dataclass(frozen=True)
class FinalGrader:
    store: Store
    model: GradingModel
    transcriber: Transcriber
    assembler: ReportAssembler

    def handle(self, done: Mapping[str, Any]) -> None:
        """done is the data of a session.done event."""
        session_id = done["session_id"]
        if self.store.get(paths.grading(session_id)) is None:
            self.store.set(paths.grading(session_id), self._grade(done))
        self.assembler.assemble(session_id)

    def _grade(self, done: Mapping[str, Any]) -> dict:
        session_id = done["session_id"]
        session = require(self.store, paths.session(session_id))
        primary_class = require(self.store, paths.child(session["child_id"]))["primary_class"]
        targets = self._targets(done)
        phases = {
            phase for _, retell_phase, item_phase in targets for phase in (retell_phase, item_phase)
        }
        turns = sorted(
            (turn for turn in done["turn_audio_uris"] if turn["phase"] in phases),
            key=lambda turn: turn["part"],
        )
        matched = {
            passage["passage_id"]: answer_turns(
                passage, [t for t in turns if t["phase"] == item_phase]
            )
            for passage, _, item_phase in targets
        }
        texts = self._transcribe(session_id, turns)
        graded = {}
        for passage, retell_phase, _ in targets:
            retell = " ".join(texts[t["turn_id"]] for t in turns if t["phase"] == retell_phase)
            answers = {
                item_id: " ".join(texts[turn_id] for turn_id in turn_ids).strip()
                for item_id, turn_ids in matched[passage["passage_id"]].items()
            }
            graded[passage["mode"]] = self._grade_passage(
                session_id, passage, primary_class, retell.strip(), answers
            )
        return {
            "reading_stopped_early": done["reading_stopped_early"],
            "listening_module_run": done["listening_module_run"],
            "capture_mode": done["capture_mode"],
            "session_settings": done["session_settings"],
            "session_flags": done["flags"],
            "read": graded.get("READ"),
            "listen": graded.get("LISTEN"),
        }

    def _targets(self, done: Mapping[str, Any]) -> list[tuple[dict, str, str]]:
        """The passages to grade, with the turn phases of their retell and items."""
        targets = []
        if not done["reading_stopped_early"]:
            read = require(self.store, paths.passage(done["passage_id"]))
            targets.append((read, "RETELL", "QUESTION"))
        if done["listening_module_run"]:
            listen = require(self.store, paths.passage(done["listening_passage_id"]))
            targets.append((listen, "LISTENING_RETELL", "LISTENING_QUESTION"))
        return targets

    def _transcribe(self, session_id: str, turns: Sequence[Mapping[str, Any]]) -> dict[str, str]:
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_TRANSCRIPTS) as pool:
            texts = list(
                pool.map(lambda turn: transcript(self.transcriber.words(turn["audio_uri"])), turns)
            )
        for turn, text in zip(turns, texts):
            self.store.merge(paths.turn(session_id, turn["turn_id"]), {"asr_transcript": text})
        return {turn["turn_id"]: text for turn, text in zip(turns, texts)}

    def _grade_passage(
        self,
        session_id: str,
        passage: dict,
        primary_class: int,
        retell: str,
        answers: Mapping[str, str],
    ) -> dict:
        spoken = {item_id: words for item_id, words in answers.items() if words.strip()}

        def task(pass_number: int) -> GradingTask:
            return GradingTask(
                key=f"{passage['passage_id']}/pass{pass_number}",
                session_id=session_id,
                model=GRADER_MODEL,
                passage=passage,
                retell=retell or None,
                answers=spoken,
                primary_class=primary_class,
                pass_number=pass_number,
            )

        retell_result, items_result = self._reconcile(
            passage, task, nothing_said=not retell and not spoken
        )
        return {
            "passage_id": passage["passage_id"],
            "total_weight": total_weight(passage),
            "weighted_credit": retell_result.credit,
            "item_points": list(items_result.points),
            "disagreement": retell_result.disagreement or items_result.disagreement,
        }

    def _reconcile(
        self, passage: dict, task: Callable[[int], GradingTask], *, nothing_said: bool
    ) -> tuple[scoring.CombinedRetell, scoring.CombinedItems]:
        if nothing_said:
            silent = self._score(passage, {"propositions": [], "items": []})
            return (
                scoring.CombinedRetell(silent.credit, disagreement=False),
                scoring.CombinedItems(silent.points, disagreement=False),
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(
                lambda n: self._score(passage, grade(self.model, task(n))), (1, 2)
            )
        third = None
        if scoring.retell_needs_third_pass(
            first.credit, second.credit
        ) or scoring.items_need_third_pass(first.points, second.points):
            third = self._score(passage, grade(self.model, task(3)))
        return (
            scoring.combine_retell_passes(
                first.credit, second.credit, third.credit if third else None
            ),
            scoring.combine_item_passes(
                first.points, second.points, third.points if third else None
            ),
        )

    @staticmethod
    def _score(passage: dict, output: dict) -> PassScore:
        """One pass's weighted retell credit and item points; anything not graded is 0."""
        credits = {p["id"]: p["credit"] for p in output["propositions"]}
        points = {i["item_id"]: i["points"] for i in output["items"]}
        return PassScore(
            credit=scoring.weighted_credit(
                [(w, credits.get(pid, 0)) for pid, w in weights(passage).items()]
            ),
            points=tuple(points.get(item["item_id"], 0) for item in ordered_items(passage)),
        )
