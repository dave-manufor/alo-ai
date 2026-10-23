"""Step G2: the Story Writer (PRD 4.5). One Gemini Flash call writes the title, the
sentences, the propositions and the items for the target level. Code checks everything
it returns (gate.py, critic.py); nothing the Writer says is trusted.

Changing the prompt means rerunning the story evaluation set (alo-prompt-eval) under a
new PROMPT_VERSION.
"""

from dataclasses import dataclass

from jsonschema import Draft202012Validator

from . import blueprint
from .data import Topic
from .models import FLASH, Model, ModelCall, ModelError
from .names import NameList

MODEL = FLASH
PROMPT_VERSION = "writer_v1"
TEMPERATURE = 1.0  # a retry with feedback should not write the same story again

CATEGORIES = ["SETTING", "CHARACTER", "PROBLEM", "ACTION", "RESOLUTION", "MAIN_IDEA", "DETAIL"]
VARIETIES = ["STANDARD", "NIGERIAN_ENGLISH", "PIDGIN"]

# The Writer's output: the story dict gate.run() reads. Numbers use minimum and maximum,
# not enum, which keeps to what Vertex's response schema accepts for sure.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sentences": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "propositions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "sentence_index": {"type": "integer", "minimum": 0},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "description": {"type": "string"},
                    "weight": {"type": "integer", "minimum": 1, "maximum": 2},
                },
                "required": ["id", "sentence_index", "category", "description", "weight"],
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "order": {"type": "integer", "minimum": 1},
                    "type": {"type": "string", "enum": ["LITERAL", "INFERENTIAL"]},
                    "target_sentence_index": {"type": "integer", "minimum": 0},
                    "prompt_text": {"type": "string"},
                    "rubric": {
                        "type": "object",
                        "properties": {
                            "2": {"type": "string"},
                            "1": {"type": "string"},
                            "0": {"type": "string"},
                        },
                        "required": ["2", "1", "0"],
                    },
                    "exemplars": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "answer": {"type": "string"},
                                "points": {"type": "integer", "minimum": 0, "maximum": 2},
                                "variety": {"type": "string", "enum": VARIETIES},
                            },
                            "required": ["answer", "points", "variety"],
                        },
                    },
                },
                "required": [
                    "item_id",
                    "order",
                    "type",
                    "target_sentence_index",
                    "prompt_text",
                    "rubric",
                    "exemplars",
                ],
            },
        },
    },
    "required": ["title", "sentences", "propositions", "items"],
}
_VALIDATOR = Draft202012Validator(OUTPUT_SCHEMA)


@dataclass(frozen=True)
class Brief:
    """What the Writer is asked for. Every detail has already passed detail.safe_details."""

    session_id: str
    target_arl: int
    length_profile: str
    genre: str  # NARRATIVE | EXPOSITORY
    topics: tuple[Topic, ...]
    details: tuple[str, ...]
    names: NameList
    attempt: int = 1
    feedback: str = ""  # the failed checks of the first attempt, for the retry


INSTRUCTIONS = """\
You write one short original story for a Nigerian primary school child to read aloud,
with questions that check the child understood it.

Rules:
- A Nigerian setting: a home, a school, a market, a farm, a street or a town in Nigeria.
- British spelling. Plain sentences, each ending with . ! or ?
- Write numbers as words, never digits.
- People and places: use only names from the name list, exactly as spelled there. No other
  names, no real people, no brands.
- Nothing about religion, politics, romance, violence, weapons, death, alcohol, or anything
  frightening. Kind, everyday and gently funny is best.
- Avoid words that are said two ways: read, live, wind, tear, bow, lead.
- Keep to the length and sentence rules below exactly; count the words."""

NARRATIVE = """\
Text type: a story. Follow this plan: a character and a setting, a problem, two or three
events, and a resolution. Proposition categories: SETTING, CHARACTER, PROBLEM, ACTION,
RESOLUTION."""

EXPOSITORY = """\
Text type: a short factual text. One main idea, then details that explain it, told
simply and correctly, in a Nigerian setting where it fits. Proposition categories:
MAIN_IDEA and DETAIL."""


def build_prompt(brief: Brief) -> str:
    rules = blueprint.rules_for(brief.length_profile)
    row = blueprint.row_for(brief.target_arl)
    low, high = blueprint.word_range(brief.target_arl, brief.length_profile)
    p_low, p_high = rules.propositions
    parts = [
        INSTRUCTIONS,
        NARRATIVE if brief.genre == "NARRATIVE" else EXPOSITORY,
        _topic(brief),
        "\n".join(
            [
                f"Level and length (reading level {brief.target_arl} of 12):",
                f"- {low} to {high} words in all.",
                f"- Sentences of {row.max_mean_sentence:g} words or fewer on average.",
                (
                    f"- At least {row.zipf_share:.0%} of the words should be very common ones a young"
                    " child knows."
                ),
                f"- At most {row.max_long_share:.0%} of the words with three or more syllables.",
            ]
        ),
        "\n".join(
            [
                "Propositions (the story's ideas, used to mark the child's retell):",
                (
                    f"- {p_low} to {p_high} propositions, ids p1, p2, ... Each has the index"
                    " (from 0) of the sentence it comes from, a category, and a short"
                    " description that uses words from that sentence."
                ),
                (
                    f"- Weight 2 for the core ideas a good retell must have (at least"
                    f" {rules.core_min}), weight 1 for the others."
                ),
            ]
        ),
        _items(rules),
        "Name list: " + ", ".join(f"{n.text} ({n.kind.lower()})" for n in brief.names.entries),
    ]
    if brief.feedback:
        parts.append(
            "Your last story failed these checks. Write a new story that passes them:\n"
            + brief.feedback
        )
    return "\n\n".join(parts)


def _topic(brief: Brief) -> str:
    if brief.topics:
        line = "Topic: " + " and ".join(topic.description for topic in brief.topics) + "."
    else:
        line = "Topic: any everyday topic a Nigerian child enjoys."
    if brief.details:
        line += f" Include {_listed(brief.details)} in the story."
    return line


def _listed(items: tuple[str, ...]) -> str:
    """The things the child named, as one phrase: "a", "a and b", "a, b and c"."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _items(rules: blueprint.LengthRules) -> str:
    count = rules.literal_items + rules.inferential_items
    return "\n".join(
        [
            f"Questions: exactly {count}, with order 1 to {count} and ids q1, q2, ...:",
            (
                f"- {rules.literal_items} LITERAL: the answer is stated in one sentence"
                " (target_sentence_index). It must not be guessable from the title and question"
                " alone."
            ),
            (
                f"- {rules.inferential_items} INFERENTIAL, last: the answer is never written in"
                " the story; the child gets it by linking two sentences."
            ),
            "- Short spoken questions a seven to twelve year old understands.",
            (
                "- A rubric for 2, 1 and 0 points, and example answers for each of 2, 1 and 0"
                " points. Include at least one example answer in Nigerian English or Nigerian"
                " Pidgin, marked with its variety."
            ),
        ]
    )


def write(model: Model, brief: Brief, timeout_s: float) -> dict:
    """The Writer's story, refused (ModelError) if it breaks the output schema."""
    call = ModelCall(
        key=f"writer/{brief.attempt}",
        session_id=brief.session_id,
        model=MODEL,
        prompt=build_prompt(brief),
        response_schema=OUTPUT_SCHEMA,
        timeout_s=timeout_s,
        temperature=TEMPERATURE,
    )
    story = model.call(call)
    error = next(iter(_VALIDATOR.iter_errors(story)), None)
    if error is not None:
        raise ModelError(f"{call.key} broke the output schema: {error.message}")
    return story
