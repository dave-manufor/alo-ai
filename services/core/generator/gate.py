"""Step G4: the code checks of the generation gate (PRD 4.5), with no LLM.

The Critic (critic.py: items answerable, items not guessable) runs only when these
pass. Every check runs, so the failed ones can all go back to the Writer as
feedback in one retry. Each result is a name, a pass or fail, and a reason; the names are
the keys of the passage's generation.gate_results.

A story is a dict shaped like the passage schema (PRD 10.1):

    {"title": str, "sentences": [str], "propositions": [...], "items": [...]}

with each exemplar also carrying a `variety` (STANDARD, NIGERIAN_ENGLISH or PIDGIN).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import cached_property

from spacy.language import Language
from wordfreq import zipf_frequency

from . import blueprint, textlevel
from .names import Blocklist, NameList
from .text import HOMOGRAPHS, clean_word, words_of

CATEGORIES = frozenset(
    {"SETTING", "CHARACTER", "PROBLEM", "ACTION", "RESOLUTION", "MAIN_IDEA", "DETAIL"}
)
NAME_ENTITIES = frozenset({"PERSON", "GPE", "LOC", "ORG", "NORP", "FAC"})
LEMMA_POS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "NUM"})
LOCAL_VARIETIES = frozenset({"NIGERIAN_ENGLISH", "PIDGIN"})
TERMINAL_MARKS = (".", "!", "?")

NAME_ZIPF = 3.0  # [CAL] a title word rarer than this and not on the list may be a name
COPY_RATIO = 0.8  # [CAL] an inferential answer this alike to one sentence is a copy
COPY_OVERLAP = 0.6  # [CAL] ... or shares this much of its content words with one sentence
MIN_CONTAINED_WORDS = 4  # a sentence of fewer words inside an answer is a coincidence


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class Request:
    target_arl: int
    length_profile: str  # STANDARD | DEMO


@dataclass(frozen=True)
class Context:
    story: Mapping
    request: Request
    nlp: Language
    names: NameList
    blocklist: Blocklist

    @property
    def sentences(self) -> list[str]:
        return list(self.story["sentences"])

    @cached_property
    def words(self) -> list[str]:
        return words_of(self.sentences)

    @cached_property
    def rules(self) -> blueprint.LengthRules:
        return blueprint.rules_for(self.request.length_profile)

    @cached_property
    def features(self) -> textlevel.Features:
        return textlevel.features(self.sentences, self.names)

    def lemmas(self, text: str) -> set[str]:
        doc = self.nlp(text)
        return {t.lemma_.lower() for t in doc if t.pos_ in LEMMA_POS and not t.is_stop}


def run(
    story: Mapping, request: Request, nlp: Language, names: NameList, blocklist: Blocklist
) -> list[Check]:
    """All the code checks, in the order of the gate table. Raises ValueError for a
    request that is not a valid one. The story must already match the Writer's output
    schema (its fields are present and typed); a bad story then fails a check."""
    ctx = Context(story, request, nlp, names, blocklist)
    blueprint.rules_for(request.length_profile)
    blueprint.row_for(request.target_arl)
    if not ctx.words:
        return [Check("plain_text", False, "there are no sentences, or they have no words")]
    return [check(ctx) for check in CHECKS]


def passed(checks: Sequence[Check]) -> bool:
    return all(check.passed for check in checks)


def results(checks: Sequence[Check]) -> dict[str, bool]:
    return {check.name: check.passed for check in checks}


def feedback(checks: Sequence[Check]) -> str:
    """The failed checks, as the Writer's retry sees them."""
    return "\n".join(f"- {check.name}: {check.reason}" for check in checks if not check.passed)


def _check(name: str, problems: Sequence[str]) -> Check:
    return Check(name, not problems, "; ".join(problems))


# ---- blueprint, difficulty, safety, names


def blueprint_check(ctx: Context) -> Check:
    row = blueprint.row_for(ctx.request.target_arl)
    low, high = blueprint.word_range(ctx.request.target_arl, ctx.request.length_profile)
    found, problems = ctx.features, []
    if not low <= len(ctx.words) <= high:
        problems.append(f"{len(ctx.words)} words; this level needs {low} to {high}")
    if found.mean_sentence_length > row.max_mean_sentence:
        problems.append(
            f"sentences average {found.mean_sentence_length:.1f} words; "
            f"the limit is {row.max_mean_sentence:g}"
        )
    common = found.common_shares[blueprint.ROWS.index(row)]
    if common < row.zipf_share:
        problems.append(
            f"{common:.0%} of words are common (Zipf {row.zipf_threshold:g} or more); "
            f"{row.zipf_share:.0%} are needed"
        )
    if found.long_share > row.max_long_share:
        problems.append(
            f"{found.long_share:.1%} of words have 3 or more syllables; "
            f"the limit is {row.max_long_share:.0%}"
        )
    return _check("blueprint", problems)


def difficulty_check(ctx: Context) -> Check:
    estimate = textlevel.estimate_arl(ctx.features)
    target, tolerance = ctx.request.target_arl, blueprint.DIFFICULTY_TOLERANCE
    problems = []
    if abs(estimate - target) > tolerance:
        direction = "too hard" if estimate > target else "too easy"
        problems.append(f"estimated level {estimate} is {direction} for {target} (+/- {tolerance})")
    return _check("difficulty", problems)


def _story_texts(story: Mapping) -> list[str]:
    texts = [story["title"], *story["sentences"]]
    for proposition in story["propositions"]:
        texts.append(proposition["description"])
    for item in story["items"]:
        texts += [item["prompt_text"], *item["rubric"].values()]
        texts += [exemplar["answer"] for exemplar in item["exemplars"]]
    return texts


def safety_check(ctx: Context) -> Check:
    found: list[str] = []
    for text in _story_texts(ctx.story):
        found += [word for word in ctx.blocklist.hits(text) if word not in found]
    return _check("safety", [f"uses {', '.join(found)}"] if found else [])


def _unlisted_names(ctx: Context, text: str) -> list[str]:
    """Proper nouns of a sentence or question that are not on the list: a word spaCy tags
    PROPN or puts in a person, place or group entity, or any capital after the first word."""
    found: list[str] = []
    for token in ctx.nlp(text):
        word = clean_word(token.text)
        capital = token.text[:1].isupper()
        named = token.pos_ == "PROPN" or (token.ent_type_ in NAME_ENTITIES and capital)
        mid_sentence = capital and not token.is_sent_start and token.text != "I"
        if word and (named or mid_sentence) and word not in ctx.names and word not in found:
            found.append(token.text)
    return found


def _unlisted_title_names(ctx: Context, title: str) -> list[str]:
    """A title is Title Case, so a capital means nothing: only a rare word that is not on
    the list could be a name (common ones, like Blue or Kite, are not)."""
    return [
        word
        for word in title.split()
        if clean_word(word) not in ctx.names
        and clean_word(word)
        and zipf_frequency(clean_word(word), "en") < NAME_ZIPF
    ]


def names_check(ctx: Context) -> Check:
    found: list[str] = []
    found += _unlisted_title_names(ctx, ctx.story["title"])
    for text in [*ctx.sentences, *(item["prompt_text"] for item in ctx.story["items"])]:
        found += [w for w in _unlisted_names(ctx, text) if w not in found]
    return _check("names", [f"names not on the list: {', '.join(found)}"] if found else [])


# ---- propositions


def propositions_check(ctx: Context) -> Check:
    propositions, rules, sentences = ctx.story["propositions"], ctx.rules, ctx.sentences
    low, high = rules.propositions
    problems = []
    if not low <= len(propositions) <= high:
        problems.append(f"{len(propositions)} propositions; {low} to {high} are needed")
    core = sum(1 for p in propositions if p.get("weight") == 2)
    if core < rules.core_min:
        problems.append(f"{core} core propositions (weight 2); at least {rules.core_min}")
    ids = [p.get("id") for p in propositions]
    if len(set(ids)) != len(ids) or not all(ids):
        problems.append("proposition ids must be present and different")
    for proposition in propositions:
        label = proposition.get("id") or "a proposition"
        index = proposition.get("sentence_index")
        if proposition.get("category") not in CATEGORIES:
            problems.append(f"{label} has category {proposition.get('category')!r}")
        elif proposition.get("weight") not in (1, 2):
            problems.append(f"{label} has weight {proposition.get('weight')!r}")
        elif not isinstance(index, int) or not 0 <= index < len(sentences):
            problems.append(f"{label} cites sentence {index!r}, which does not exist")
        elif not ctx.lemmas(proposition["description"]) & ctx.lemmas(sentences[index]):
            problems.append(f"{label} shares no content word with its sentence {index}")
    return _check("propositions", problems)


# ---- the inferential item


def _normal(text: str) -> str:
    return " ".join(w for w in (clean_word(t) for t in text.split()) if w)


def _copy_of(answer: str, sentence: str, stop_words: frozenset[str]) -> str | None:
    """Why the answer is a copy of the sentence, or None."""
    if not answer or not sentence:
        return None
    if answer in sentence or (len(sentence.split()) >= MIN_CONTAINED_WORDS and sentence in answer):
        return "is contained in"
    if SequenceMatcher(None, answer, sentence).ratio() >= COPY_RATIO:
        return "is nearly the same as"
    a = {w for w in answer.split() if w not in stop_words}
    s = {w for w in sentence.split() if w not in stop_words}
    if a and s and len(a & s) / len(a | s) >= COPY_OVERLAP:
        return "shares almost all its content words with"
    return None


def inference_check(ctx: Context) -> Check:
    items = [i for i in ctx.story["items"] if i["type"] == "INFERENTIAL"]
    if not items:
        return Check("inference_is_real", False, "there is no inferential item")
    stop_words = frozenset(ctx.nlp.Defaults.stop_words)
    sentences = [_normal(s) for s in ctx.sentences]
    problems = []
    for item in items:
        answers = [_normal(e["answer"]) for e in item["exemplars"] if e["points"] == 2]
        if not answers:
            problems.append(f"{item['item_id']} has no 2-point answer")
        for answer in answers:
            for number, sentence in enumerate(sentences):
                how = _copy_of(answer, sentence, stop_words)
                if how:
                    problems.append(
                        f"{item['item_id']}: the 2-point answer {how} sentence {number}; "
                        "the answer must link two sentences"
                    )
                    break
    return _check("inference_is_real", problems)


# ---- items, plain text, ambiguous words


def items_check(ctx: Context) -> Check:
    items, rules, sentences = ctx.story["items"], ctx.rules, ctx.sentences
    problems = []
    kinds = [item["type"] for item in items]
    for kind, wanted in (
        ("LITERAL", rules.literal_items),
        ("INFERENTIAL", rules.inferential_items),
    ):
        if kinds.count(kind) != wanted:
            problems.append(f"{kinds.count(kind)} {kind} items; {wanted} are needed")
    if len(kinds) != rules.literal_items + rules.inferential_items:
        problems.append(
            f"{len(kinds)} items in all; {rules.literal_items + rules.inferential_items}"
        )
    if [item["order"] for item in items] != list(range(1, len(items) + 1)):
        problems.append("item order must be 1, 2, 3 in turn")
    ids = [item["item_id"] for item in items]
    if len(set(ids)) != len(ids) or not all(ids):
        problems.append("item ids must be present and different")
    for item in items:
        label = item["item_id"] or "an item"
        if not item["prompt_text"].strip():
            problems.append(f"{label} has no question")
        if not 0 <= item["target_sentence_index"] < len(sentences):
            problems.append(f"{label} targets sentence {item['target_sentence_index']}")
        if set(item["rubric"]) != {"2", "1", "0"} or not all(item["rubric"].values()):
            problems.append(f"{label} needs a rubric for 2, 1 and 0 points")
        if not all(e["answer"].strip() for e in item["exemplars"]):
            problems.append(f"{label} has an empty example answer")
        if {e["points"] for e in item["exemplars"]} != {0, 1, 2}:
            problems.append(f"{label} needs example answers for 0, 1 and 2 points")
    varieties = {e.get("variety") for item in items for e in item["exemplars"]}
    if items and not varieties & LOCAL_VARIETIES:
        problems.append("no example answer in Nigerian English or Pidgin")
    return _check("items_shape", problems)


def plain_text_check(ctx: Context) -> Check:
    problems = []
    sentences = ctx.sentences
    if not sentences or not all(s.strip() for s in sentences):
        return Check("plain_text", False, "there are no sentences, or one is empty")
    if any(ch.isdigit() for text in [ctx.story["title"], *sentences] for ch in text):
        problems.append("write numbers as words; the story has digits")
    bare = [t for s in sentences for t in s.split() if not clean_word(t)]
    if bare:
        problems.append(f"tokens with no letters: {' '.join(bare)}")
    open_ended = [s for s in sentences if not s.rstrip("\"'”’) ").endswith(TERMINAL_MARKS)]
    if open_ended:
        problems.append("every sentence must end with . ! or ?")
    return _check("plain_text", problems)


def ambiguous_words_check(ctx: Context) -> Check:
    found = sorted(set(ctx.words) & HOMOGRAPHS)
    reason = [f"avoid words said two ways: {', '.join(found)}"] if found else []
    return _check("no_ambiguous_words", reason)


CHECKS: tuple[Callable[[Context], Check], ...] = (
    blueprint_check,
    difficulty_check,
    safety_check,
    names_check,
    propositions_check,
    inference_check,
    items_check,
    plain_text_check,
    ambiguous_words_check,
)
