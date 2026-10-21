"""Seeding the clips and the bank passages (services/session_agent/seed.py). Memory stores and
fake voices only: nothing here reaches a cloud."""

import copy
import io
import json
import threading
from pathlib import Path

import pytest
from aloai_blobs import MemoryBlobs
from aloai_store import MemoryStore
from services.session_agent import seed
from services.session_agent.clips.catalog import PROMPTS, ClipCatalog
from services.session_agent.clips.keys import word_key
from services.session_agent.clips.prompts import PROMPT_TEXTS
from services.session_agent.clips.store import ClipStore, MemoryBucket
from services.session_agent.machine.profiles import DEMO, STANDARD
from services.session_agent.passages import PassageBank

ROOT = Path(__file__).resolve().parents[3]
BANK_DIR = ROOT / "fixtures" / "contracts"
BANK = seed.load_bank(BANK_DIR)
BY_ID = {p["passage_id"]: p for p in BANK}


def store(scheme="az", bucket="clips", voice="vp_azure_v1") -> ClipStore:
    return ClipStore(MemoryBucket(), bucket, voice, "v1", scheme)


def mp3(text: str) -> bytes:
    return f"mp3:{text}".encode()


def word_mp3(text: str, ipa: str | None) -> bytes:
    return f"mp3:{text}:{ipa}".encode()


def run(clips=None, docs=None, **options):
    clips = clips or store()
    docs = docs or MemoryStore()
    out = io.StringIO()
    ok = seed.run(bank=BANK, store=clips, docs=docs, line=mp3, word=word_mp3, out=out, **options)
    return ok, clips, docs, out.getvalue()


# ---- what is said


def test_the_fixed_prompts_are_every_prompt_the_machine_can_say():
    assert set(PROMPTS) <= set(PROMPT_TEXTS)
    lines = seed.prompt_lines(store())
    assert [line.text for line in lines] == [PROMPT_TEXTS[p] for p in PROMPTS]
    assert lines[0].name == "vp_azure_v1/v1/interest_prompt.mp3"
    assert len({line.name for line in lines}) == len(PROMPTS)


def test_a_read_passage_has_a_clip_for_each_question_in_the_order_asked():
    passage = BY_ID["bank_p3_market_day"]
    lines = seed.passage_lines(passage, store())
    asked = sorted(passage["items"], key=lambda item: item["order"])
    assert [line.text for line in lines] == [item["prompt_text"] for item in asked]
    assert [line.name.rsplit("/", 1)[1] for line in lines] == ["question_0.mp3", "question_1.mp3"]


def test_a_listen_passage_has_its_story_first_and_then_its_item_prompts():
    passage = BY_ID["bank_l3_rain"]
    lines = seed.passage_lines(passage, store())
    assert lines[0].name == "vp_azure_v1/v1/passages/bank_l3_rain/story.mp3"
    assert lines[0].text == passage["text_content"]
    assert [line.name.rsplit("/", 1)[1] for line in lines[1:]] == ["item_0.mp3"]


# ---- making the clips


def test_only_the_missing_lines_are_made_and_an_existing_clip_is_never_replaced():
    clips = store()
    lines = seed.prompt_lines(clips)
    clips.bucket.objects[lines[0].name] = b"already here"
    made = []
    report = seed.seed_lines(lines, clips, lambda text: made.append(text) or mp3(text))
    assert report.existing == [lines[0].name]
    assert len(report.written) == len(lines) - 1
    assert lines[0].text not in made
    assert clips.bucket.objects[lines[0].name] == b"already here"
    assert seed.seed_lines(lines, clips, mp3).written == []


def test_a_line_that_cannot_be_made_is_reported_and_the_rest_are_still_made():
    clips = store()
    lines = seed.prompt_lines(clips)

    def flaky(text):
        if text == PROMPT_TEXTS["kind_end"]:
            raise ConnectionError("Speech is unavailable")
        return mp3(text)

    report = seed.seed_lines(lines, clips, flaky)
    assert list(report.failed) == [clips.prompt_clip_name("kind_end")]
    assert "unavailable" in next(iter(report.failed.values()))
    assert len(report.written) == len(lines) - 1


def test_a_line_someone_else_wrote_first_is_not_replaced():
    class Racing(MemoryBucket):
        def upload_if_absent(self, name, data, content_type):
            self.objects.setdefault(name, b"theirs")
            return False

    clips = ClipStore(Racing(), "clips", "vp_azure_v1", "v1", "az")
    report = seed.seed_lines(seed.prompt_lines(clips)[:1], clips, mp3)
    assert len(report.lost_race) == 1 and report.written == []


def test_the_same_line_twice_is_made_once():
    clips = store()
    line = seed.prompt_lines(clips)[0]
    made = []
    seed.seed_lines([line, line], clips, lambda text: made.append(text) or mp3(text))
    assert made == [line.text]


def test_lines_are_made_in_parallel_up_to_the_limit():
    clips = store()
    lines = [seed.Line(f"v/v1/x{n}.mp3", f"line {n}") for n in range(40)]
    live, peak, lock = 0, 0, threading.Lock()

    def slow(text):
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        threading.Event().wait(0.01)
        with lock:
            live -= 1
        return mp3(text)

    assert len(seed.seed_lines(lines, clips, slow).written) == 40
    assert 1 < peak <= seed.MAX_CONCURRENT_REQUESTS


# ---- the stored passage


def test_a_stored_passage_names_this_stores_clips_not_the_google_dev_ones():
    clips = store(scheme="az", bucket="clips")
    doc = seed.with_store_uris(BY_ID["bank_p3_market_day"], clips)
    assert not json.dumps(doc).count("gs://")
    tunde = next(t for t in doc["tokens"] if t.get("name_ipa"))
    key = word_key(tunde["clean_text"], tunde["name_ipa"])
    assert tunde["word_clip_gcs_uri"] == f"az://clips/vp_azure_v1/v1/words/{key}.mp3"
    assert "audio_gcs_uri" not in doc  # a READ passage has no story audio
    assert [i["prompt_audio_gcs_uri"] for i in sorted(doc["items"], key=lambda i: i["order"])] == [
        "az://clips/vp_azure_v1/v1/passages/bank_p3_market_day/question_0.mp3",
        "az://clips/vp_azure_v1/v1/passages/bank_p3_market_day/question_1.mp3",
    ]


def test_a_stored_listening_passage_names_its_story_and_item_clips():
    doc = seed.with_store_uris(BY_ID["bank_l3_rain"], store())
    assert doc["audio_gcs_uri"] == "az://clips/vp_azure_v1/v1/passages/bank_l3_rain/story.mp3"
    [item] = doc["items"]
    assert item["prompt_audio_gcs_uri"].endswith("/passages/bank_l3_rain/item_0.mp3")


def test_the_same_passage_on_google_keeps_gs_uris():
    doc = seed.with_store_uris(BY_ID["bank_l3_rain"], store(scheme="gs", bucket="aloai-dev-clips"))
    assert doc["audio_gcs_uri"].startswith("gs://aloai-dev-clips/vp_azure_v1/")


def test_the_passage_given_is_not_changed():
    before = copy.deepcopy(BY_ID["bank_l3_rain"])
    seed.with_store_uris(BY_ID["bank_l3_rain"], store())
    assert BY_ID["bank_l3_rain"] == before


def test_a_passage_that_breaks_the_schema_is_refused():
    broken = copy.deepcopy(BY_ID["bank_l3_rain"])
    del broken["items"][0]["rubric"]
    with pytest.raises(Exception, match="rubric"):
        seed.with_store_uris(broken, store())


def test_a_homograph_word_with_no_ipa_is_refused_by_name():
    broken = copy.deepcopy(BY_ID["bank_p3_market_day"])
    broken["tokens"][0].update(text="read", clean_text="read", name_ipa=None)
    with pytest.raises(ValueError, match="more than one way"):
        seed.with_store_uris(broken, store())


# ---- the whole run


def test_every_clip_a_session_asks_for_exists_after_seeding():
    ok, clips, docs, _ = run()
    assert ok
    catalog = ClipCatalog(clips, "https://example.org/clips")
    bank = PassageBank(lambda passage_id: docs.get(f"passages/{passage_id}"))
    for profile, read_id in ((DEMO, "bank_p3_market_day"), (STANDARD, "bank_p3_school_garden")):
        pair = bank.pair(read_id, profile)
        ids = {
            "passage_id": pair.read["passage_id"],
            "listening_passage_id": pair.listening["passage_id"],
        }
        asked = catalog.session_clips(
            pair.read, pair.listening, profile.n_questions, profile.n_listening_items
        )
        assert len(asked) > len(PROMPTS)
        for clip_id, _url, _text in asked:
            assert clips.bucket.exists(catalog.object_name(clip_id, **ids)), clip_id


def test_the_words_are_made_with_their_ipa_and_the_prompts_with_their_text():
    ok, clips, _, _ = run()
    assert ok
    objects = clips.bucket.objects
    assert objects[clips.prompt_clip_name("retell_prompt")] == mp3(PROMPT_TEXTS["retell_prompt"])
    assert any(
        data.startswith(b"mp3:tunde:") and not data.endswith(b":None") for data in objects.values()
    )


def test_a_second_run_makes_and_writes_nothing_new():
    clips, docs = store(), MemoryStore()
    run(clips, docs)
    objects, stored = dict(clips.bucket.objects), copy.deepcopy(docs.docs)
    ok, _, _, report = run(clips, docs)
    assert ok
    assert "0 made" in report
    assert clips.bucket.objects == objects and docs.docs == stored


def test_the_passages_are_written_after_their_clips_and_each_validates():
    _, clips, docs, report = run()
    assert sorted(docs.docs) == sorted(f"passages/{p}" for p in BY_ID)
    assert "passages: 4 written, 0 FAILED" in report


@pytest.mark.parametrize(
    "only, clips_made, passages_written", [("clips", True, False), ("passages", False, True)]
)
def test_only_clips_or_only_passages(only, clips_made, passages_written):
    _, clips, docs, _ = run(only=only)
    assert bool(clips.bucket.objects) is clips_made
    assert bool(docs.docs) is passages_written


def test_a_dry_run_writes_nothing_and_says_what_it_would_do():
    ok, clips, docs, report = run(dry_run=True)
    assert ok and not clips.bucket.objects and not docs.docs
    assert "would make" in report and "would write 4 passages" in report
    clips2, docs2 = store(), MemoryStore()
    run(clips2, docs2)
    _, _, _, again = run(clips2, docs2, dry_run=True)
    assert "would make 0 of" in again and "and 0 words" in again


def test_a_failure_is_reported_and_the_run_says_it_did_not_finish():
    def flaky(text):
        raise ConnectionError("Speech is unavailable")

    out = io.StringIO()
    ok = seed.run(bank=BANK, store=store(), docs=MemoryStore(), line=flaky, word=word_mp3, out=out)
    assert ok is False
    assert "FAILED" in out.getvalue() and "unavailable" in out.getvalue()


def test_a_passage_that_cannot_be_stored_is_reported_and_the_rest_are_written():
    bank = [copy.deepcopy(BY_ID["bank_l3_rain"]), BY_ID["bank_p3_market_day"]]
    del bank[0]["items"][0]["rubric"]
    docs, out = MemoryStore(), io.StringIO()
    ok = seed.run(
        bank=bank, store=store(), docs=docs, line=mp3, word=word_mp3, only="passages", out=out
    )
    assert ok is False
    assert list(docs.docs) == ["passages/bank_p3_market_day"]
    assert "passages: 1 written, 1 FAILED" in out.getvalue()


# ---- the command


def env(**more):
    return {"ALO_ENV": "local", "CLOUD": "azure", "AZURE_STORAGE_ACCOUNT": "aloaistore", **more}


@pytest.fixture
def stores(monkeypatch):
    blobs, docs = MemoryBlobs(), MemoryStore()
    monkeypatch.setattr(seed, "open_blobs", lambda shared: blobs)
    monkeypatch.setattr(seed, "open_store", lambda shared: docs)
    return blobs, docs


def test_the_command_seeds_silent_placeholders_with_recorded_responses(stores, capsys):
    blobs, docs = stores
    code = seed.main(["--bank-dir", str(BANK_DIR)], env(AI_MODE="fixtures", CLIPS_BUCKET="clips"))
    assert code == 0
    assert "lines:" in capsys.readouterr().out
    assert blobs.blobs and all(uri.startswith("az://clips/") for uri in blobs.blobs)
    assert len(docs.docs) == 4


def test_the_command_speaks_with_the_azure_voice_when_live(stores, monkeypatch):
    blobs, _ = stores
    asked = []
    monkeypatch.setattr(
        seed, "azure_synthesize", lambda shared, ssml: asked.append(ssml) or b"spoken"
    )
    code = seed.main(
        ["--bank-dir", str(BANK_DIR), "--only", "clips"],
        env(AI_MODE="live", TTS_VOICE="en-NG-EzinneNeural", AZURE_SPEECH_REGION="swedencentral"),
    )
    assert code == 0
    assert asked and all(
        'name="en-NG-EzinneNeural"' in ssml and 'xml:lang="en-NG"' in ssml for ssml in asked
    )
    assert set(blobs.blobs.values()) == {b"spoken"}


def test_the_command_refuses_a_live_run_it_cannot_voice(stores, capsys):
    assert seed.main([], {"ALO_ENV": "local", "AI_MODE": "live"}) == 1
    assert "no Google voice" in capsys.readouterr().err
    assert seed.main([], env(AI_MODE="live")) == 1
    assert "TTS_VOICE" in capsys.readouterr().err


def test_the_command_refuses_recorded_responses_when_hosted(stores, capsys):
    hosted = {"CLOUD": "azure", "CONTAINER_APP_NAME": "aloai-seed", "AI_MODE": "fixtures"}
    assert seed.main([], hosted) == 1
    assert "refusing to seed" in capsys.readouterr().err


def test_the_command_refuses_an_empty_bank(stores, tmp_path, capsys):
    assert seed.main(["--bank-dir", str(tmp_path)], env(AI_MODE="fixtures")) == 1
    assert "no passage" in capsys.readouterr().err


def test_the_command_exits_non_zero_when_a_clip_could_not_be_made(stores, monkeypatch):
    def down(shared, ssml):
        raise ConnectionError("Speech is unavailable")

    monkeypatch.setattr(seed, "azure_synthesize", down)
    code = seed.main(
        ["--bank-dir", str(BANK_DIR), "--only", "clips"],
        env(AI_MODE="live", TTS_VOICE="en-NG-EzinneNeural"),
    )
    assert code == 1


def test_a_homograph_with_no_ipa_is_reported_as_failed_and_left_out_of_the_dry_run_count():
    bank = [copy.deepcopy(BY_ID["bank_p3_market_day"])]
    bank[0]["tokens"][0].update(text="read", clean_text="read", name_ipa=None)
    out = io.StringIO()
    ok = seed.run(
        bank=bank, store=store(), docs=MemoryStore(), line=mp3, word=word_mp3, only="clips", out=out
    )
    assert ok is False
    assert "read" in out.getvalue() and "FAILED" in out.getvalue()
    dry = io.StringIO()
    seed.run(
        bank=bank, store=store(), docs=MemoryStore(), line=mp3, word=word_mp3, dry_run=True, out=dry
    )
    assert "would make" in dry.getvalue()
