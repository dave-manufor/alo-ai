"""A stand-in for the web app and the child, for local runs (not used in production).

Creates a room with session metadata, joins as "child", publishes a silent
microphone and prints every data-channel message the agent sends. Like the web
app, it answers each `play` with `played`, so the agent's answer timers start.

    services/session_agent/.venv/bin/python services/session_agent/tools/fake_child.py \
        --room alo-test-1 --seconds 60
"""

import argparse
import asyncio
import json
import time

from livekit import api, rtc

TOPIC = "aloai.session"


async def run(args: argparse.Namespace) -> None:
    lk = api.LiveKitAPI(args.url, args.key, args.secret)
    meta = {"session_id": f"sess_{args.room}", "child_id": "child_demo_001", "context": "HOME"}
    await lk.room.create_room(api.CreateRoomRequest(name=args.room, metadata=json.dumps(meta)))
    await lk.aclose()

    token = (
        api.AccessToken(args.key, args.secret)
        .with_identity("child")
        .with_grants(api.VideoGrants(room_join=True, room=args.room))
        .to_jwt()
    )
    room = rtc.Room()
    started = time.monotonic()

    @room.on("data_received")
    def on_data(packet: rtc.DataPacket) -> None:
        if packet.topic != TOPIC:
            return
        message = json.loads(packet.data)
        shown = {k: v for k, v in message.items() if k not in ("schema_version", "clips")}
        if "clips" in message:
            shown["clips"] = f"{len(message['clips'])} clips"
        print(f"{time.monotonic() - started:6.1f}s  agent -> {shown}", flush=True)
        if message.get("cmd") == "play":
            ack = {"schema_version": 1, "cmd": "played", "clip_id": message["clip_id"]}
            asyncio.ensure_future(room.local_participant.publish_data(json.dumps(ack), topic=TOPIC))

    print(f"joining room {args.room} as 'child' (silent microphone) for {args.seconds}s")
    await room.connect(args.url, token)
    source = rtc.AudioSource(16_000, 1)
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(track, options)
    silence = rtc.AudioFrame.create(16_000, 1, 160)  # 10 ms
    for _ in range(args.seconds * 100):
        await source.capture_frame(silence)
    await room.disconnect()
    print("left the room; the agent now waits 30 s for a reconnect, then ends the session")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--room", default="alo-test-1")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--url", default="ws://localhost:7880")
    parser.add_argument("--key", default="devkey")
    parser.add_argument("--secret", default="secret")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
