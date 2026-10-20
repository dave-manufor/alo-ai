"""The code checks of the generation gate (PRD 4.5 G4), one failure at a time."""

import pytest
from services.core.generator import gate

from .sample import BLOCKLIST, NAMES, SENTENCES, STORY, story

DEMO_3 = gate.Request(target_arl=3, length_profile="DEMO")
NAMES_OF_CHECKS = [
    "blueprint",
    "difficulty",
    "safety",
    "names",
    "propositions",
    "inference_is_real",
    "items_shape",
    "plain_text",
    "no_ambiguous_words",
]


def run(candidate, request=DEMO_3, nlp=None):
    return {c.name: c for c in gate.run(candidate, request, nlp, NAMES, BLOCKLIST)}


@pytest.fixture
def check(nlp):
    def check(candidate, request=DEMO_3):
        return run(candidate, request, nlp)

    return check


def failed(found):
    return {name for name, c in found.items() if not c.passed}


def with_sentence(index, text):
    sentences = list(SENTENCES)
    sentences[index] = text
    return story(sentences=sentences)


def with_item(index, **changes):
    candidate = story()
    candidate["items"][index].update(changes)
    return candidate


def test_the_sample_story_passes_every_check(check):
    found = check(story())
    assert list(found) == NAMES_OF_CHECKS
    assert failed(found) == set()
    assert gate.passed(list(found.values()))
    assert gate.feedback(list(found.values())) == ""
    assert gate.results(list(found.values())) == dict.fromkeys(NAMES_OF_CHECKS, True)


def test_feedback_lists_every_failed_check(nlp):
    checks = gate.run(story(sentences=SENTENCES[:3]), DEMO_3, nlp, NAMES, BLOCKLIST)
    assert not gate.passed(checks)
    text = gate.feedback(checks)
    assert text.startswith("- blueprint: ") and "words" in text
    assert gate.results(checks)["blueprint"] is False


@pytest.mark.parametrize(
    ("request_", "message"),
    [
        (gate.Request(0, "DEMO"), "1 to 12"),
        (gate.Request(13, "DEMO"), "1 to 12"),
        (gate.Request(3, "LONG"), "STANDARD or DEMO"),
    ],
)
def test_a_bad_request_is_an_error_not_a_failed_check(nlp, request_, message):
    with pytest.raises(ValueError, match=message):
        gate.run(story(), request_, nlp, NAMES, BLOCKLIST)


@pytest.mark.parametrize("sentences", [[], ["", "  "], ["— !"]])
def test_a_story_with_no_words_fails_plain_text_and_nothing_raises(check, sentences):
    found = check(story(sentences=sentences))
    assert list(found) == ["plain_text"] and not found["plain_text"].passed


# ---- blueprint and difficulty


def test_too_few_words(check):
    found = check(story(sentences=SENTENCES[:6]))
    assert "blueprint" in failed(found)
    assert "words; this level needs 70 to 80" in found["blueprint"].reason


def test_the_standard_profile_wants_the_rows_word_count(check):
    found = check(story(), gate.Request(3, "STANDARD"))
    assert "needs 100 to 120" in found["blueprint"].reason


def test_sentences_that_are_too_long(check):
    long = ["Ada and Tunde went to the market with Mama and they saw the sun and many people."]
    found = check(story(sentences=long + SENTENCES[1:]))
    assert "the limit is 9" in found["blueprint"].reason


def test_too_few_common_words(check):
    rare = "Tunde saw marbles, trumpets, bangles, lanterns and puppets."
    found = check(with_sentence(3, rare))
    assert "words are common" in found["blueprint"].reason


def test_too_many_long_words(check):
    heavy = "Mama bought some vegetables, watermelons and enormous strawberries."
    found = check(with_sentence(2, heavy))
    assert "3 or more syllables" in found["blueprint"].reason


def test_a_story_too_easy_or_too_hard_for_the_target_level(check):
    found = check(story(), gate.Request(7, "DEMO"))
    assert "too easy for 7" in found["difficulty"].reason
    found = check(story(), gate.Request(1, "DEMO"))
    assert "too hard for 1" in found["difficulty"].reason


# ---- safety and names


@pytest.mark.parametrize(
    "where",
    [
        lambda s: s["sentences"].__setitem__(4, "He wanted a knife, but he had no money."),
        lambda s: s.__setitem__("title", "The Blood Ball"),
        lambda s: s["items"][0].__setitem__("prompt_text", "Who had a gun?"),
        lambda s: s["items"][0]["exemplars"][3].__setitem__("answer", "A knife."),
        lambda s: s["propositions"][0].__setitem__("description", "They went to church."),
    ],
)
def test_a_blocked_word_anywhere_fails_safety(check, where):
    candidate = story()
    where(candidate)
    found = check(candidate)
    assert "safety" in failed(found) and "uses" in found["safety"].reason


@pytest.mark.parametrize(
    ("candidate", "named"),
    [
        (with_sentence(0, "Ada and Kemi went to the market with Mama."), "Kemi"),
        (with_sentence(1, "The sun was hot in Abuja and the market was full."), "Abuja"),
        (with_sentence(1, "The sun was hot and the Market was full."), "Market"),
        (story(title="Kemi and the Ball"), "Kemi"),
        (with_item(0, prompt_text="What did Chidi see at the market?"), "Chidi"),
    ],
)
def test_a_name_not_on_the_list_fails(check, candidate, named):
    found = check(candidate)
    assert "names" in failed(found) and named in found["names"].reason


def test_names_on_the_list_and_a_title_in_title_case_pass(check):
    candidate = with_sentence(1, "Mama said Ada and Tunde could go to Lagos.")
    assert "names" not in failed(check(candidate))
    assert "names" not in failed(check(story(title="The Big Blue Ball")))


# ---- propositions


def test_too_many_or_too_few_propositions(check):
    many = story()
    many["propositions"] = many["propositions"] * 2
    assert "5 to 8" not in check(many)["propositions"].reason
    assert "10 propositions; 4 to 8" in check(many)["propositions"].reason
    few = story()
    few["propositions"] = few["propositions"][:3]
    assert "3 propositions; 4 to 8" in check(few)["propositions"].reason


def test_core_propositions_are_counted_by_weight_2(check):
    candidate = story()
    candidate["propositions"][1]["weight"] = 1
    assert "1 core propositions (weight 2); at least 2" in check(candidate)["propositions"].reason


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"category": "FEELING"}, "has category 'FEELING'"),
        ({"weight": 3}, "has weight 3"),
        ({"sentence_index": 99}, "cites sentence 99, which does not exist"),
        ({"sentence_index": None}, "cites sentence None"),
        ({"description": "A large elephant crossed a wide river."}, "shares no content word"),
        ({"id": "p1"}, "ids must be present and different"),
    ],
)
def test_a_proposition_must_be_valid_and_traceable_to_its_sentence(check, change, message):
    candidate = story()
    candidate["propositions"][1].update(change)
    found = check(candidate)
    assert "propositions" in failed(found) and message in found["propositions"].reason


# ---- the inferential item


def inferential(answer, points=2):
    candidate = story()
    candidate["items"][1]["exemplars"] = [
        {"answer": answer, "points": points, "variety": "NIGERIAN_ENGLISH"},
        {"answer": "Because she is nice.", "points": 1, "variety": "STANDARD"},
        {"answer": "No idea.", "points": 0, "variety": "STANDARD"},
    ]
    candidate["items"][0]["exemplars"][3]["points"] = 0
    return candidate


@pytest.mark.parametrize(
    ("answer", "how"),
    [
        ("Ada gave Tunde her coins and he bought the ball", "is contained in"),
        ("Ada gave Tunde her coins and he bought a ball", "is nearly the same as"),
        ("gave Tunde her coins", "is contained in"),
        ("Ada gave Tunde her coins and he bought the ball and then ran home", "is contained in"),
        ("Tunde bought the ball and Ada gave him coins", "shares almost all"),
    ],
)
def test_an_answer_that_copies_one_sentence_is_not_an_inference(check, answer, how):
    found = check(inferential(answer))
    assert "inference_is_real" in failed(found)
    assert how in found["inference_is_real"].reason
    assert "sentence 5" in found["inference_is_real"].reason


def test_an_answer_that_links_two_sentences_passes(check):
    answer = "She paid with her own money so that her brother could get a toy"
    assert "inference_is_real" not in failed(check(inferential(answer)))


def test_an_answer_with_no_words_is_not_a_copy_and_does_not_crash(check):
    assert "inference_is_real" not in failed(check(inferential("...")))


def test_the_inferential_item_needs_a_2_point_answer(check):
    found = check(inferential("She was kind to him", points=1))
    assert "q2 has no 2-point answer" in found["inference_is_real"].reason


def test_a_story_without_an_inferential_item_fails(check):
    candidate = with_item(1, type="LITERAL")
    assert "there is no inferential item" in check(candidate)["inference_is_real"].reason


# ---- items


def test_item_counts_follow_the_length_profile(check):
    found = check(story(), gate.Request(3, "STANDARD"))
    reason = found["items_shape"].reason
    assert "1 LITERAL items; 2 are needed" in reason
    assert "2 items in all; 3" in reason


@pytest.mark.parametrize(
    ("candidate", "message"),
    [
        (with_item(1, type="VOCABULARY"), "0 INFERENTIAL items; 1 are needed"),
        (with_item(1, order=3), "item order must be 1, 2, 3 in turn"),
        (with_item(1, item_id="q1"), "item ids must be present and different"),
        (with_item(0, prompt_text="  "), "q1 has no question"),
        (with_item(0, target_sentence_index=40), "q1 targets sentence 40"),
        (with_item(0, rubric={"2": "A ball.", "1": "A toy."}), "q1 needs a rubric for 2, 1 and 0"),
        (with_item(0, rubric={"2": "A ball.", "1": "A toy.", "0": ""}), "q1 needs a rubric"),
    ],
)
def test_an_item_must_be_well_formed(check, candidate, message):
    found = check(candidate)
    assert "items_shape" in failed(found) and message in found["items_shape"].reason


def test_each_item_needs_example_answers_for_0_1_and_2_points(check):
    candidate = story()
    candidate["items"][0]["exemplars"] = [
        {"answer": "A ball.", "points": 2, "variety": "STANDARD"},
        {"answer": "Na ball.", "points": 2, "variety": "PIDGIN"},
    ]
    found = check(candidate)  # q2 covers all three, q1 does not
    assert found["items_shape"].reason == "q1 needs example answers for 0, 1 and 2 points"


def test_an_empty_example_answer_fails(check):
    candidate = story()
    candidate["items"][0]["exemplars"][0]["answer"] = " "
    assert "q1 has an empty example answer" in check(candidate)["items_shape"].reason


def test_one_example_answer_must_be_in_nigerian_english_or_pidgin(check):
    candidate = story()
    for item in candidate["items"]:
        for exemplar in item["exemplars"]:
            exemplar["variety"] = "STANDARD"
    assert "Nigerian English or Pidgin" in check(candidate)["items_shape"].reason


# ---- plain text and ambiguous words


def test_digits_fail_plain_text(check):
    found = check(with_sentence(2, "Mama bought 3 rice, fish and ripe tomatoes."))
    assert "write numbers as words" in found["plain_text"].reason
    found = check(story(title="Ball 2"))
    assert "write numbers as words" in found["plain_text"].reason


def test_an_empty_sentence_among_real_ones_fails_plain_text(check):
    found = check(story(sentences=[*SENTENCES, "  "]))
    assert found["plain_text"].reason == "there are no sentences, or one is empty"


def test_a_token_with_no_letters_fails_plain_text(check):
    found = check(with_sentence(1, "The sun was hot — and the market was full."))
    assert "tokens with no letters: —" in found["plain_text"].reason


@pytest.mark.parametrize("ending", ["", ",", "…"])
def test_every_sentence_must_end_in_a_stop(check, ending):
    found = check(with_sentence(8, "They all went home with a smile" + ending))
    assert "every sentence must end with" in found["plain_text"].reason


def test_a_closing_quote_after_the_stop_is_fine(check):
    found = check(with_sentence(7, 'Mama laughed and said, "Ada is kind."'))
    assert "plain_text" not in failed(found)


def test_words_said_two_ways_fail(check):
    found = check(with_sentence(8, "They all read home with a smile."))
    assert "avoid words said two ways: read" in found["no_ambiguous_words"].reason


def test_the_unchanged_story_is_not_modified_by_the_checks(check):
    before = repr(STORY)
    check(story())
    assert repr(STORY) == before
