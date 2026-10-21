"""What the Reading Coach reaches outside its own documents (SDD 8, 11): the Passage
Generator's queue, the Account and Payments email, and Chirp 3 HD for the spoken summary.

queue_story (W2) and /internal/notify (W1) are not built yet, so StoryRequests and
Outbox leave each request in Firestore for its owner to pick up.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from aloai_store import Store
from google.cloud import storage, texttospeech

REPORT_READY = "report_ready"
SPEAKING_RATE = 0.9  # [CAL] PRD 4.6


@dataclass(frozen=True)
class StoryRequests:
    store: Store

    def queue(self, *, session_id: str, child_id: str, arl: int, tags: Sequence[str]) -> str:
        """One request per session, so a rerun replaces it instead of adding another."""
        request_id = f"story_{session_id}"
        self.store.set(
            f"story_requests/{request_id}",
            {"child_id": child_id, "arl": arl, "tags": list(tags), "session_id": session_id},
        )
        return request_id


class Notifier(Protocol):
    def notify(self, *, template_id: str, guardian_id: str, child_id: str, session_id: str) -> str:
        """Send a templated email (no scores) once per session and template; the delivery id."""
        ...


@dataclass(frozen=True)
class Outbox:
    store: Store

    def notify(self, *, template_id: str, guardian_id: str, child_id: str, session_id: str) -> str:
        delivery_id = f"{session_id}_{template_id}"
        self.store.create(
            f"outbox/{delivery_id}",
            {"template_id": template_id, "guardian_id": guardian_id, "child_id": child_id},
        )
        return delivery_id


@dataclass(frozen=True)
class AccountNotifier:
    """POST {ACCOUNT_URL}/internal/notify with Core's ID token (Cloud Run IAM)."""

    url: str
    post: Callable[..., Any]
    id_token: Callable[[str], str]

    def notify(self, *, template_id: str, guardian_id: str, child_id: str, session_id: str) -> str:
        response = self.post(
            f"{self.url}/internal/notify",
            json={
                "template_id": template_id,
                "guardian_id": guardian_id,
                "child_id": child_id,
                "idempotency_key": f"{session_id}_{template_id}",
            },
            headers={"Authorization": f"Bearer {self.id_token(self.url)}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["delivery_id"]


class Speaker(Protocol):
    def speak(self, text: str, session_id: str) -> str | None:
        """The gs:// URI of the spoken text, or None when nothing is spoken."""
        ...


class SilentSpeaker:
    def speak(self, text: str, session_id: str) -> str | None:
        return None


@dataclass(frozen=True)
class ChirpSpeaker:
    """Auntie Kemi's voice (PRD 4.6), saved beside the session's audio."""

    tts: texttospeech.TextToSpeechClient
    bucket: storage.Bucket
    voice: str

    def speak(self, text: str, session_id: str) -> str | None:
        response = self.tts.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(
                language_code="-".join(self.voice.split("-")[:2]), name=self.voice
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=SPEAKING_RATE
            ),
        )
        name = f"{session_id}/summary/summary.mp3"
        self.bucket.blob(name).upload_from_string(response.audio_content, content_type="audio/mpeg")
        return f"gs://{self.bucket.name}/{name}"
