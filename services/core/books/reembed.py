"""Embed the catalogue again with the Azure embedding model (see embedding.py).

    python -m services.core.books.reembed [--dry-run] [--book-id book_x ...]

Run it as the book job on Azure (infra/azure/README.md) after the catalogue is in Cosmos DB.
It needs CLOUD=azure and AI_MODE=live: the Google embedder is for queries only, and recorded
vectors cannot be made for text that was never recorded.
"""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence

import aloai_env
from aloai_azure import deployment, open_openai
from aloai_store import open_store

from ..grader.azure import EMBEDDING_MODEL, AzureEmbedder
from .embedding import reembed_books


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed the catalogue with the Azure model.")
    parser.add_argument("--dry-run", action="store_true", help="say what would change")
    parser.add_argument("--book-id", action="append", help="only this book (repeatable)")
    args = parser.parse_args(argv)
    try:
        settings = aloai_env.load(os.environ if env is None else env)
        if settings.cloud != "azure" or settings.ai_mode != "live":
            raise aloai_env.ConfigError("re-embedding needs CLOUD=azure and AI_MODE=live")
        embedder = AzureEmbedder(open_openai(settings), deployment(settings, "embedding"))
    except aloai_env.ConfigError as error:
        print(f"refusing to re-embed: {error}", file=sys.stderr)
        return 1
    report = reembed_books(
        open_store(settings), embedder, EMBEDDING_MODEL, dry_run=args.dry_run, only=args.book_id
    )
    verb = "would re-embed" if args.dry_run else "re-embedded"
    print(f"{verb} {len(report.done)} books; {report.already} already on {EMBEDDING_MODEL}")
    for book_id, reason in report.failed.items():
        print(f"  FAILED {book_id}: {reason}")
    return 1 if report.failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
