"""Pre-generating the child's next story (PRD 4.5, SDD 11): the Passage Generator's
handler for plan.ready.

The Reading Coach's queue_story writes story_requests/story_{session_id} before it
publishes plan.ready. This generates the story with no deadline and no bank fallback,
stores it at passages/gen_next_{session_id}, sets children/{child_id}.next_passage_id
(which the Account service passes to the next session as passage_id) and marks the
request DONE. A story that fails the gate marks the request FAILED, and the child simply
gets a live story next time.

Each step is idempotent and the request is marked last, so a redelivered plan.ready
finishes whatever a crash left undone. A request with a status is skipped. Vertex AI or
Firestore not answering raises, so Pub/Sub retries; a request that breaks its schema
raises ValidationError, which the events route parks.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

import aloai_contracts
from aloai_events import iso_utc
from aloai_store import Store, require

from .generator.pipeline import GateFailed, Generator, Request, choose_listening
from .grader import paths

log = logging.getLogger(__name__)


def request_path(session_id: str) -> str:
    return f"story_requests/story_{session_id}"


def next_passage_id(session_id: str) -> str:
    return f"gen_next_{session_id}"


class NextStories:
    def __init__(
        self,
        generator: Generator,
        store: Store,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.generator, self.store, self.clock = generator, store, clock

    def handle(self, session_id: str) -> None:
        path = request_path(session_id)
        request = self.store.get(path)
        if request is None:
            log.info("no story request for %s", session_id)  # the Coach had no tags to send
            return
        if "status" in request:
            return  # already handled
        aloai_contracts.STORY_REQUEST.validate(request)
        passage_id = next_passage_id(session_id)
        passage_path = paths.passage(passage_id)
        if self.store.get(passage_path) is None:
            session = require(self.store, paths.session(session_id))
            length_profile = session["session_profile"].upper()
            try:
                generated = self.generator.generate(
                    Request(
                        session_id=session_id,
                        target_arl=request["arl"],
                        tags=tuple(request["tags"]),
                        length_profile=length_profile,
                        voice_profile_id=session["voice_profile_id"],
                        deadline_ms=None,
                    ),
                    passage_id,
                    choose_listening(
                        self.store.where("passages", "mode", "LISTEN"),
                        request["arl"],
                        length_profile,
                    ),
                )
            except GateFailed as error:
                log.info("next story for %s failed the gate: %s", session_id, error.attempts)
                self.store.merge(path, {"status": "FAILED", "processed_at": self._now()})
                return
            aloai_contracts.PASSAGE.validate(generated.passage)
            self.store.create(passage_path, generated.passage)
        self.store.merge(paths.child(request["child_id"]), {"next_passage_id": passage_id})
        self.store.merge(
            path, {"status": "DONE", "passage_id": passage_id, "processed_at": self._now()}
        )

    def _now(self) -> str:
        return iso_utc(self.clock())
