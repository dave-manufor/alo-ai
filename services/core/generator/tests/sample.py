"""A fictional story that passes every code check at ARL 3 in the DEMO length profile
(75 +/- 5 words), and the small name list and blocklist the tests use."""

import copy

from services.core.generator.names import Blocklist, Name, NameList

NAMES = NameList(
    (
        Name("Ada", "ˈɑːdɑ", "PERSON"),
        Name("Tunde", "ˈtundɛ", "PERSON"),
        Name("Mama", "ˈmɑːmɑ", "KIN"),
        Name("Lagos", "ˈleɪɡɒs", "PLACE"),
    )
)

BLOCKLIST = Blocklist(frozenset({"gun", "knife", "kill", "blood", "kiss", "church"}))

SENTENCES = [
    "Ada and Tunde went to the market with Mama.",
    "The sun was hot and the market was full.",
    "Mama bought some rice, fish and ripe tomatoes.",
    "Tunde saw a tall man selling shiny blue balls.",
    "He wanted a ball, but he had no money.",
    "Ada gave Tunde her coins and he bought the ball.",
    "Tunde ran to the field and kicked it high.",
    "Mama laughed and said that Ada was kind.",
    "They all went home with a smile.",
]

STORY = {
    "title": "The Blue Ball",
    "sentences": SENTENCES,
    "propositions": [
        {
            "id": "p1",
            "sentence_index": 0,
            "category": "SETTING",
            "description": "Ada, Tunde and Mama went to the market.",
            "weight": 1,
        },
        {
            "id": "p2",
            "sentence_index": 4,
            "category": "PROBLEM",
            "description": "Tunde wanted a ball but had no money.",
            "weight": 2,
        },
        {
            "id": "p3",
            "sentence_index": 5,
            "category": "ACTION",
            "description": "Ada gave Tunde her coins so he bought the ball.",
            "weight": 2,
        },
        {
            "id": "p4",
            "sentence_index": 6,
            "category": "RESOLUTION",
            "description": "Tunde kicked the ball high in the field.",
            "weight": 1,
        },
        {
            "id": "p5",
            "sentence_index": 7,
            "category": "RESOLUTION",
            "description": "Mama said Ada was kind.",
            "weight": 1,
        },
    ],
    "items": [
        {
            "item_id": "q1",
            "order": 1,
            "type": "LITERAL",
            "target_sentence_index": 3,
            "prompt_text": "What did Tunde see at the market?",
            "rubric": {
                "2": "A ball, or a blue ball.",
                "1": "Something that was for sale, such as a toy.",
                "0": "Something else, or no answer.",
            },
            "exemplars": [
                {"answer": "A blue ball.", "points": 2, "variety": "STANDARD"},
                {"answer": "Na ball he see.", "points": 2, "variety": "PIDGIN"},
                {"answer": "A toy.", "points": 1, "variety": "STANDARD"},
                {"answer": "Some rice.", "points": 0, "variety": "STANDARD"},
            ],
        },
        {
            "item_id": "q2",
            "order": 2,
            "type": "INFERENTIAL",
            "target_sentence_index": 5,
            "prompt_text": "Why did Mama say Ada was kind?",
            "rubric": {
                "2": "Ada used her own money to help her brother get the ball.",
                "1": "Says Ada is nice or good, without a reason.",
                "0": "A reason that is not in the story, or no answer.",
            },
            "exemplars": [
                {
                    "answer": "She used her own money so her brother could get a toy.",
                    "points": 2,
                    "variety": "NIGERIAN_ENGLISH",
                },
                {"answer": "Because she is nice.", "points": 1, "variety": "STANDARD"},
                {"answer": "Because the sun was hot.", "points": 0, "variety": "STANDARD"},
            ],
        },
    ],
}


def story(**changes) -> dict:
    """A deep copy of the sample story with top-level fields replaced."""
    return {**copy.deepcopy(STORY), **changes}
