"""Syntactic boundaries for prosody phrasing (PRD 4.5 G3, 5.5).

After each token of a sentence: NONE, PHRASE, CLAUSE, or TERMINAL for the last one. The
Reading Scorer reads these from the stored passage and never parses (PRD 5.5), so the
rule is small, deterministic and tested. It uses punctuation plus a spaCy dependency parse
(en_core_web_sm):

- the last token of a sentence is TERMINAL;
- before a token that starts a new clause (a subordinator, a relative or wh- word, a
  subject of a subordinate or coordinated clause, or "and"/"but"/"or" joining two
  verbs) the boundary is CLAUSE, with or without a comma;
- after a comma, semicolon, colon or dash that does not start a clause it is PHRASE;
- after a subject of 3+ words, before its verb, it is PHRASE ("Ada and Mama | went",
  "The old man with the goat | ran");
- after a fronted adverbial of 2+ words, before the rest of the clause, it is PHRASE
  ("Every morning | the farmer feeds his goats");
- with no punctuation, a prepositional phrase of 3+ words that follows 3+ words since the
  last boundary starts after a PHRASE boundary ("The boy ran | to the old market"), unless
  the phrase is inside the subject ("The old man with the goat" stays whole);
- anything else is NONE.

A child pauses at these breaks, and the Scorer counts a pause as phrasing only after one,
so a missed break makes a natural pause count against them.
"""

from spacy.language import Language
from spacy.tokens import Doc, Token

from .text import split_edges

CLAUSE_PUNCT = ",;:—–"
CLAUSE_DEPS = frozenset({"advcl", "ccomp", "relcl", "conj"})
VERBAL = frozenset({"VERB", "AUX"})
WH_TAGS = frozenset({"WDT", "WP", "WP$", "WRB"})
MIN_PHRASE = 3  # words in the phrase, and words since the last boundary
MIN_SUBJECT = 3  # words in a subject that is followed by a break before its verb
MIN_FRONTED = 2  # words in a fronted adverbial that is followed by a break
SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass"})
FRONTED_DEPS = frozenset({"npadvmod", "advmod", "prep", "obl"})


def boundaries(sentence: str, nlp: Language) -> list[str]:
    """One label per whitespace token of the sentence."""
    return [label for label, _ in analyse(sentence, nlp)]


def analyse(sentence: str, nlp: Language) -> list[tuple[str, str]]:
    """(boundary label, part of speech) for each whitespace token of the sentence. One
    parse gives both, so the artifact builder and the gate read the same analysis."""
    tokens = sentence.split()
    if not tokens:
        return []
    pieces: list[str] = []
    spans: list[tuple[int | None, str]] = []  # per token: index of its word in pieces, trailer
    for token in tokens:
        lead, core, trail = split_edges(token)
        if not core:  # a lone dash or quote: the parser sees it; it marks the word before
            pieces.append(token)
            spans.append((None, token))
            _mark_previous_word(spans, token)
            continue
        pieces.extend(list(lead))
        spans.append((len(pieces), trail))
        pieces.append(core)
        pieces.extend(list(trail))
    doc = _parse(pieces, nlp)

    labels: list[str] = []
    since = 0  # words since the last boundary
    for position, (index, trail) in enumerate(spans):
        if index is None:  # standalone punctuation: carried by the previous word's trailer
            continue
        since += 1
        following = _next_word(spans, position, doc)
        labels.append(_label(doc[index], following, trail, since, last=following is None))
        if labels[-1] != "NONE":
            since = 0
    return _align(spans, labels, doc)


def _mark_previous_word(spans: list[tuple[int | None, str]], marks: str) -> None:
    for position in range(len(spans) - 2, -1, -1):
        index, trail = spans[position]
        if index is not None:
            spans[position] = (index, trail + marks)
            return


def _parse(pieces: list[str], nlp: Language) -> Doc:
    doc = Doc(nlp.vocab, words=pieces)
    for _, component in nlp.pipeline:
        doc = component(doc)
    return doc


def _next_word(spans: list[tuple[int | None, str]], position: int, doc: Doc) -> Token | None:
    for index, _ in spans[position + 1 :]:
        if index is not None:
            return doc[index]
    return None


def _label(current: Token, following: Token | None, trail: str, since: int, *, last: bool) -> str:
    if last:
        return "TERMINAL"
    if _introduces_clause(current):
        return "NONE"  # the boundary came before "and", "because", "who", ...
    punctuated = any(mark in CLAUSE_PUNCT for mark in trail)
    if _starts_clause(following):
        return "CLAUSE"
    if punctuated:
        return "CLAUSE" if _ends_subordinate_clause(current) else "PHRASE"
    if _ends_long_subject(current) or _ends_fronted_adverbial(current):
        return "PHRASE"
    if (
        following.dep_ == "prep"
        and since >= MIN_PHRASE
        and _size(following) >= MIN_PHRASE
        and not _in_subject(following)
    ):
        return "PHRASE"
    return "NONE"


def _size(token: Token) -> int:
    return sum(1 for t in token.subtree if not t.is_punct)


def _last_word(token: Token) -> int:
    return max(t.i for t in token.subtree if not t.is_punct)


def _ends_long_subject(token: Token) -> bool:
    """Is this the last word of a subject of 3+ words that comes before its verb?"""
    for candidate in (token, *token.ancestors):
        if candidate.dep_ in SUBJECT_DEPS:
            return (
                _last_word(candidate) == token.i
                and _size(candidate) >= MIN_SUBJECT
                and candidate.head.pos_ in VERBAL
                and candidate.head.i > token.i
            )
    return False


def _ends_fronted_adverbial(token: Token) -> bool:
    """Is this the last word of a 2+ word modifier that opens the sentence ("Every
    morning", "After the rain") and hangs off a verb that comes later?"""
    for candidate in (token, *token.ancestors):
        if candidate.dep_ in FRONTED_DEPS and candidate.left_edge.i == 0:
            return (
                _last_word(candidate) == token.i
                and _size(candidate) >= MIN_FRONTED
                and candidate.head.i > token.i
            )
    return False


def _in_subject(token: Token) -> bool:
    return any(candidate.dep_ in SUBJECT_DEPS for candidate in (token, *token.ancestors))


def _introduces_clause(token: Token) -> bool:
    return token.dep_ == "mark" or token.tag_ in WH_TAGS or _joins_verbs(token)


def _joins_verbs(token: Token) -> bool:
    """ "and", "but" or "or" between two verbs: "Ada ran and Tunde laughed"."""
    return (
        token.dep_ == "cc"
        and token.head.pos_ in VERBAL
        and any(child.dep_ == "conj" and child.pos_ in VERBAL for child in token.head.children)
    )


def _starts_clause(token: Token) -> bool:
    """Does a new clause begin at this token (its subject, or its subordinator)?"""
    if _introduces_clause(token):
        return True
    for candidate in (token, *token.ancestors):
        if candidate.left_edge.i != token.i:
            return False  # token is no longer the first word of what we are climbing
        if candidate.dep_ in {"nsubj", "nsubjpass", "expl"}:
            head = candidate.head
            return head.dep_ in CLAUSE_DEPS and head.pos_ in VERBAL and head.i > token.i
    return False


def _ends_subordinate_clause(token: Token) -> bool:
    """Is this the last word of an adverbial, complement or relative clause?"""
    for candidate in (token, *token.ancestors):
        if candidate.dep_ in {"advcl", "ccomp", "relcl"}:
            last = max(t.i for t in candidate.subtree if not t.is_punct)
            if last == token.i:
                return True
    return False


def _align(
    spans: list[tuple[int | None, str]], labels: list[str], doc: Doc
) -> list[tuple[str, str]]:
    """Standalone punctuation tokens get NONE, so there is one entry per whitespace token."""
    iterator = iter(labels)
    return [
        ("NONE", "PUNCT") if index is None else (next(iterator), doc[index].pos_)
        for index, _ in spans
    ]
