"""A stand-in for the web app and the child, for local runs and the cloud smoke (not used in production).

Creates a room with session metadata, joins as "child", publishes a microphone and prints
every data-channel message the agent sends. Like the web app, it answers each `play` with
`played`, so the agent's answer timers start. Unless --silent, the child also talks: it reads
the story the agent shows and gives short fictional answers, spoken by Azure AI Speech at run
time (nothing recorded, no audio in Git), so a session can run to a report. It leaves when the
agent sends the ENDED step.

    PYTHONPATH=libs/aloai services/session_agent/.venv/bin/python \
        services/session_agent/tools/fake_child.py --room alo-test-1 --silent
"""

import argparse
import asyncio
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

TOPIC = "aloai.session"
SCHEMA_VERSION = 2  # services/session_agent/protocol.py
SAMPLE_RATE = 16_000
FRAME_SAMPLES = SAMPLE_RATE // 100  # 10 ms
DEFAULT_VOICE = "en-NG-EzinneNeural"
LEAVE_DELAY_S = 2.0

# What the child says outside the story. Fictional, and kind, so nothing here trips a rule.
INTEREST_LINE = "I like football and jollof rice."
MIC_LINE = "Hello, I am ready to read."
RETELL_LINE = "The story was about a child at the market, and everyone was happy at the end."
ANSWER_LINE = "I think it was because they were kind."
LISTEN_LINE = "It was about a child who was kind."

SPOKEN_PHASES = {
    "INTEREST_CHAT": INTEREST_LINE,
    "MIC_CHECK": MIC_LINE,
    "RETELL": RETELL_LINE,
    "QUESTIONS": ANSWER_LINE,
    "LISTENING": LISTEN_LINE,
}


@dataclass(frozen=True)
class Reply:
    ack: dict | None = None  # sent back on the data channel
    say: str | None = None  # spoken into the microphone
    ended: bool = False  # the agent has ended the session


class Responder:
    """What the child does for each message from the agent. It follows the agent's steps and
    never decides anything itself, as the web app does."""

    def __init__(self) -> None:
        self.phase = ""

    def on_message(self, message: dict) -> Reply:
        match message.get("cmd"):
            case "step":
                self.phase = str(message.get("step", ""))
                return Reply(ended=self.phase == "ENDED")
            case "show_passage":
                return Reply(say=" ".join(message.get("sentences", [])) or None)
            case "play":
                ack = {
                    "schema_version": SCHEMA_VERSION,
                    "cmd": "played",
                    "clip_id": message["clip_id"],
                }
                return Reply(ack=ack, say=SPOKEN_PHASES.get(self.phase))
        return Reply()


def chunks(pcm: bytes, samples: int = FRAME_SAMPLES) -> list[bytes]:
    """16-bit mono PCM cut into frames of `samples` samples, the last one padded with silence."""
    size = samples * 2
    return [pcm[i : i + size].ljust(size, b"\0") for i in range(0, len(pcm), size)]


def azure_speaker(env: dict[str, str], voice: str = DEFAULT_VOICE) -> Callable[[str], bytes]:
    """Text to 16 kHz mono PCM with Azure AI Speech. Needs AZURE_SPEECH_REGION and either
    AZURE_SPEECH_KEY or AZURE_SPEECH_RESOURCE_ID with an `az login` that may use it."""
    import aloai_azure
    import aloai_env

    config = aloai_env.load(env, receives_pushes=False)
    locale = voice[:5]

    def speak(text: str) -> bytes:
        ssml = aloai_azure.build_ssml(text, voice=voice, locale=locale)
        return aloai_azure.pcm16(aloai_azure.synthesize(config, ssml))

    return speak


async def run_session(  # pragma: no cover - needs a LiveKit server and the agent
    *,
    url: str,
    key: str,
    secret: str,
    room_name: str,
    metadata: dict,
    speak: Callable[[str], bytes] | None,
    seconds: int,
) -> dict:
    """Join the room as the child and follow the agent until it ends the session or `seconds`
    pass. speak is None for a silent child. Returns what happened."""
    from livekit import api, rtc

    lk = api.LiveKitAPI(url, key, secret)
    await lk.room.create_room(api.CreateRoomRequest(name=room_name, metadata=json.dumps(metadata)))
    await lk.aclose()

    token = (
        api.AccessToken(key, secret)
        .with_identity("child")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    room = rtc.Room()
    responder = Responder()
    said: asyncio.Queue[bytes] = asyncio.Queue()
    ended = asyncio.Event()
    tasks: set[asyncio.Task] = set()
    result = {"ended": False, "messages": 0, "spoken": 0}
    started = time.monotonic()

    async def talk(text: str) -> None:
        pcm = await asyncio.get_running_loop().run_in_executor(None, speak, text)
        result["spoken"] += 1
        await said.put(pcm)

    def spawn(coro) -> None:
        task = asyncio.ensure_future(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @room.on("data_received")
    def on_data(packet: rtc.DataPacket) -> None:
        if packet.topic != TOPIC:
            return
        message = json.loads(packet.data)
        result["messages"] += 1
        shown = {k: v for k, v in message.items() if k not in ("schema_version", "clips")}
        if "clips" in message:
            shown["clips"] = f"{len(message['clips'])} clips"
        print(f"{time.monotonic() - started:6.1f}s  agent -> {shown}", flush=True)
        reply = responder.on_message(message)
        if reply.ack:
            spawn(room.local_participant.publish_data(json.dumps(reply.ack), topic=TOPIC))
        if reply.say and speak:
            spawn(talk(reply.say))
        if reply.ended:
            result["ended"] = True
            ended.set()

    print(f"joining room {room_name} as 'child' for up to {seconds}s", flush=True)
    await room.connect(url, token)
    source = rtc.AudioSource(SAMPLE_RATE, 1)
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(track, options)
    silence = rtc.AudioFrame.create(SAMPLE_RATE, 1, FRAME_SAMPLES)
    deadline = time.monotonic() + seconds
    left_at: float | None = None
    while time.monotonic() < deadline:
        if ended.is_set():
            left_at = left_at or time.monotonic() + LEAVE_DELAY_S
            if time.monotonic() >= left_at:
                break
        try:
            pcm = said.get_nowait()
        except asyncio.QueueEmpty:
            await source.capture_frame(silence)
            continue
        for part in chunks(pcm):
            frame = rtc.AudioFrame(part, SAMPLE_RATE, 1, FRAME_SAMPLES)
            await source.capture_frame(frame)
    for task in list(tasks):
        task.cancel()
    await room.disconnect()
    return result


def main() -> None:  # pragma: no cover - needs a LiveKit server
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--room", default="alo-test-1")
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--silent", action="store_true", help="a silent microphone, no speech")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--url", default=os.environ.get("LIVEKIT_URL", "ws://localhost:7880"))
    parser.add_argument("--key", default=os.environ.get("LIVEKIT_API_KEY", "devkey"))
    parser.add_argument("--secret", default=os.environ.get("LIVEKIT_API_SECRET", "secret"))
    args = parser.parse_args()
    metadata = {"session_id": f"sess_{args.room}", "child_id": "child_demo_001", "context": "HOME"}
    speak = None if args.silent else azure_speaker(dict(os.environ), args.voice)
    result = asyncio.run(
        run_session(
            url=args.url,
            key=args.key,
            secret=args.secret,
            room_name=args.room,
            metadata=metadata,
            speak=speak,
            seconds=args.seconds,
        )
    )
    print(f"left the room: {result}")


if __name__ == "__main__":  # pragma: no cover
    main()
