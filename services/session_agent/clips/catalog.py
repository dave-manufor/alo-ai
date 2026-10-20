"""Where each clip the machine plays lives in the shared clip store (PRD 4.4, 4.5 G5).

The machine names clips by role ("retell_prompt", "question:1", "listening_story")
and words by token index. The web app caches clips by the same ids before the
session starts (the clip_list message), so ids and URLs come from one place:

    prompts           {voice}/{tts}/{clip_id}.mp3
    questions         {voice}/{tts}/passages/{passage_id}/question_{n}.mp3
    listening story   {voice}/{tts}/passages/{listening_passage_id}/story.mp3
    listening items   {voice}/{tts}/passages/{listening_passage_id}/item_{n}.mp3
    words             {voice}/{tts}/words/{word_key}.mp3, clip id "word_{word_key}"

Each clip also carries the words it says (prompts.py, the passage items' prompt_text,
"That word is X."), which the web app shows in the speech bubble. The listening story
has no text: the child must hear it, not read it.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .keys import clean_word, word_key
from .prompts import PROMPT_TEXTS, WORD_CLIP_TEXT
from .store import ClipStore

# Every prompt the machine can say (machine/step.py). The web app caches all of them.
PROMPTS = (
    "interest_prompt",
    "interest_fallback",
    "mic_check_prompt",
    "mic_closer",
    "mic_softer",
    "story_almost_ready",
    "retell_prompt",
    "anything_else",
    "take_your_time",
    "lets_go_next",
    "kind_end",
    "listening_retell_prompt",
    "close_praise",
    "stop_praise",
    "wait_for_internet",
)


@dataclass(frozen=True)
class ClipCatalog:
    store: ClipStore
    base_url: str  # e.g. https://storage.googleapis.com/{clips bucket}

    def word_clip_id(self, token: dict) -> str:
        return f"word_{self._word_key(token)}"

    def object_name(
        self,
        clip_id: str,
        *,
        passage_id: str | None = None,
        listening_passage_id: str | None = None,
    ) -> str:
        """The clip store object for a clip id. Raises ValueError for an unknown id."""
        prefix = f"{self.store.voice_profile_id}/{self.store.tts_version}"
        role, _, number = clip_id.partition(":")
        if clip_id.startswith("word_"):
            return self.store.word_clip_name(clip_id.removeprefix("word_"))
        if role == "question" and number.isdigit() and passage_id:
            return self.store.passage_clip_name(passage_id, f"question_{number}")
        if role == "listening_item" and number.isdigit() and listening_passage_id:
            return self.store.passage_clip_name(listening_passage_id, f"item_{number}")
        if clip_id == "listening_story" and listening_passage_id:
            return self.store.passage_clip_name(listening_passage_id, "story")
        if clip_id in PROMPTS:
            return f"{prefix}/{clip_id}.mp3"
        raise ValueError(f"no clip store object for {clip_id!r}")

    def url(self, clip_id: str, **passages: str | None) -> str:
        return f"{self.base_url.rstrip('/')}/{self.object_name(clip_id, **passages)}"

    def text(
        self, clip_id: str, read: dict | None = None, listening: dict | None = None
    ) -> str | None:
        """What the clip says, or None for the listening story. Raises ValueError for an
        id it can't place, like object_name."""
        role, _, number = clip_id.partition(":")
        if clip_id in PROMPT_TEXTS:
            return PROMPT_TEXTS[clip_id]
        if clip_id == "listening_story" and listening is not None:
            return None
        if role == "question" and number.isdigit() and read is not None:
            return read["items"][int(number)]["prompt_text"]
        if role == "listening_item" and number.isdigit() and listening is not None:
            return listening["items"][int(number)]["prompt_text"]
        if clip_id.startswith("word_") and read is not None:
            for token in _words(read["tokens"]):
                if self.word_clip_id(token) == clip_id:
                    return WORD_CLIP_TEXT.format(word=_display_word(token))
        raise ValueError(f"no text for clip {clip_id!r}")

    def session_clips(
        self, read: dict, listening: dict | None, n_questions: int, n_listening_items: int
    ) -> list[tuple[str, str, str | None]]:
        """(clip_id, url, text) for every clip a session on these passages can play."""
        ids = {"passage_id": read["passage_id"]}
        if listening is not None:
            ids["listening_passage_id"] = listening["passage_id"]
        clip_ids = [*PROMPTS, *(f"question:{n}" for n in range(n_questions))]
        if listening is not None:
            clip_ids += ["listening_story"]
            clip_ids += [f"listening_item:{n}" for n in range(n_listening_items)]
        clip_ids += _unique(self.word_clip_id(t) for t in _words(read["tokens"]))
        return [
            (clip_id, self.url(clip_id, **ids), self.text(clip_id, read, listening))
            for clip_id in clip_ids
        ]

    def _word_key(self, token: dict) -> str:
        return word_key(token.get("clean_text") or token["text"], token.get("name_ipa"))


def _words(tokens: Sequence[dict]) -> list[dict]:
    return [t for t in tokens if clean_word(t.get("clean_text") or t["text"])]


def _unique(items) -> list[str]:
    return list(dict.fromkeys(items))


def _display_word(token: dict) -> str:
    """The word without the punctuation around it ("market." -> "market"). Names keep
    their capital; other words are lowercased, so "It" at the start of a sentence reads
    "That word is it."."""
    word = token["text"].strip(".,;:!?\"'“”‘’()[]-—")
    return word if token.get("name_ipa") else word.lower()
