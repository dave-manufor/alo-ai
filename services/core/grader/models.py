"""The grading model (PRD 7): one call credits a passage's propositions, scores its
items, or both. The model never computes a score; aloai_scoring does.

VertexGradingModel calls Gemini on Vertex AI. FixtureGradingModel answers from the
recorded responses in fixtures/ai/grader/, so laptops and CI never reach Vertex
(AI_MODE=fixtures). Callers pass every answer through grade() here, which checks it.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from google import genai
from google.genai import types

from .. import contracts
from .prompts import build_prompt

QUICK_MODEL = "gemini-2.5-flash"
GRADER_MODEL = "gemini-2.5-pro"


@dataclass(frozen=True)
class GradingTask:
    """One model call. key names it among the recorded responses, e.g. "quick/RETELL_0"."""

    key: str
    session_id: str
    model: str
    passage: dict
    retell: str | None
    answers: Mapping[str, str]
    primary_class: int | None = None
    pass_number: int = 1


class GradingError(Exception):
    """The model gave no usable answer for the task."""


class GradingModel(Protocol):
    def grade(self, task: GradingTask) -> dict: ...


_RESPONSE_SCHEMA = {
    key: value
    for key, value in contracts.load("grader_output.schema.json").items()
    if key not in ("$schema", "$id")
}
_CONFIG = types.GenerateContentConfig(
    temperature=0,
    response_mime_type="application/json",
    response_json_schema=_RESPONSE_SCHEMA,
)


class VertexGradingModel:
    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def grade(self, task: GradingTask) -> dict:
        prompt = build_prompt(
            passage=task.passage,
            retell=task.retell,
            answers=task.answers,
            primary_class=task.primary_class,
            pass_number=task.pass_number,
        )
        response = self._client.models.generate_content(
            model=task.model, contents=prompt, config=_CONFIG
        )
        return _parse(response.text)


class FixtureGradingModel:
    def __init__(self, root: Path) -> None:
        self._root = root

    def grade(self, task: GradingTask) -> dict:
        path = self._root / f"{task.session_id}.json"
        recorded = json.loads(path.read_text()) if path.exists() else {}
        if task.key not in recorded:
            raise GradingError(f"no recorded response {task.key} for {task.session_id}")
        return recorded[task.key]


def grade(model: GradingModel, task: GradingTask) -> dict:
    """The model's GraderOutput for the task, refused if it breaks the schema or grades
    other propositions or items than it was asked."""
    output = model.grade(task)
    error = next(iter(contracts.GRADER_OUTPUT.iter_errors(output)), None)
    if error is not None:
        raise GradingError(f"{task.key} is not a GraderOutput: {error.message}")
    propositions = (
        {p["id"] for p in task.passage["propositions"]} if task.retell is not None else set()
    )
    graded_propositions = {p["id"] for p in output["propositions"]}
    graded_items = {i["item_id"] for i in output["items"]}
    if graded_propositions != propositions or graded_items != set(task.answers):
        raise GradingError(f"{task.key} graded other propositions or items than it was asked")
    return output


def _parse(text: str | None) -> dict:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise GradingError(f"the model did not return JSON: {error}") from error
