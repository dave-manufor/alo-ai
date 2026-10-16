"""Fill the clip store with "That word is X." clips (SDD 6, step 4).

List the distinct words, find which clips already exist, make only the missing
ones (at most 16 requests at once) and write each only if it is still absent.
The text-to-speech call is passed in, so tests and AI_MODE=fixtures never reach
Cloud TTS.
"""

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .keys import clean_word, word_key
from .store import ClipStore

MAX_CONCURRENT_REQUESTS = 16

# One silent MPEG-1 Layer III frame (128 kbps, 44.1 kHz). A stand-in for local
# runs; generated here so no audio file is committed.
_SILENT_FRAME = b"\xff\xfb\x90\x04" + b"\x00" * 413


def silent_clip(text: str) -> bytes:
    return _SILENT_FRAME


@dataclass(frozen=True)
class WordToSeed:
    text: str
    ipa: str | None = None


@dataclass
class SeedReport:
    existing: list[str] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    lost_race: list[str] = field(default_factory=list)  # another writer got there first
    failed: dict[str, str] = field(default_factory=dict)


def words_from_tokens(tokens: Iterable[dict]) -> list[WordToSeed]:
    """The words in a passage artifact's tokens (clean_text, plus name_ipa for names)."""
    return [
        WordToSeed(token.get("clean_text") or token["text"], token.get("name_ipa"))
        for token in tokens
        if clean_word(token.get("clean_text") or token["text"])
    ]


def seed_words(
    words: Iterable[WordToSeed],
    store: ClipStore,
    synthesize: Callable[[str, str | None], bytes],
) -> SeedReport:
    """`synthesize(text, ipa)` returns the MP3 for "That word is {text}."."""
    report = SeedReport()
    pending: dict[str, WordToSeed] = {}
    for word in words:
        try:
            key = word_key(word.text, word.ipa)
        except ValueError as error:
            report.failed[word.text] = str(error)
            continue
        if key in pending or key in report.existing:
            continue
        if store.has_word(key):
            report.existing.append(key)
        else:
            pending[key] = word

    def make(item: tuple[str, WordToSeed]) -> tuple[str, bytes | Exception]:
        key, word = item
        try:
            return key, synthesize(clean_word(word.text), word.ipa)
        except Exception as error:  # noqa: BLE001 - one bad word must not stop the run
            return key, error

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as pool:
        for key, result in pool.map(make, pending.items()):
            if isinstance(result, Exception):
                report.failed[pending[key].text] = str(result)
            elif store.put_word(key, result):
                report.written.append(key)
            else:
                report.lost_race.append(key)
    return report
