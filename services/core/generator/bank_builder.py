"""Build a bank passage fixture from a story, offline and with no LLM (PRD 4.5, 10.1).

A spec is the story as a person wrote it:

    {"passage_id", "title", "mode": "READ" | "LISTEN", "arl_level", "genre", "topic_tags",
     "length_profile": "STANDARD", "sentences": [...], "propositions": [...],
     "items": [{"type", "target_sentence_index", "prompt_text", "rubric", "exemplars"}],
     "paired_listening_passage_id": "..."}        (READ only)

`build` makes the passage the schema wants, with the tokens, boundaries and clip URIs the
generator uses for a generated story. `check` runs the generator's code gate, so a bank
passage meets the same blueprint (a LISTEN passage gets the checks that apply to it). The
clip URIs are the Google ones, like the other bank fixtures; the seed job rewrites them for
the cloud it runs on.

    python -m services.core.generator.bank_builder spec.json [spec.json ...] --out fixtures/contracts
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from spacy.language import Language

from . import artifact, clips, data, gate
from .names import Blocklist, NameList

SCHEMA_VERSION = 4  # schemas/passage.schema.json
BUCKET = "aloai-dev-clips"
VOICE_PROFILE = "vp_google_v1"
TTS_VERSION = "v1"
LICENCE = "CC0-1.0 (written for Alo.ai fixtures)"
LISTEN_WORDS = (80, 120)  # PRD 4.5: a pre-written listening story


def with_ids(spec: Mapping) -> dict:
    """The spec with each item's id and order added, as the Writer's story has them."""
    items = [
        {**item, "item_id": f"{spec['passage_id']}_q{order}", "order": order}
        for order, item in enumerate(spec["items"], start=1)
    ]
    return {**spec, "items": items}


def build(spec: Mapping, nlp: Language, names: NameList) -> dict:
    spec = with_ids(spec)
    sentences = spec["sentences"]
    passage_id = spec["passage_id"]
    tokens = artifact.build_tokens(
        sentences, nlp, names, clips.word_clip_uri(BUCKET, VOICE_PROFILE, TTS_VERSION)
    )
    items = spec["items"]
    passage = {
        "schema_version": SCHEMA_VERSION,
        "passage_id": passage_id,
        "title": spec["title"],
        "mode": spec["mode"],
        "source": "BANK",
        "licence": LICENCE,
        "topic_tags": list(spec["topic_tags"]),
        "genre": spec["genre"],
        "arl_level": spec["arl_level"],
        "word_count": len(tokens),
        "text_content": artifact.text_content(sentences),
        "voice_profile_id": VOICE_PROFILE,
        "length_profile": spec["length_profile"],
        "tokens": tokens,
        "propositions": spec["propositions"],
        "items": artifact.artifact_items(items),
    }
    if spec["mode"] == "READ":
        passage["paired_listening_passage_id"] = spec["paired_listening_passage_id"]
        return passage
    listening = f"gs://{BUCKET}/{VOICE_PROFILE}/{TTS_VERSION}/listening"
    passage["audio_gcs_uri"] = f"{listening}/{passage_id}.mp3"
    for item in passage["items"]:
        item["prompt_audio_gcs_uri"] = f"{listening}/{item['item_id']}.mp3"
    return passage


def check(spec: Mapping, nlp: Language, names: NameList, blocklist: Blocklist) -> list[gate.Check]:
    """The code gate for a READ story; the checks that fit for a LISTEN one."""
    spec = with_ids(spec)
    request = gate.Request(spec["arl_level"], spec["length_profile"])
    if spec["mode"] == "READ":
        return gate.run(spec, request, nlp, names, blocklist)
    ctx = gate.Context(spec, request, nlp, names, blocklist)
    low, high = LISTEN_WORDS
    fits = low <= len(ctx.words) <= high
    return [
        gate.Check(
            "listening_length", fits, "" if fits else f"{len(ctx.words)} words, not {low}-{high}"
        ),
        gate.safety_check(ctx),
        gate.names_check(ctx),
        gate.plain_text_check(ctx),
        gate.ambiguous_words_check(ctx),
    ]


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - loads spaCy
    import spacy

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("specs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    nlp, names, blocklist = spacy.load("en_core_web_sm"), data.names(), data.blocklist()
    failed = False
    for path in args.specs:
        spec = json.loads(path.read_text())
        checks = check(spec, nlp, names, blocklist)
        for result in checks:
            if not result.passed:
                failed = True
                print(f"{spec['passage_id']}: {result.name}: {result.reason}", file=sys.stderr)
        if all(result.passed for result in checks):
            out = args.out / f"passage.{spec['passage_id']}.json"
            out.write_text(json.dumps(build(spec, nlp, names), indent=2, ensure_ascii=False) + "\n")
            print(f"wrote {out}")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
