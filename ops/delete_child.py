"""Delete one child's data: the audio, the sessions and everything under them, the report,
plan and story request, any story written for them, the consents and the child (PRD 12,
SDD 12). A guardian can ask for this at any time; deletion is by request until the
delete-child screen exists (PRD 14.1).

    PYTHONPATH=libs/aloai:. python -m ops.delete_child --child-id child_x --operator you

It is a dry run unless --yes is given, and it prints counts, never names or ids. See
ops/README.md for the steps. Audio files are removed first, then the documents with the
child last, so a run that stops half way can simply be run again.
"""

import argparse
import hashlib
import os
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import aloai_env
from aloai_blobs import Blobs, open_blobs
from aloai_store import Store, open_store

# The collections under sessions/{session_id} (services/core/grader/paths.py, aloai_events).
SESSION_PARTS = ("turns", "quick", "grading", "phase1", "errors")


class ChildNotFound(LookupError):
    pass


@dataclass(frozen=True)
class Footprint:
    documents: tuple[str, ...]
    blobs: tuple[str, ...]


def _once(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def footprint(store: Store, child_id: str) -> Footprint:
    """Everything that belongs to this child, found from the child's sessions and consents."""
    documents: list[str] = []
    blobs: list[str] = []
    session_paths = store.list_paths("sessions")
    for path, session in zip(session_paths, store.get_many(session_paths), strict=True):
        if session is None or session.get("child_id") != child_id:
            continue
        session_id = path.split("/")[1]
        documents.append(path)
        for part in SESSION_PARTS:
            part_paths = store.list_paths(f"sessions/{session_id}/{part}")
            documents.extend(part_paths)
            if part == "turns":
                blobs.extend(
                    turn["audio_uri"]
                    for turn in store.get_many(part_paths)
                    if turn and turn.get("audio_uri")
                )
        for extra in (
            f"reports/{session_id}",
            f"plans/plan_{session_id}",
            f"story_requests/story_{session_id}",
        ):
            document = store.get(extra)
            if document is not None:
                documents.append(extra)
                if document.get("summary_audio_uri"):
                    blobs.append(document["summary_audio_uri"])
        if session.get("passage_source") == "GENERATED":
            passage = f"passages/{session['passage_id']}"
            if store.get(passage) is not None:
                documents.append(passage)
    consent_paths = store.list_paths("consents")
    for path, consent in zip(consent_paths, store.get_many(consent_paths), strict=True):
        if consent is not None and consent.get("child_id") == child_id:
            documents.append(path)
    # The Account service's record of which guardian was handed a session id (GET /v1/sessions).
    start_paths = store.list_paths("session_starts")
    for path, start in zip(start_paths, store.get_many(start_paths), strict=True):
        if start is not None and start.get("child_id") == child_id:
            documents.append(path)
    if store.get(f"children/{child_id}") is not None:
        documents.append(f"children/{child_id}")
    if not documents:
        raise ChildNotFound("nothing found for that child id")
    return Footprint(_once(documents), _once(blobs))


def delete_child(
    store: Store,
    blobs: Blobs,
    child_id: str,
    *,
    operator: str,
    dry_run: bool = True,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Footprint:
    found = footprint(store, child_id)
    if dry_run:
        return found
    for uri in found.blobs:
        blobs.delete(uri)
    for path in found.documents:
        store.delete(path)
    store.set(
        f"audit_log/audit_{uuid.uuid4().hex}",
        {
            "actor": "ops",
            "operator": operator,
            "action": "child.delete",
            "child_sha256": hashlib.sha256(child_id.encode()).hexdigest(),
            "documents": len(found.documents),
            "blobs": len(found.blobs),
            "at": now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return found


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    store: Store | None = None,
    blobs: Blobs | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Delete one child's data (dry run by default).")
    parser.add_argument("--child-id", required=True)
    parser.add_argument("--operator", required=True, help="who is running this, for the audit log")
    parser.add_argument("--yes", action="store_true", help="really delete; without it, a dry run")
    args = parser.parse_args(argv)
    if store is None or blobs is None:  # pragma: no cover - builds real clients
        config = aloai_env.load(os.environ if env is None else env, receives_pushes=False)
        store, blobs = open_store(config), open_blobs(config)
    try:
        found = delete_child(
            store, blobs, args.child_id, operator=args.operator, dry_run=not args.yes
        )
    except ChildNotFound as error:
        print(f"{error}. Nothing was deleted.")
        return 1
    verb = "Deleted" if args.yes else "Would delete (dry run, add --yes to delete)"
    print(f"{verb}: {len(found.documents)} documents and {len(found.blobs)} audio files.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
