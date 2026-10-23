import hashlib
from datetime import UTC, datetime

import pytest
from aloai_blobs import MemoryBlobs
from aloai_store import MemoryStore
from ops.delete_child import ChildNotFound, delete_child, footprint, main

AUDIO = "az://aloai-audio/"
NOW = datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)


def seed() -> tuple[MemoryStore, MemoryBlobs]:
    """Two children. c1 has two sessions (one with a generated story); c2 has one."""
    store = MemoryStore(
        {
            "guardians/g1": {"email": "guardian@example.com"},
            "children/c1": {"guardian_id": "g1", "first_name": "Demo"},
            "children/c2": {"guardian_id": "g2", "first_name": "Other"},
            "consents/k1": {"child_id": "c1"},
            "consents/k1b": {"child_id": "c1"},
            "consents/k2": {"child_id": "c2"},
            "session_starts/s1": {"guardian_id": "g1", "child_id": "c1"},
            "session_starts/s2": {"guardian_id": "g2", "child_id": "c2"},
            "sessions/s1": {"child_id": "c1", "passage_source": "BANK", "passage_id": "bank_x"},
            "sessions/s1/turns/t1": {"audio_uri": AUDIO + "u1.flac"},
            "sessions/s1/turns/t2": {"audio_uri": AUDIO + "u2.flac"},
            "sessions/s1/quick/RESULT": {"n": 1},
            "sessions/s1/grading/final": {"n": 1},
            "sessions/s1/phase1/telemetry": {"n": 1},
            "sessions/s1/errors/report.ready": {"n": 1},
            "reports/s1": {"child_id": "c1"},
            "plans/plan_s1": {"summary_audio_uri": AUDIO + "summary1.mp3"},
            "story_requests/story_s1": {"n": 1},
            "sessions/s3": {"child_id": "c1", "passage_source": "GENERATED", "passage_id": "gen_3"},
            "sessions/s3/turns/t9": {"audio_uri": None},
            "passages/gen_3": {"text": "a story"},
            "passages/bank_x": {"text": "a bank story"},
            "sessions/s2": {"child_id": "c2", "passage_source": "BANK", "passage_id": "bank_x"},
            "sessions/s2/turns/t5": {"audio_uri": AUDIO + "u5.flac"},
            "reports/s2": {"child_id": "c2"},
            "plans/plan_s2": {"summary_audio_uri": None},
        }
    )
    blobs = MemoryBlobs(
        {
            AUDIO + "u1.flac": b"1",
            AUDIO + "u2.flac": b"2",
            AUDIO + "summary1.mp3": b"s",
            AUDIO + "u5.flac": b"5",
        }
    )
    return store, blobs


def test_the_footprint_is_everything_that_belongs_to_the_child_and_nothing_else():
    store, _ = seed()
    found = footprint(store, "c1")
    assert set(found.blobs) == {AUDIO + "u1.flac", AUDIO + "u2.flac", AUDIO + "summary1.mp3"}
    assert set(found.documents) == {
        "children/c1",
        "consents/k1",
        "consents/k1b",
        "session_starts/s1",
        "sessions/s1",
        "sessions/s1/turns/t1",
        "sessions/s1/turns/t2",
        "sessions/s1/quick/RESULT",
        "sessions/s1/grading/final",
        "sessions/s1/phase1/telemetry",
        "sessions/s1/errors/report.ready",
        "reports/s1",
        "plans/plan_s1",
        "story_requests/story_s1",
        "sessions/s3",
        "sessions/s3/turns/t9",
        "passages/gen_3",
    }
    assert found.documents[-1] == "children/c1"


def test_a_dry_run_changes_nothing():
    store, blobs = seed()
    before = (dict(store.docs), dict(blobs.blobs))
    found = delete_child(store, blobs, "c1", operator="someone")
    assert len(found.documents) == 17
    assert (store.docs, blobs.blobs) == before


def test_deleting_removes_the_child_and_leaves_everyone_else():
    store, blobs = seed()
    found = delete_child(store, blobs, "c1", operator="someone", dry_run=False, now=lambda: NOW)
    assert found.blobs and found.documents
    assert not [p for p in store.docs if p.startswith("sessions/s1") or p.startswith("sessions/s3")]
    assert "children/c1" not in store.docs and "consents/k1" not in store.docs
    assert "passages/gen_3" not in store.docs
    # The other child, the guardian and the shared bank passage are untouched.
    for kept in ("children/c2", "consents/k2", "sessions/s2", "sessions/s2/turns/t5",
                 "reports/s2", "plans/plan_s2", "guardians/g1", "passages/bank_x",
                 "session_starts/s2"):
        assert kept in store.docs
    assert blobs.blobs == {AUDIO + "u5.flac": b"5"}


def test_the_deletion_is_audited_without_the_child_id_or_any_name():
    store, blobs = seed()
    delete_child(store, blobs, "c1", operator="david", dry_run=False, now=lambda: NOW)
    entries = [d for p, d in store.docs.items() if p.startswith("audit_log/")]
    assert entries == [
        {
            "actor": "ops",
            "operator": "david",
            "action": "child.delete",
            "child_sha256": hashlib.sha256(b"c1").hexdigest(),
            "documents": 17,
            "blobs": 3,
            "at": "2026-02-01T12:00:00Z",
        }
    ]


def test_a_dry_run_writes_no_audit_entry():
    store, blobs = seed()
    delete_child(store, blobs, "c1", operator="david")
    assert not [p for p in store.docs if p.startswith("audit_log/")]


def test_running_it_again_after_a_deletion_finds_nothing():
    store, blobs = seed()
    delete_child(store, blobs, "c1", operator="david", dry_run=False)
    with pytest.raises(ChildNotFound):
        delete_child(store, blobs, "c1", operator="david", dry_run=False)


def test_a_run_that_stopped_after_the_audio_can_be_finished():
    store, blobs = seed()
    for uri in list(blobs.blobs):
        if "u5" not in uri:
            blobs.delete(uri)
    delete_child(store, blobs, "c1", operator="david", dry_run=False)
    assert "children/c1" not in store.docs


def test_an_unknown_child_is_not_found():
    store, blobs = seed()
    with pytest.raises(ChildNotFound):
        delete_child(store, blobs, "nobody", operator="david", dry_run=False)
    assert len(store.docs) == 26 and len(blobs.blobs) == 4


def test_a_child_with_only_a_consent_is_still_found():
    store = MemoryStore({"consents/k": {"child_id": "c9"}})
    assert footprint(store, "c9").documents == ("consents/k",)


def test_the_command_is_a_dry_run_unless_asked(capsys):
    store, blobs = seed()
    assert main(["--child-id", "c1", "--operator", "me"], store=store, blobs=blobs) == 0
    out = capsys.readouterr().out
    assert "Would delete" in out and "17 documents and 3 audio files" in out
    assert "children/c1" in store.docs


def test_the_command_deletes_with_yes_and_prints_counts_not_ids(capsys):
    store, blobs = seed()
    assert main(["--child-id", "c1", "--operator", "me", "--yes"], store=store, blobs=blobs) == 0
    out = capsys.readouterr().out
    assert out.startswith("Deleted: 17 documents and 3 audio files")
    assert "c1" not in out and "Demo" not in out
    assert "children/c1" not in store.docs


def test_the_command_says_so_and_fails_for_an_unknown_child(capsys):
    store, blobs = seed()
    code = main(["--child-id", "nobody", "--operator", "me", "--yes"], store=store, blobs=blobs)
    assert code == 1
    assert "Nothing was deleted" in capsys.readouterr().out


def test_the_command_needs_a_child_and_an_operator():
    store, blobs = seed()
    for argv in (["--operator", "me"], ["--child-id", "c1"]):
        with pytest.raises(SystemExit):
            main(argv, store=store, blobs=blobs)
