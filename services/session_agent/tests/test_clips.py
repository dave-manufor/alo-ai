import pytest
from services.session_agent.clips.keys import HOMOGRAPHS, clean_word, word_key
from services.session_agent.clips.seed import (
    MAX_CONCURRENT_REQUESTS,
    WordToSeed,
    seed_words,
    silent_clip,
    words_from_tokens,
)
from services.session_agent.clips.store import ClipStore, MemoryBucket

# ---- word keys


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Hello,", "hello"),
        ('"Market!"', "market"),
        ("Jàpá", "jàpá"),
        ("don’t", "don't"),
        ("'tis", "tis"),
        ("dogs'", "dogs"),
        ("well-known", "wellknown"),
        ("9", "9"),
        ("—", ""),
    ],
)
def test_clean_word(raw, clean):
    assert clean_word(raw) == clean


def test_accents_are_kept_so_names_do_not_collide():
    assert word_key("Jàpá") != word_key("Japa")
    assert word_key("Jàpá") == "j%C3%A0p%C3%A1"


def test_composed_and_decomposed_accents_make_the_same_key():
    assert word_key("é") == word_key("é")


def test_apostrophe_keeps_we_ll_apart_from_well():
    assert word_key("we'll") != word_key("well")


def test_case_and_punctuation_do_not_change_the_key():
    assert word_key("Market,") == word_key("market")


def test_a_name_adds_its_ipa():
    assert word_key("Ngozi", "ŋɡoːzi") == "ngozi~%C5%8B%C9%A1o%CB%90zi"
    assert word_key("Ngozi", "ŋɡoːzi") != word_key("Ngozi")
    assert word_key("Ngozi", "ŋɡoːzi") != word_key("Ngozi", "nɡozi")


def test_a_homograph_needs_its_ipa():
    for word in HOMOGRAPHS:
        with pytest.raises(ValueError, match="IPA"):
            word_key(word)
    assert word_key("read", "ɹɛd") != word_key("read", "ɹiːd")


def test_a_word_with_nothing_in_it_has_no_key():
    with pytest.raises(ValueError, match="no word"):
        word_key("...")


# ---- clip store layout


def make_store(bucket=None):
    return ClipStore(bucket or MemoryBucket(), "aloai-dev-clips", "vp_google_v1", "v1")


def test_clip_paths_follow_the_prd_layout():
    store = make_store()
    assert store.word_clip_name("market") == "vp_google_v1/v1/words/market.mp3"
    assert (
        store.passage_clip_name("p1", "question_0") == "vp_google_v1/v1/passages/p1/question_0.mp3"
    )
    assert store.uri("a/b.mp3") == "gs://aloai-dev-clips/a/b.mp3"


def test_a_new_tts_version_does_not_share_clips():
    bucket = MemoryBucket()
    old = ClipStore(bucket, "b", "vp", "v1")
    new = ClipStore(bucket, "b", "vp", "v2")
    old.put_word("market", b"old")
    assert old.has_word("market") and not new.has_word("market")


def test_writes_happen_only_if_absent():
    store = make_store()
    assert store.put_word("market", b"first") is True
    assert store.put_word("market", b"second") is False
    assert store.bucket.objects["vp_google_v1/v1/words/market.mp3"] == b"first"
    assert store.put_passage_clip("p1", "q0", b"x") is True
    assert store.put_passage_clip("p1", "q0", b"y") is False


# ---- seeding


def tokens(*texts):
    return [{"text": t, "clean_text": clean_word(t)} for t in texts]


def test_words_from_tokens_skips_punctuation_and_keeps_name_ipa():
    found = words_from_tokens(
        [
            {"text": "Ngozi,", "clean_text": "ngozi", "name_ipa": "ŋɡoːzi"},
            {"text": "—", "clean_text": ""},
            {"text": "Market"},
        ]
    )
    assert found == [WordToSeed("ngozi", "ŋɡoːzi"), WordToSeed("Market", None)]


def test_seed_writes_only_the_missing_clips():
    store = make_store()
    store.put_word("market", b"already")
    calls = []

    def synth(text, ipa):
        calls.append(text)
        return b"mp3:" + text.encode()

    words = [WordToSeed("Market"), WordToSeed("day"), WordToSeed("DAY,"), WordToSeed("market")]
    report = seed_words(words, store, synth)
    assert report.existing == ["market"]
    assert report.written == ["day"]
    assert calls == ["day"]  # one request for a word seen twice
    assert store.bucket.objects["vp_google_v1/v1/words/day.mp3"] == b"mp3:day"


def test_seed_reports_a_homograph_without_ipa_and_carries_on():
    report = seed_words([WordToSeed("read"), WordToSeed("sun")], make_store(), lambda t, i: b"x")
    assert report.written == ["sun"]
    assert "IPA" in report.failed["read"]


def test_seed_reports_a_failed_synthesis_and_carries_on():
    def synth(text, ipa):
        if text == "bad":
            raise RuntimeError("tts unavailable")
        return b"x"

    report = seed_words([WordToSeed("bad"), WordToSeed("good")], make_store(), synth)
    assert report.written == ["good"]
    assert report.failed == {"bad": "tts unavailable"}


def test_seed_notes_a_clip_another_writer_finished_first():
    store = make_store()

    def synth(text, ipa):
        store.put_word("sun", b"theirs")  # another seeder wins the race
        return b"mine"

    report = seed_words([WordToSeed("sun")], store, synth)
    assert report.lost_race == ["sun"] and report.written == []
    assert store.bucket.objects["vp_google_v1/v1/words/sun.mp3"] == b"theirs"


def test_seed_passes_the_ipa_to_the_voice():
    seen = []
    seed_words(
        [WordToSeed("Ngozi", "ŋɡoːzi")], make_store(), lambda t, i: seen.append((t, i)) or b"x"
    )
    assert seen == [("ngozi", "ŋɡoːzi")]


def test_silent_clip_is_a_small_mp3_frame_and_requests_are_capped():
    clip = silent_clip("anything")
    assert clip[:2] == b"\xff\xfb" and len(clip) == 417
    assert MAX_CONCURRENT_REQUESTS == 16
