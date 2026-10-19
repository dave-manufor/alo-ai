"""In-session quick scoring, POST /v1/grade:quick (PRD 7.4, SDD 7).

One Gemini Flash pass per retell or item, stored under sessions/{id}/quick so a
repeated call returns the stored result. An unanswered item scores 0 without a
model call. Once the retell and every item are in, aloai_scoring decides whether
the listening module runs; the quick RC is stored for the report, never returned.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import aloai_scoring as scoring

from ..store import Store
from . import paths
from .models import QUICK_MODEL, GradingModel, GradingTask, grade
from .passages import ordered_items, total_weight, weights

SCHEMA_VERSION = 1


class PassageNotFound(LookupError):
    pass


class UnknownItem(ValueError):
    pass


@dataclass(frozen=True)
class QuickGrader:
    store: Store
    model: GradingModel

    def grade(self, request: Mapping[str, Any]) -> dict:
        """request must already match schemas/grade_quick_request.schema.json."""
        session_id = request["session_id"]
        passage = self._passage(request["passage_id"])
        path = paths.quick(session_id, request["turn_phase"], request["index"])
        if self.store.get(path) is None:
            self.store.set(path, self._score(request, passage))
        return self._decision(session_id, passage)

    def _passage(self, passage_id: str) -> dict:
        passage = self.store.get(paths.passage(passage_id))
        if passage is None:
            raise PassageNotFound(f"no passage {passage_id}")
        return passage

    def _score(self, request: Mapping[str, Any], passage: dict) -> dict:
        words = request["transcript"].strip()
        if request["turn_phase"] == "RETELL":
            credits = self._retell_credits(request, passage, words) if words else {}
            pairs = [(w, credits.get(pid, 0)) for pid, w in weights(passage).items()]
            return {"weighted_credit": scoring.weighted_credit(pairs)}
        items = ordered_items(passage)
        if request["index"] >= len(items):
            raise UnknownItem(f"{passage['passage_id']} has {len(items)} items")
        item_id = items[request["index"]]["item_id"]
        points = self._item_points(request, passage, item_id, words) if words else 0
        return {"item_id": item_id, "points": points}

    def _retell_credits(self, request: Mapping[str, Any], passage: dict, words: str) -> dict:
        output = grade(self.model, self._task(request, passage, retell=words, answers={}))
        return {p["id"]: p["credit"] for p in output["propositions"]}

    def _item_points(
        self, request: Mapping[str, Any], passage: dict, item_id: str, words: str
    ) -> int:
        task = self._task(request, passage, retell=None, answers={item_id: words})
        return grade(self.model, task)["items"][0]["points"]

    def _task(self, request: Mapping[str, Any], passage: dict, **graded: Any) -> GradingTask:
        return GradingTask(
            key=f"quick/{request['turn_phase']}_{request['index']}",
            session_id=request["session_id"],
            model=QUICK_MODEL,
            passage=passage,
            **graded,
        )

    def _decision(self, session_id: str, passage: dict) -> dict:
        retell = self.store.get(paths.quick(session_id, "RETELL", 0))
        items = [
            self.store.get(paths.quick(session_id, "QUESTION", index))
            for index in range(len(passage["items"]))
        ]
        if retell is None or None in items:
            return {
                "schema_version": SCHEMA_VERSION,
                "complete": False,
                "run_listening_module": None,
            }
        points = [item["points"] for item in items]
        quick_rc = scoring.comprehension(retell["weighted_credit"], total_weight(passage), points)
        run = scoring.run_listening_module(quick_rc.score)
        self.store.set(
            paths.quick_result(session_id),
            {"quick_rc": quick_rc.score, "item_points": points, "run_listening_module": run},
        )
        return {"schema_version": SCHEMA_VERSION, "complete": True, "run_listening_module": run}
