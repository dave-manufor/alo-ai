"""Step G3: build the passage artifact's tokens in code, with no LLM (PRD 4.5).

Tokens follow the bank passages (fixtures/contracts/passage.bank_p3_market_day.json):
one per whitespace-separated word with its punctuation attached, so joining the token
texts with spaces gives text_content back. clean_text is the clip store's word rule, a
name carries the IPA from the curated list, and word_clip_gcs_uri points into the shared
clip store (PRD 4.5 G5) through the clip_uri function the caller supplies.
"""

from collections.abc import Callable, Sequence

from spacy.language import Language

from .boundaries import analyse
from .names import NameList
from .text import clean_word

CONTENT_POS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV", "NUM"})
MAX_POINTS = 2

ClipUri = Callable[[str, str | None], str]  # (clean_text, name_ipa) -> gs:// URI


def build_tokens(
    sentences: Sequence[str], nlp: Language, names: NameList, clip_uri: ClipUri
) -> list[dict]:
    tokens: list[dict] = []
    for sentence_index, sentence in enumerate(sentences):
        for text, (boundary, pos) in zip(sentence.split(), analyse(sentence, nlp), strict=True):
            clean = clean_word(text)
            name = names.get(clean)
            ipa = name.ipa if name else None
            tokens.append(
                {
                    "token_index": len(tokens),
                    "sentence_index": sentence_index,
                    "text": text,
                    "clean_text": clean,
                    "is_content_word": pos in CONTENT_POS,
                    "syntactic_boundary_after": boundary,
                    "name_ipa": ipa,
                    "word_clip_gcs_uri": clip_uri(clean, ipa),
                }
            )
    return tokens


def text_content(sentences: Sequence[str]) -> str:
    return " ".join(" ".join(sentence.split()) for sentence in sentences)


def artifact_items(items: Sequence[dict]) -> list[dict]:
    """The Writer's items as the passage schema has them: max_points added, and the
    exemplars' `variety` (STANDARD, NIGERIAN_ENGLISH, PIDGIN) dropped."""
    return [
        {
            **{key: value for key, value in item.items() if key != "exemplars"},
            "max_points": MAX_POINTS,
            "exemplars": [
                {"answer": exemplar["answer"], "points": exemplar["points"]}
                for exemplar in item["exemplars"]
            ],
        }
        for item in items
    ]
