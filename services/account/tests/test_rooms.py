import jwt
import pytest
from services.account import rooms as rooms_module
from services.account.main import livekit_rooms
from services.account.rooms import LiveKitRooms
from services.account.settings import AccountSettings
from services.account.tests.support import SETTINGS

KEY = "devkey"
SECRET = "a-long-enough-secret-for-hs256-signing-0123456789"


class FakeRoomService:
    def __init__(self, calls: list, fail: bool) -> None:
        self.calls = calls
        self.fail = fail

    async def create_room(self, request) -> None:
        self.calls.append(("create", request))
        if self.fail:
            raise ConnectionError("down")


class FakeLiveKitAPI:
    calls: list = []
    fail = False

    def __init__(self, url: str, api_key: str, api_secret: str) -> None:
        self.calls.append(("open", url, api_key, api_secret))
        self.room = FakeRoomService(self.calls, self.fail)

    async def aclose(self) -> None:
        self.calls.append(("close",))


@pytest.fixture
def fake_api(monkeypatch):
    FakeLiveKitAPI.calls = []
    FakeLiveKitAPI.fail = False
    monkeypatch.setattr(rooms_module.api, "LiveKitAPI", FakeLiveKitAPI)
    return FakeLiveKitAPI


def test_open_makes_the_room_with_its_metadata_over_https(fake_api):
    LiveKitRooms("wss://livekit.example.test", KEY, SECRET).open("sess_1", '{"a": 1}')
    opened, created, closed = fake_api.calls
    assert opened == ("open", "https://livekit.example.test", KEY, SECRET)
    request = created[1]
    assert (request.name, request.metadata) == ("sess_1", '{"a": 1}')
    assert request.max_participants == rooms_module.MAX_PARTICIPANTS
    assert request.empty_timeout == rooms_module.EMPTY_TIMEOUT_SECONDS
    assert closed == ("close",)


def test_a_plain_ws_address_uses_plain_http(fake_api):
    LiveKitRooms("ws://localhost:7880", KEY, SECRET).open("sess_1", "{}")
    assert fake_api.calls[0][1] == "http://localhost:7880"


def test_the_client_is_closed_even_when_livekit_is_down(fake_api):
    fake_api.fail = True
    with pytest.raises(ConnectionError):
        LiveKitRooms("wss://livekit.example.test", KEY, SECRET).open("sess_1", "{}")
    assert fake_api.calls[-1] == ("close",)


def test_the_token_joins_one_room_and_nothing_else():
    token = LiveKitRooms("wss://x.test", KEY, SECRET).token("sess_1", "guardian:g1")
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_aud": False})
    assert (claims["iss"], claims["sub"]) == (KEY, "guardian:g1")
    assert claims["exp"] - claims["nbf"] == int(rooms_module.TOKEN_LIFE.total_seconds())
    assert claims["video"] == {
        "roomJoin": True,
        "room": "sess_1",
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": True,
    }


def test_rooms_exist_only_when_livekit_is_fully_configured():
    full = AccountSettings(
        **{**SETTINGS.__dict__, "livekit_url": "wss://x.test", "livekit_api_key": KEY}
        | {"livekit_api_secret": SECRET}
    )
    assert isinstance(livekit_rooms(full), LiveKitRooms)
    assert livekit_rooms(SETTINGS) is None
    partial = AccountSettings(**{**SETTINGS.__dict__, "livekit_url": "wss://x.test"})
    assert livekit_rooms(partial) is None
