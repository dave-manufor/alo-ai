from services.session_agent import protocol
from services.session_agent.tools import fake_child
from services.session_agent.tools.fake_child import Reply, Responder, chunks


def step(name: str) -> dict:
    return {"schema_version": 3, "cmd": "step", "step": name}


def play(clip_id: str = "clip_1") -> dict:
    return {"schema_version": 3, "cmd": "play", "clip_id": clip_id}


# ---- what the child does for each message


def test_every_play_is_acked_and_the_ack_is_one_the_agent_accepts():
    reply = Responder().on_message(play("greeting"))
    assert reply.ack == {"schema_version": 3, "cmd": "played", "clip_id": "greeting"}
    assert protocol.parse_client(protocol.encode(reply.ack)).clip_id == "greeting"


def test_the_ack_uses_the_protocol_version_the_agent_sends():
    assert fake_child.SCHEMA_VERSION == protocol.SCHEMA_VERSION


def test_a_play_in_each_spoken_phase_gets_that_phases_line():
    responder = Responder()
    for phase, line in fake_child.SPOKEN_PHASES.items():
        responder.on_message(step(phase))
        assert responder.on_message(play()).say == line


def test_a_play_while_reading_gets_no_speech():
    responder = Responder()
    responder.on_message(step("READING"))
    reply = responder.on_message(play())
    assert reply.say is None
    assert reply.ack is not None


def test_the_child_reads_the_story_the_agent_shows():
    shown = {"cmd": "show_passage", "sentences": ["Ada went to the market.", "She bought rice."]}
    assert Responder().on_message(shown) == Reply(say="Ada went to the market. She bought rice.")


def test_a_passage_without_sentences_says_nothing():
    assert Responder().on_message({"cmd": "show_passage", "sentences": []}) == Reply()


def test_the_session_ends_on_the_ended_step_only():
    responder = Responder()
    assert not responder.on_message(step("CLOSE")).ended
    assert responder.on_message(step("ENDED")).ended
    assert responder.phase == "ENDED"


def test_other_messages_are_ignored():
    responder = Responder()
    for message in (
        {"cmd": "clip_list", "clips": []},
        {"cmd": "hide_passage"},
        {"cmd": "reconnecting"},
        {},
    ):
        assert responder.on_message(message) == Reply()


# ---- the voice


def test_the_speaker_asks_the_voice_in_its_own_locale_and_returns_pcm(monkeypatch):
    import aloai_azure

    asked = {}
    monkeypatch.setattr(
        aloai_azure, "synthesize", lambda config, ssml: asked.update(ssml=ssml) or b"mp3"
    )
    monkeypatch.setattr(aloai_azure, "pcm16", lambda audio: audio + b"-pcm")
    speak = fake_child.azure_speaker({"AI_MODE": "live"}, "en-NG-AbeoNeural")
    assert speak("Hello & welcome") == b"mp3-pcm"
    assert 'xml:lang="en-NG"' in asked["ssml"]
    assert 'name="en-NG-AbeoNeural"' in asked["ssml"]
    assert "Hello &amp; welcome" in asked["ssml"]


# ---- the microphone


def test_pcm_is_cut_into_whole_frames_and_the_last_is_padded_with_silence():
    frames = chunks(b"\x01\x00" * 400, samples=160)
    assert [len(f) for f in frames] == [320, 320, 320]
    assert frames[2][-2:] == b"\0\0"
    assert frames[2][:160] == b"\x01\x00" * 80


def test_no_pcm_is_no_frames():
    assert chunks(b"") == []
    assert len(chunks(b"\0" * 2 * fake_child.FRAME_SAMPLES)[0]) == 2 * fake_child.FRAME_SAMPLES
