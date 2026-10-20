"""The boundary rule, on hand-labelled sentences (PRD 4.5 G3).

Labels: - NONE, P PHRASE, C CLAUSE, T TERMINAL, one per whitespace token. The parse-based
cases are pinned to en_core_web_sm 3.8.0, the model requirements.txt installs.
"""

import pytest
from services.core.generator.boundaries import analyse, boundaries

CODE = {"-": "NONE", "P": "PHRASE", "C": "CLAUSE", "T": "TERMINAL"}


def labels(sentence, nlp):
    short = {value: key for key, value in CODE.items()}
    return "".join(short[label] for label in boundaries(sentence, nlp))


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        # only the end of the sentence
        ("Ada went to the market.", "----T"),
        ("Ada saw a red hat.", "----T"),
        ("It cost too much.", "---T"),
        ("The goat ate the leaves and the grass.", "-------T"),
        # a prepositional phrase of three words after three words, no punctuation
        ("Ada and Mama went to the market.", "---P--T"),
        ("The boy ran to the old market near the river.", "--P---P--T"),
        # a new clause starts: "and" between verbs, a subordinator
        ("Ada ran and Tunde laughed.", "-C--T"),
        ("Ada went to the market and she bought a hat.", "----C----T"),
        ("The children stayed inside because it rained.", "---C--T"),
        ("Mama said that the rain would stop soon.", "-C-----T"),
        # commas
        ("When it rained, the children stayed inside.", "--C---T"),
        ("Ada smiled, and Mama smiled too.", "-C---T"),
        ("Tunde, who was hungry, ate the mango.", "C--C--T"),
        ("Ada ran home, but the door was shut.", "--C----T"),
        # a dash, a quotation
        ("She looked at the sky — it was dark.", "----C---T"),
        ('"Come here," said Mama.', "-C-T"),
    ],
)
def test_boundaries_after_each_token(nlp, sentence, expected):
    assert labels(sentence, nlp) == expected


def test_a_lone_dash_is_a_token_with_no_boundary_of_its_own(nlp):
    tokens = "Ada waited — and then she left.".split()
    found = boundaries("Ada waited — and then she left.", nlp)
    assert len(found) == len(tokens)
    assert found[2] == "NONE"
    assert found[-1] == "TERMINAL"
    assert found[1] in {"PHRASE", "CLAUSE"}  # the dash marks "waited"


def test_one_label_and_a_part_of_speech_per_whitespace_token(nlp):
    found = analyse("Ada saw the red hat.", nlp)
    assert [pos for _, pos in found] == ["PROPN", "VERB", "DET", "ADJ", "NOUN"]
    assert [label for label, _ in found] == ["NONE"] * 4 + ["TERMINAL"]


def test_an_empty_sentence_has_no_tokens(nlp):
    assert boundaries("", nlp) == [] and boundaries("   ", nlp) == []


def test_only_the_last_token_is_ever_terminal(nlp):
    for sentence in ["Mr. Okoro came home.", "Is it hot? Yes!"]:
        found = boundaries(sentence, nlp)
        assert found.count("TERMINAL") == 1 and found[-1] == "TERMINAL"
