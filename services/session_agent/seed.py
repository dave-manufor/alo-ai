"""Seed a cloud's stores with the clips and the bank passages the Session Agent needs
(SDD 6, PRD 4.5).

    python -m services.session_agent.seed [--bank-dir DIR] [--only clips|passages] [--dry-run]

It makes every clip a session can play, then writes the passages:

    fixed prompts      the lines in clips/prompts.py (Auntie Kemi's fixed prompts)
    questions          each READ passage's item prompts
    listening          each LISTEN passage's story and item prompts
    words              "That word is X." for every word of every READ passage

Clips are written only if absent, so running it again changes nothing and an existing clip is
never replaced: a new voice or new voice settings mean a new VOICE_PROFILE_ID or TTS_VERSION,
which is a new set of clips. Clips come before passages, so a passage never names a clip that
does not exist. A stored passage names its clips by this cloud's URIs (az:// or gs://, this
voice's folder), not the ones in fixtures/contracts, which name the Google dev bucket.

Voice: with AI_MODE=live and CLOUD=azure the clips are spoken by the Azure voice in TTS_VOICE
(an Azure AI Speech call per clip). With AI_MODE=fixtures they are silent placeholders, only
for a laptop (a hosted service refuses fixtures). There is no Google voice here: Cloud
Text-to-Speech clips are not built.
"""

import argparse
import copy
import json
import logging
import os
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from jsonschema import ValidationError

import aloai_contracts
import aloai_env
from aloai_azure import synthesize as azure_synthesize
from aloai_blobs import SCHEME_OF, open_blobs
from aloai_store import Store, open_store

from . import config
from .cloud import BlobBucket
from .clips.azure import line_synthesizer, word_synthesizer
from .clips.catalog import PROMPTS
from .clips.keys import clean_word, word_key
from .clips.prompts import PROMPT_TEXTS
from .clips.seed import SeedReport, WordToSeed, seed_words, silent_clip, words_from_tokens
from .clips.store import ClipStore
from .passages import PassagePair

log = logging.getLogger(__name__)

MAX_CONCURRENT_REQUESTS = 16
DEFAULT_BANK_DIR = "fixtures/contracts"

LineSynthesizer = Callable[[str], bytes]
WordSynthesizer = Callable[[str, str | None], bytes]


@dataclass(frozen=True)
class Line:
    name: str  # the clip store object
    text: str  # what it says


def _asked(passage: dict) -> list[dict]:
    """Items in the order they are asked (clips/catalog.py): question 0 has the lowest order."""
    return sorted(passage["items"], key=lambda item: item["order"])


def prompt_lines(store: ClipStore) -> list[Line]:
    return [Line(store.prompt_clip_name(clip_id), PROMPT_TEXTS[clip_id]) for clip_id in PROMPTS]


def passage_lines(passage: dict, store: ClipStore) -> list[Line]:
    """The clips of a passage: a READ passage's questions; a LISTEN passage's story, which
    the child hears and does not read, and its item prompts."""
    passage_id = passage["passage_id"]
    listening = passage["mode"] == "LISTEN"
    kind = "item" if listening else "question"
    lines = [
        Line(store.passage_clip_name(passage_id, f"{kind}_{n}"), item["prompt_text"])
        for n, item in enumerate(_asked(passage))
    ]
    if listening:
        story = Line(store.passage_clip_name(passage_id, "story"), passage["text_content"])
        lines.insert(0, story)
    return lines


def seed_lines(lines: Iterable[Line], store: ClipStore, synthesize: LineSynthesizer) -> SeedReport:
    """Make the lines whose clip is missing, at most 16 requests at once, and write each only
    if it is still absent. The report is keyed by object name."""
    report = SeedReport()
    pending: dict[str, Line] = {}
    for line in lines:
        if line.name in pending or line.name in report.existing:
            continue
        if store.bucket.exists(line.name):
            report.existing.append(line.name)
        else:
            pending[line.name] = line

    def make(line: Line) -> tuple[str, bytes | Exception]:
        try:
            return line.name, synthesize(line.text)
        except Exception as error:  # noqa: BLE001 - one bad line must not stop the run
            return line.name, error

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as pool:
        for name, result in pool.map(make, pending.values()):
            if isinstance(result, Exception):
                report.failed[name] = str(result)
            elif store.bucket.upload_if_absent(name, result, "audio/mpeg"):
                report.written.append(name)
            else:
                report.lost_race.append(name)
    return report


def with_store_uris(passage: dict, store: ClipStore) -> dict:
    """The passage with its clip URIs naming this store: each word's clip, a LISTEN passage's
    story, and each item's prompt. Checked against the passage schema."""
    doc = copy.deepcopy(passage)
    passage_id = doc["passage_id"]
    for token in doc["tokens"]:
        word = token.get("clean_text") or token["text"]
        if clean_word(word):
            key = word_key(word, token.get("name_ipa"))
            token["word_clip_gcs_uri"] = store.uri(store.word_clip_name(key))
    listening = doc["mode"] == "LISTEN"
    if listening:
        doc["audio_gcs_uri"] = store.uri(store.passage_clip_name(passage_id, "story"))
    kind = "item" if listening else "question"
    numbers = {item["item_id"]: n for n, item in enumerate(_asked(doc))}
    for item in doc["items"]:
        name = store.passage_clip_name(passage_id, f"{kind}_{numbers[item['item_id']]}")
        item["prompt_audio_gcs_uri"] = store.uri(name)
    aloai_contracts.validator("passage.schema.json").validate(doc)
    return doc


def load_bank(folder: Path) -> list[dict]:
    """Every passage.*.json in the folder."""
    return [json.loads(path.read_text()) for path in sorted(folder.glob("passage.*.json"))]


def _say(out: TextIO, text: str) -> None:
    print(text, file=out)


def _summary(out: TextIO, what: str, report: SeedReport) -> bool:
    _say(
        out,
        f"{what}: {len(report.written)} made, {len(report.existing)} already there"
        + (f", {len(report.lost_race)} made by someone else first" if report.lost_race else "")
        + (f", {len(report.failed)} FAILED" if report.failed else ""),
    )
    for name, reason in report.failed.items():
        _say(out, f"  failed {name}: {reason}")
    return not report.failed


def run(
    *,
    bank: Sequence[dict],
    store: ClipStore,
    docs: Store,
    line: LineSynthesizer,
    word: WordSynthesizer,
    only: str | None = None,
    dry_run: bool = False,
    out: TextIO | None = None,
) -> bool:
    """Seed the clips, then the passages. True if nothing failed."""
    out = sys.stdout if out is None else out
    ok = True
    if only != "passages":
        lines = prompt_lines(store)
        for passage in bank:
            lines += passage_lines(passage, store)
        words = [w for p in bank if p["mode"] == "READ" for w in words_from_tokens(p["tokens"])]
        if dry_run:
            missing_lines = {line_.name for line_ in lines if not store.bucket.exists(line_.name)}
            missing_words = {
                key for key in map(_word_key, words) if key and not store.has_word(key)
            }
            _say(
                out,
                f"would make {len(missing_lines)} of {len({x.name for x in lines})} lines "
                f"and {len(missing_words)} words",
            )
        else:
            ok &= _summary(out, "lines", seed_lines(lines, store, line))
            ok &= _summary(out, "words", seed_words(words, store, word))
    if only != "clips":
        if dry_run:
            _say(out, f"would write {len(bank)} passages")
        else:
            failures = []
            for passage in bank:
                try:
                    docs.set(f"passages/{passage['passage_id']}", with_store_uris(passage, store))
                except (ValueError, ValidationError) as error:
                    failures.append(f"{passage['passage_id']}: {error}")
                    ok = False
            _say(out, f"passages: {len(bank) - len(failures)} written, {len(failures)} FAILED")
            for failure in failures:
                _say(out, f"  failed {failure}")
    return ok


def _word_key(word: WordToSeed) -> str | None:
    """The clip key of a word, or None when it has none (a homograph with no IPA): seed_words
    reports such a word as failed."""
    try:
        return word_key(word.text, word.ipa)
    except ValueError:
        return None


def _synthesizers(
    cfg: config.Config, shared: aloai_env.Config, env: Mapping[str, str]
) -> tuple[LineSynthesizer, WordSynthesizer]:
    if cfg.ai_mode == "fixtures":
        return silent_clip, lambda text, ipa: silent_clip(text)
    if shared.cloud != "azure":
        raise aloai_env.ConfigError(
            "no Google voice is built for the clips: use CLOUD=azure, or AI_MODE=fixtures for silent ones"
        )
    voice = env.get("TTS_VOICE", "")
    if not voice:
        raise aloai_env.ConfigError("TTS_VOICE must name an Azure voice, e.g. en-US-JennyNeural")
    locale = "-".join(voice.split("-")[:2])

    def ssml_to_mp3(ssml: str) -> bytes:
        return azure_synthesize(shared, ssml)

    return (
        line_synthesizer(ssml_to_mp3, voice=voice, locale=locale),
        word_synthesizer(ssml_to_mp3, voice=voice, locale=locale),
    )


def story_clip_maker(
    cfg: config.Config,
    shared: aloai_env.Config,
    env: Mapping[str, str],
    store: ClipStore,
) -> Callable[[PassagePair], None] | None:
    """What a session uses to make the "That word is X." clips of a story the Passage
    Generator wrote (4.5 G5): only the words the shared store lacks are made, and each is
    written only if still absent. None when this build has no voice to make them with
    (fixtures, no Azure voice named, or another cloud): the story's words the store lacks are
    then `missing` when told, as before."""
    if cfg.ai_mode != "live" or shared.cloud != "azure" or not env.get("TTS_VOICE"):
        return None
    _, word = _synthesizers(cfg, shared, env)

    def make(pair: PassagePair) -> None:
        report = seed_words(words_from_tokens(pair.read["tokens"]), store, word)
        log.info(
            "story clips: %d made, %d already there, %d failed",
            len(report.written),
            len(report.existing),
            len(report.failed),
        )

    return make


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the clips and the bank passages.")
    parser.add_argument("--bank-dir", default=DEFAULT_BANK_DIR, help="folder of passage.*.json")
    parser.add_argument("--only", choices=("clips", "passages"))
    parser.add_argument("--dry-run", action="store_true", help="say what would be made")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    try:
        cfg = config.load(env)
        settings = config.worker_settings(env)
        shared = aloai_env.load(env, receives_pushes=False)
        line, word = _synthesizers(cfg, shared, env)
    except (config.ConfigError, aloai_env.ConfigError) as error:
        print(f"refusing to seed: {error}", file=sys.stderr)
        return 1
    store = ClipStore(
        BlobBucket(open_blobs(shared), settings.cloud, settings.clips_bucket),
        settings.clips_bucket,
        settings.voice_profile_id,
        settings.tts_version,
        SCHEME_OF[settings.cloud],
    )
    bank = load_bank(Path(args.bank_dir))
    if not bank:
        print(f"refusing to seed: no passage.*.json in {args.bank_dir}", file=sys.stderr)
        return 1
    ok = run(
        bank=bank,
        store=store,
        docs=open_store(shared),
        line=line,
        word=word,
        only=args.only,
        dry_run=args.dry_run,
    )
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
