"""The LiveKit side of POST /v1/sessions: make a session room and mint the browser's token.
Only this service holds the LiveKit key and secret. The Session Agent has no agent name, so
LiveKit puts it in any new room, and it reads its job from the room metadata."""

import asyncio
from datetime import timedelta
from typing import Protocol

from livekit import api

TOKEN_LIFE = timedelta(hours=1)
# The child's browser and the agent. One more than that leaves room for the agent restarting.
MAX_PARTICIPANTS = 3
# A room nobody joined is removed after five minutes.
EMPTY_TIMEOUT_SECONDS = 300


class Rooms(Protocol):
    url: str

    def open(self, room: str, metadata: str) -> None:
        """Create the room with its metadata; raises if LiveKit cannot be reached."""

    def token(self, room: str, identity: str) -> str:
        """A join token for this one room: publish audio and data, subscribe, nothing else."""


class LiveKitRooms:
    def __init__(self, url: str, api_key: str, api_secret: str) -> None:
        self.url = url
        self._key = api_key
        self._secret = api_secret

    @property
    def _api_url(self) -> str:
        return self.url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)

    def open(self, room: str, metadata: str) -> None:
        asyncio.run(self._create(room, metadata))

    async def _create(self, room: str, metadata: str) -> None:
        client = api.LiveKitAPI(self._api_url, self._key, self._secret)
        try:
            await client.room.create_room(
                api.CreateRoomRequest(
                    name=room,
                    metadata=metadata,
                    empty_timeout=EMPTY_TIMEOUT_SECONDS,
                    max_participants=MAX_PARTICIPANTS,
                )
            )
        finally:
            await client.aclose()

    def token(self, room: str, identity: str) -> str:
        grants = api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )
        return (
            api.AccessToken(self._key, self._secret)
            .with_identity(identity)
            .with_grants(grants)
            .with_ttl(TOKEN_LIFE)
            .to_jwt()
        )
