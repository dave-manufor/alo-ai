"""The book ingestion job (PRD 9.1): real open-licence books into books/{book_id}.

    python -m services.core.books.ingest --files DIR [--manifest FILE] [--check] [--book-id ID]

The manifest (catalogue.json by default) holds what only a person can check against the
publisher's page, and nothing in it is invented: title, author, publisher, licence, the
attribution the licence requires, the publisher's own level, topic tags, the setting and a short
description. The job reads the rest from the file (extract.py): the story's text, word and page
counts, and the share of illustrated pages. It maps the publisher level to ARL (levels.py),
cross-checks it with the text-level estimate (PRD 9.2) and holds a book more than 2 levels out for
a person, embeds the description and tags with the deployment's model (embedding.py), keeps the
raw file in the private books store under its hash, and writes a document that passes
book.schema.json.

Re-running it is idempotent: a book whose file and manifest entry are unchanged is left as it is,
and a changed entry keeps its vector unless the embedded text changed. --check reads the files and
reports the levels without touching any store or model (run it before the real run).
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import aloai_contracts
import aloai_env
from aloai_blobs import Blobs, blob_uri
from aloai_store import Store

from ..generator.names import NameList
from ..generator.textlevel import estimate_arl, features
from ..grader.books import Embedder
from .embedding import COLLECTION, DIMENSIONS, book_text
from .extract import read_book
from .levels import publisher_arl

MANIFEST = Path(__file__).with_name("catalogue.json")
SCHEMA_VERSION = 3
HOLD_GAP = 2  # PRD 9.1: held when the estimate is more than 2 levels from the publisher's ARL
_BOOK = aloai_contracts.validator("book.schema.json")
_BOOK_ID = re.compile(r"^book_[a-z0-9_]+$")
# What the manifest gives. `arl` and `arl_reason` only for a publisher with no levels.
REQUIRED = (
    "book_id",
    "file",
    "title",
    "author",
    "publisher",
    "source_url",
    "licence",
    "attribution",
    "language",
    "publisher_level",
    "topic_tags",
    "west_african_setting",
    "description",
)
OPTIONAL = ("illustrator", "arl", "arl_reason")
COPIED = tuple(k for k in REQUIRED + OPTIONAL if k not in ("file", "arl", "arl_reason"))


@dataclass
class IngestReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    held: dict[str, str] = field(default_factory=dict)  # book_id -> why it is held
    failed: dict[str, str] = field(default_factory=dict)  # book_id -> why it failed


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    books = json.loads(path.read_text(encoding="utf-8"))["books"]
    if not isinstance(books, list):
        raise ValueError("the manifest's books must be a list")
    return books


def check_entry(entry: Mapping) -> int:
    """The entry's ARL. ValueError when a required field is missing or the level has no ARL."""
    missing = [key for key in REQUIRED if entry.get(key) in (None, "", [])]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    unknown = sorted(set(entry) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise ValueError(f"unknown fields {', '.join(unknown)}")
    if not _BOOK_ID.match(entry["book_id"]):
        raise ValueError("book_id must look like book_[a-z0-9_]+")
    if "arl" in entry:
        if not entry.get("arl_reason"):
            raise ValueError("an arl given by hand needs its arl_reason")
        return int(entry["arl"])
    mapped = publisher_arl(entry["publisher"], entry["publisher_level"])
    if mapped is None:
        raise ValueError(
            f"no ARL for {entry['publisher']} {entry['publisher_level']!r}: give arl and arl_reason"
        )
    return mapped


@dataclass
class Ingest:
    store: Store | None
    blobs: Blobs | None
    embedder: Embedder | None
    model: str
    cloud: str
    bucket: str
    names: NameList
    now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def run(
        self,
        entries: Sequence[Mapping],
        files: Path,
        *,
        check: bool = False,
        only: Sequence[str] | None = None,
    ) -> IngestReport:
        report = IngestReport()
        for entry in entries:
            book_id = str(entry.get("book_id"))
            if only is not None and book_id not in only:
                continue
            try:
                self._one(entry, files, report, check)
            except Exception as error:  # noqa: BLE001 - one bad book must not stop the run
                report.failed[book_id] = str(error)[:300]
        return report

    def _one(self, entry: Mapping, files: Path, report: IngestReport, check: bool) -> None:
        book_id = entry["book_id"]
        arl = check_entry(entry)
        path = files / entry["file"]
        data = path.read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()
        existing = None if check else self.store.get(f"{COLLECTION}/{book_id}")
        copied = {key: entry[key] for key in COPIED if key in entry}
        if (
            existing
            and existing.get("file_hash") == file_hash
            and self._same(existing, copied, arl)
        ):
            report.already.append(book_id)
            return
        extracted = read_book(path.name, data)
        estimated = round(estimate_arl(features(extracted.sentences, self.names)))
        estimated = min(max(estimated, 1), 12)
        held = abs(estimated - arl) > HOLD_GAP
        if held:
            report.held[book_id] = (
                f"publisher level is ARL {arl}, the text estimates ARL {estimated}"
            )
        text = book_text(copied)
        if (
            existing
            and existing.get("embedding_model") == self.model
            and book_text(existing) == text
        ):
            vector = existing["embedding"]
        elif check:
            vector = [0.0] * DIMENSIONS  # checking only: no model is called
        else:
            vector = self.embedder.embed(text)
        if len(vector) != DIMENSIONS:
            raise ValueError(f"the vector has {len(vector)} numbers, not {DIMENSIONS}")
        suffix = path.suffix.lower()
        raw_uri = blob_uri(self.cloud, self.bucket, f"raw/{file_hash}{suffix}")
        book = {
            "schema_version": SCHEMA_VERSION,
            **copied,
            "arl": arl,
            "estimated_arl": estimated,
            "held_for_review": held,
            "embedding": vector,
            "embedding_model": self.model,
            "page_count": extracted.page_count,
            "illustration_ratio": extracted.illustration_ratio,
            "word_count": extracted.word_count,
            "raw_uri": raw_uri,
            "file_hash": file_hash,
            "ingested_at": self.now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        _BOOK.validate(book)
        if check:
            report.added.append(book_id)
            return
        content_type = mimetypes.types_map.get(suffix, "application/octet-stream")
        self.blobs.write_if_absent(raw_uri, data, content_type)
        self.store.set(f"{COLLECTION}/{book_id}", book)
        (report.updated if existing else report.added).append(book_id)

    def _same(self, existing: Mapping, copied: Mapping, arl: int) -> bool:
        return (
            all(existing.get(key) == value for key, value in copied.items())
            and existing.get("arl") == arl
            and existing.get("embedding_model") == self.model
        )


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest real open-licence books (PRD 9.1).")
    parser.add_argument("--files", type=Path, required=True, help="the folder with the book files")
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help="the checked manifest")
    parser.add_argument("--check", action="store_true", help="read and report only; no store")
    parser.add_argument("--book-id", action="append", help="only this book (repeatable)")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    from ..generator import data

    try:
        entries = load_manifest(args.manifest)
        if args.check:
            ingest = Ingest(
                None, None, None, "gemini-embedding-001", "azure", "books", data.names()
            )
        else:
            ingest = _live(env, data.names())
    except (aloai_env.ConfigError, ValueError, OSError, KeyError) as error:
        print(f"refusing to ingest: {error}", file=sys.stderr)
        return 1
    report = ingest.run(entries, args.files, check=args.check, only=args.book_id)
    verb = "would add" if args.check else "added"
    print(
        f"{verb} {len(report.added)}, updated {len(report.updated)}, unchanged {len(report.already)}"
    )
    for book_id, why in report.held.items():
        print(f"  HELD {book_id}: {why} (a person checks it before it is recommended)")
    for book_id, why in report.failed.items():
        print(f"  FAILED {book_id}: {why}")
    return 1 if report.failed else 0


def _live(env: Mapping[str, str], names: NameList) -> Ingest:  # pragma: no cover - real clients
    from aloai_azure import deployment, open_openai
    from aloai_blobs import open_blobs
    from aloai_store import open_store

    from ..grader.azure import AzureEmbedder
    from .embedding import azure_embedding_model

    settings = aloai_env.load(env)
    if settings.cloud != "azure" or settings.ai_mode != "live":
        raise aloai_env.ConfigError("ingesting needs CLOUD=azure and AI_MODE=live")
    return Ingest(
        store=open_store(settings),
        blobs=open_blobs(settings),
        embedder=AzureEmbedder(open_openai(settings), deployment(settings, "embedding")),
        model=azure_embedding_model(settings),
        cloud=settings.cloud,
        bucket=aloai_env.require_setting(env.get("BOOKS_BUCKET"), "BOOKS_BUCKET"),
        names=names,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
