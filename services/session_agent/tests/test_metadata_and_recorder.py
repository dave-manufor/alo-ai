import io
import json
import uuid

import numpy as np
import pytest
import soundfile
from services.session_agent.metadata import MetadataError, parse
from services.session_agent.recorder import FlacRecorder, encode_flac, object_name
from services.session_agent.recording import AudioLog

GOOD = {"session_id": "sess_demo_001", "child_id": "child_demo_001", "context": "SCHOOL"}


# ---- session metadata


def test_metadata_gives_the_session_context():
    start = parse(json.dumps(GOOD), "vp_google_v1")
    assert start.ctx.session_id == "sess_demo_001" and start.ctx.capture_mode == "LIVE"
    assert start.ctx.voice_profile_id == "vp_google_v1" and start.passage_id is None
    returning = parse(
        json.dumps(GOOD | {"passage_id": "gen_1", "capture_mode": "LOCAL_CAPTURE"}), "v"
    )
    assert returning.passage_id == "gen_1" and returning.ctx.capture_mode == "LOCAL_CAPTURE"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("not json", "not JSON"),
        ("[1]", "JSON object"),
        ("", "lacks session_id, child_id, context"),
        (json.dumps(GOOD | {"context": "CLINIC"}), "unknown context"),
        (json.dumps(GOOD | {"capture_mode": "TAPE"}), "unknown capture_mode"),
    ],
)
def test_bad_metadata_is_refused(raw, message):
    with pytest.raises(MetadataError, match=message):
        parse(raw, "v")


def test_session_settings_cannot_come_from_metadata():
    start = parse(json.dumps(GOOD | {"voice_mode": "live_first", "session_profile": "demo"}), "v")
    assert not hasattr(start, "voice_mode") and not hasattr(start.ctx, "session_profile")


# ---- recorder


def test_flac_is_16_khz_mono_and_round_trips():
    pcm = (np.arange(16_000, dtype=np.int16) % 2_000).tobytes()
    samples, rate = soundfile.read(io.BytesIO(encode_flac(pcm)), dtype="int16")
    assert rate == 16_000 and samples.ndim == 1
    assert samples.tobytes() == pcm


def test_each_turn_uploads_its_own_flac_to_its_uri():
    uploads = []
    recorder = FlacRecorder(lambda uri, data: uploads.append((uri, len(data))))
    log = AudioLog("aloai-dev-audio", str(uuid.uuid4()))
    recorder.feed(b"\x01\x00" * 10)  # before any turn: dropped
    recorder.stop()  # nothing to stop
    first = log.new_turn("RETELL")
    recorder.start(first)
    recorder.feed(b"\x01\x00" * 1600)
    recorder.stop()
    assert [uri for uri, _ in uploads] == [first.audio_uri]
    assert uploads[0][1] > 0


def test_object_name_splits_a_gs_uri():
    assert object_name("gs://aloai-dev-audio/abc/RETELL/x.flac") == (
        "aloai-dev-audio",
        "abc/RETELL/x.flac",
    )
