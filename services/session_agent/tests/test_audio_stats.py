import asyncio
import logging
import math
from array import array

from services.session_agent.audio_stats import BLOCK_SAMPLES, AudioStats
from services.session_agent.supervise import supervised


def pcm(dbfs: float, blocks: int = 1) -> bytes:
    """A 16 kHz sine at the given level, `blocks` x 100 ms, as 16-bit PCM."""
    amplitude = 32_767 * 10 ** (dbfs / 20) * math.sqrt(2)
    n = BLOCK_SAMPLES * blocks
    return array("h", (int(amplitude * math.sin(i / 8)) for i in range(n))).tobytes()


def test_a_turn_with_no_audio_says_so():
    assert "no audio" in AudioStats().end_turn()


def test_the_level_of_a_turn_is_reported_in_dbfs_and_then_starts_over():
    stats = AudioStats()
    stats.frame(pcm(-20, 5), now_ms=100)
    stats.frame(pcm(-50, 5), now_ms=600)
    summary = stats.end_turn()
    assert "max -20" in summary and "10/10 blocks above -60" in summary
    assert "no audio" in stats.end_turn()


def test_silence_is_counted_as_audio_that_is_not_voice():
    stats = AudioStats()
    stats.frame(bytes(2 * BLOCK_SAMPLES * 3), now_ms=0)
    assert stats.frames == 1
    assert "0/3 blocks above -60" in stats.end_turn()


def test_a_frame_shorter_than_a_block_is_kept_for_the_next_one():
    stats = AudioStats()
    half = pcm(-20)[:BLOCK_SAMPLES]  # half a block of 16-bit samples
    stats.frame(half, now_ms=0)
    assert "no audio" in stats.end_turn()  # not yet a whole block
    stats.frame(half, now_ms=50)
    stats.frame(half + half, now_ms=100)
    assert "blocks above" in stats.end_turn()


def test_an_odd_trailing_byte_is_ignored_not_a_crash():
    AudioStats().frame(b"\x01\x02\x03", now_ms=0)


def test_the_counters_say_what_the_voice_detector_and_speech_to_text_did():
    stats = AudioStats()
    stats.frame(pcm(-20), now_ms=250)
    stats.vad_started(clip_playing=False)
    stats.vad_started(clip_playing=True)
    stats.vad_ended()
    stats.transcript("one", final=False)
    stats.transcript("one two", final=True)
    stats.transcript("   ", final=True)
    stats.stt_error()
    line = stats.line()
    assert "frames 1 (first 250 ms)" in line
    assert "vad starts 2 ends 1 during clip 1" in line
    assert "stt interim 1 final 1 empty 1 errors 1" in line
    assert "stopped" not in line


def test_no_frames_at_all_is_visible_in_the_line():
    assert "frames 0 (first none)" in AudioStats().line()


def test_a_stopped_task_is_named_in_the_line():
    stats = AudioStats()
    stats.task_stopped("speech_to_text", "RuntimeError")
    assert "stopped: speech_to_text: RuntimeError" in stats.line()


# ---- supervised tasks


def run(coro):
    return asyncio.run(coro)


def test_a_task_that_fails_is_logged_by_class_only_and_reported(caplog):
    seen = []

    async def work():
        raise RuntimeError("the child said hello")

    async def main():
        task = supervised(
            "speech_to_text",
            work(),
            log=logging.getLogger("t"),
            stopped=lambda name, how: seen.append((name, how)),
        )
        await task

    with caplog.at_level(logging.INFO, logger="t"):
        run(main())
    assert seen == [("speech_to_text", "RuntimeError")]
    assert "speech_to_text stopped: RuntimeError" in caplog.text
    assert "hello" not in caplog.text


def test_a_task_that_just_ends_is_reported_as_ended(caplog):
    seen = []

    async def work():
        return None

    async def main():
        await supervised(
            "audio_frames",
            work(),
            log=logging.getLogger("t"),
            stopped=lambda name, how: seen.append((name, how)),
        )

    with caplog.at_level(logging.INFO, logger="t"):
        run(main())
    assert seen == [("audio_frames", "ended")]
    assert "audio_frames ended" in caplog.text


def test_cancelling_a_task_is_not_reported_as_a_failure():
    seen = []

    async def work():
        await asyncio.Event().wait()

    async def main():
        task = supervised(
            "voice_detection",
            work(),
            log=logging.getLogger("t"),
            stopped=lambda name, how: seen.append((name, how)),
        )
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    run(main())
    assert seen == []
