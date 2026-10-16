"""The shared clip store layout and the only-if-absent write (PRD 4.5, SDD 6).

    gs://{clips bucket}/{voice_profile_id}/{tts_version}/words/{word_key}.mp3
    gs://{clips bucket}/{voice_profile_id}/{tts_version}/passages/{passage_id}/{name}.mp3

`tts_version` changes whenever the voice settings change, so old and new clips
never mix. Clips are shared by every story and tied to no child or account.
A real Cloud Storage bucket is wired in with the worker; MemoryBucket serves
tests and AI_MODE=fixtures.
"""

from dataclasses import dataclass, field
from typing import Protocol


class Bucket(Protocol):
    def exists(self, name: str) -> bool: ...

    def upload_if_absent(self, name: str, data: bytes, content_type: str) -> bool:
        """Write only if the object does not exist. True if this call wrote it."""
        ...


@dataclass
class MemoryBucket:
    objects: dict[str, bytes] = field(default_factory=dict)

    def exists(self, name: str) -> bool:
        return name in self.objects

    def upload_if_absent(self, name: str, data: bytes, content_type: str) -> bool:
        if name in self.objects:
            return False
        self.objects[name] = data
        return True


@dataclass(frozen=True)
class ClipStore:
    bucket: Bucket
    bucket_name: str
    voice_profile_id: str
    tts_version: str

    def word_clip_name(self, key: str) -> str:
        return f"{self.voice_profile_id}/{self.tts_version}/words/{key}.mp3"

    def passage_clip_name(self, passage_id: str, name: str) -> str:
        return f"{self.voice_profile_id}/{self.tts_version}/passages/{passage_id}/{name}.mp3"

    def uri(self, name: str) -> str:
        return f"gs://{self.bucket_name}/{name}"

    def has_word(self, key: str) -> bool:
        return self.bucket.exists(self.word_clip_name(key))

    def put_word(self, key: str, data: bytes) -> bool:
        return self.bucket.upload_if_absent(self.word_clip_name(key), data, "audio/mpeg")

    def put_passage_clip(self, passage_id: str, name: str, data: bytes) -> bool:
        return self.bucket.upload_if_absent(
            self.passage_clip_name(passage_id, name), data, "audio/mpeg"
        )
