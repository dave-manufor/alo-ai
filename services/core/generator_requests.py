"""Pre-generating the child's next story (PRD 4.5, SDD 11): the Passage Generator's
handler for plan.ready.

The Reading Coach's queue_story writes story_requests/story_{session_id} before it
publishes plan.ready. This generates the story within PREGENERATE_DEADLINE_MS and with no
bank fallback, stores it at passages/gen_next_{session_id}, sets
children/{child_id}.next_passage_id (which the Account service passes to the next session
as passage_id) and marks the request DONE. A story that fails the gate or runs past the
bound marks the request FAILED, and the child simply gets a live story next time.

Nothing but a session using it clears next_passage_id, so a child who read
gen_next_{N-1} would read it again in session N+1 if session N produced no new story
(that would inflate WCPM, accuracy and comprehension). So the field is cleared on FAILED
and when session N has no request at all.

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

from .generator.pipeline import (
    DeadlineExceeded,
    GateFailed,
    Generator,
    Request,
    choose_listening,
)
from .grader import paths

log = logging.getLogger(__name__)

# [CAL] The most one pre-generation may take. The worst case is about 45 s (2 attempts x
# a 12 s Writer, 5 s for Critic A and B in parallel and 5 s for C), so a slow model is cut
# short and this stays inside Core's push ack deadline (about 120 s, set in Terraform).
PREGENERATE_DEADLINE_MS = 60_000


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
            self._forget_next_story(session_id)
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
                        deadline_ms=PREGENERATE_DEADLINE_MS,
                    ),
                    passage_id,
                    choose_listening(
                        self.store.where("passages", "mode", "LISTEN"),
                        request["arl"],
                        length_profile,
                    ),
                )
            except (GateFailed, DeadlineExceeded) as error:
                log.info("no next story for %s: %s", session_id, error)
                # The child keeps no old story to read again; then the request is marked.
                self.store.merge(paths.child(request["child_id"]), {"next_passage_id": None})
                self.store.merge(path, {"status": "FAILED", "processed_at": self._now()})
                return
            aloai_contracts.PASSAGE.validate(generated.passage)
            self.store.create(passage_path, generated.passage)
        self.store.merge(paths.child(request["child_id"]), {"next_passage_id": passage_id})
        self.store.merge(
            path, {"status": "DONE", "passage_id": passage_id, "processed_at": self._now()}
        )

    def _forget_next_story(self, session_id: str) -> None:
        """With no request there is no new story: the child must not be given the one
        this session read. The child comes from the session, as there is no request."""
        session = self.store.get(paths.session(session_id))
        if session is None:
            log.warning("no session %s to find the child of", session_id)
            return
        self.store.merge(paths.child(session["child_id"]), {"next_passage_id": None})

    def _now(self) -> str:
        return iso_utc(self.clock())
