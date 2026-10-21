"""Step G4, the Critic (PRD 4.5): three Gemini Flash calls that run only when the code
checks pass.

- A answers every question from the story.
- B answers the same questions from the title and the questions alone. It never sees
  the story, so it shows what a child could guess without reading.
- C scores both sets of answers against the rubrics. B cannot be given the rubric, so a
  separate call does the scoring.

A and B run in parallel; C runs when both are in. The results are two more gate checks:
items_answerable (A earns 2 points on every item) and items_not_guessable (B earns at
most 1 point in total on the literal items). The points rate the questions, never a child.

Changing a prompt means rerunning the story evaluation set (alo-prompt-eval) under a new
PROMPT_VERSION.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from jsonschema import Draft202012Validator

from .gate import Check
from .models import FLASH, Model, ModelCall, ModelError

MODEL = FLASH
PROMPT_VERSION = "critic_v1"
MAX_GUESSED_POINTS = 1  # [CAL] B's points on the literal items, at most (PRD 4.5 G4)
CHECK_NAMES = ("items_answerable", "items_not_guessable")

ANSWERS_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"item_id": {"type": "string"}, "answer": {"type": "string"}},
                "required": ["item_id", "answer"],
            },
        }
    },
    "required": ["answers"],
}
SCORES_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "answer_set": {"type": "string", "enum": ["A", "B"]},
                    "item_id": {"type": "string"},
                    "points": {"type": "integer", "minimum": 0, "maximum": 2},
                },
                "required": ["answer_set", "item_id", "points"],
            },
        }
    },
    "required": ["scores"],
}

ANSWER_FROM_STORY = """\
Read the story, then answer each question as a careful reader would, in one short
sentence. Answer from the story only."""

ANSWER_BLIND = """\
You have NOT read the story. You only know its title and the questions. Answer each
question with your best guess, in one short sentence. Always give a guess."""

SCORE = """\
Score each answer against its question's rubric: 2, 1 or 0 points. Use the rubric and
the example answers. Score meaning only; accept Nigerian English and Nigerian Pidgin.
There are two sets of answers, A and B. Score every answer in both sets."""


def review(
    model: Model,
    story: dict,
    session_id: str,
    attempt: int,
    timeout_s: Callable[[], float],
) -> list[Check]:
    """The Critic's two checks. timeout_s gives each call the time it may take, read
    when the call starts. Raises ModelError when an answer is unusable."""
    items = story["items"]
    a_call = _call(
        "critic_a",
        attempt,
        session_id,
        _answer_prompt(story, blind=False),
        ANSWERS_SCHEMA,
        timeout_s(),
    )
    b_call = _call(
        "critic_b",
        attempt,
        session_id,
        _answer_prompt(story, blind=True),
        ANSWERS_SCHEMA,
        timeout_s(),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        a_future, b_future = pool.submit(model.call, a_call), pool.submit(model.call, b_call)
        a = _answers(a_future.result(), items, a_call.key)
        b = _answers(b_future.result(), items, b_call.key)
    c_call = _call(
        "critic_c", attempt, session_id, _score_prompt(story, a, b), SCORES_SCHEMA, timeout_s()
    )
    points = _scores(model.call(c_call), items, c_call.key)
    return _checks(items, points)


def _call(
    role: str, attempt: int, session_id: str, prompt: str, schema: dict, timeout_s: float
) -> ModelCall:
    return ModelCall(
        key=f"{role}/{attempt}",
        session_id=session_id,
        model=MODEL,
        prompt=prompt,
        response_schema=schema,
        timeout_s=timeout_s,
    )


def _questions(items: Sequence[dict]) -> str:
    return "\n".join(f"{item['item_id']}: {item['prompt_text']}" for item in items)


def _answer_prompt(story: dict, *, blind: bool) -> str:
    if blind:
        return "\n\n".join(
            [ANSWER_BLIND, f"Title: {story['title']}", "Questions:\n" + _questions(story["items"])]
        )
    text = " ".join(story["sentences"])
    return "\n\n".join(
        [
            ANSWER_FROM_STORY,
            f"Story: {story['title']}\n{text}",
            "Questions:\n" + _questions(story["items"]),
        ]
    )


def _score_prompt(story: dict, a: dict[str, str], b: dict[str, str]) -> str:
    parts = [SCORE, f"Story: {story['title']}\n{' '.join(story['sentences'])}"]
    for item in story["items"]:
        rubric = "\n".join(f"  {points} points: {item['rubric'][points]}" for points in "210")
        examples = "\n".join(f"  ({e['points']}) {e['answer']}" for e in item["exemplars"])
        parts.append(
            f"{item['item_id']}: {item['prompt_text']}\nRubric:\n{rubric}\n"
            f"Example answers:\n{examples}\n"
            f"Answer A: {a[item['item_id']]}\nAnswer B: {b[item['item_id']]}"
        )
    return "\n\n".join(parts)


def _answers(output: dict, items: Sequence[dict], key: str) -> dict[str, str]:
    _validate(output, ANSWERS_SCHEMA, key)
    answers = {a["item_id"]: a["answer"] for a in output["answers"]}
    if set(answers) != {item["item_id"] for item in items}:
        raise ModelError(f"{key} answered other questions than it was asked")
    return answers


def _scores(output: dict, items: Sequence[dict], key: str) -> dict[tuple[str, str], int]:
    _validate(output, SCORES_SCHEMA, key)
    points = {(s["answer_set"], s["item_id"]): s["points"] for s in output["scores"]}
    wanted = {(answer_set, item["item_id"]) for answer_set in "AB" for item in items}
    if set(points) != wanted or len(output["scores"]) != len(wanted):
        raise ModelError(f"{key} scored other answers than it was given")
    return points


def _checks(items: Sequence[dict], points: dict[tuple[str, str], int]) -> list[Check]:
    unanswerable = [item["item_id"] for item in items if points[("A", item["item_id"])] != 2]
    literal = [item["item_id"] for item in items if item["type"] == "LITERAL"]
    guessed = sum(points[("B", item_id)] for item_id in literal)
    return [
        Check(
            "items_answerable",
            not unanswerable,
            f"a reader of the story could not fully answer {', '.join(unanswerable)}"
            if unanswerable
            else "",
        ),
        Check(
            "items_not_guessable",
            guessed <= MAX_GUESSED_POINTS,
            f"the literal questions can be answered without reading the story ({guessed}"
            f" points from the title and questions alone; at most {MAX_GUESSED_POINTS})"
            if guessed > MAX_GUESSED_POINTS
            else "",
        ),
    ]


def _validate(output: dict, schema: dict, key: str) -> None:
    error = next(iter(Draft202012Validator(schema).iter_errors(output)), None)
    if error is not None:
        raise ModelError(f"{key} broke its output schema: {error.message}")
