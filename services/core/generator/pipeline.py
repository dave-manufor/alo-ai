"""The Story Writer + Critic loop (PRD 4.5 G1-G4, SDD 5): plain code, not an agent
workflow, because the order of the checks and the deadline must be exact.

1. Check every safe detail again (G1).
2. The Writer writes a story (G2).
3. The code checks run (G4). Only if they all pass does the Critic run.
4. If anything failed, one retry with the failed checks as feedback, and only while the
   deadline leaves room for a whole second attempt.
5. Build the passage document in code (G3).

The generator never returns a bank READ passage. A failed gate raises GateFailed and a
passed deadline raises DeadlineExceeded; the Session Agent then chooses the bank passage
and flags FALLBACK_PASSAGE. Making the clips (G5) and storing the passage come after.
"""

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from spacy.language import Language

from . import artifact, clips, critic, data, gate, textlevel, writer
from .data import Taxonomy
from .detail import safe_details
from .gate import Check
from .models import Model, ModelError, UpstreamErrors
from .names import Blocklist, NameList

# passage.schema.json: exact item counts per length profile (#25); 4 accepts az:// clip URIs.
PASSAGE_SCHEMA_VERSION = 4
WRITER_TIMEOUT_S = 12.0  # [CAL] one Writer call, at most
CRITIC_TIMEOUT_S = 5.0  # [CAL] each Critic call, at most
RETRY_MIN_S = 10.0  # [CAL] the time a second attempt needs: a Writer and three Critic calls
TAIL_S = 3.0  # [CAL] kept back from the deadline for the clips and the store write
MAX_ATTEMPTS = 2  # one retry (PRD 4.5 G4)


class GateFailed(Exception):
    def __init__(self, checks: Sequence[Check], attempts: int) -> None:
        super().__init__(gate.feedback(checks) or "the gate failed")
        self.checks = list(checks)
        self.attempts = attempts


class DeadlineExceeded(Exception):
    pass


def _details(body: Mapping) -> tuple[str, ...]:
    """The things the child named: `details`, plus the older single `detail` if sent."""
    found = list(body.get("details") or [])
    if body.get("detail") is not None:
        found.append(body["detail"])
    return tuple(dict.fromkeys(found))  # once each, in order


@dataclass(frozen=True)
class Request:
    """The fields of a passage_generate_request the loop uses. deadline_ms is None for a
    pre-generated next story, which has no session waiting on it."""

    session_id: str
    target_arl: int
    tags: tuple[str, ...]
    length_profile: str
    voice_profile_id: str
    deadline_ms: int | None
    details: tuple[str, ...] = ()
    genre_hint: str | None = None

    @classmethod
    def from_contract(cls, body: Mapping) -> "Request":
        return cls(
            session_id=body["session_id"],
            target_arl=body["target_arl"],
            tags=tuple(body["tags"]),
            length_profile=body["length_profile"],
            voice_profile_id=body["voice_profile_id"],
            deadline_ms=body["deadline_ms"],
            details=_details(body),
            genre_hint=body.get("genre_hint"),
        )


@dataclass(frozen=True)
class Generated:
    passage: dict
    attempts: int
    estimated_arl: float


class _Clock:
    def __init__(self, monotonic: Callable[[], float], deadline_ms: int | None) -> None:
        self._monotonic = monotonic
        self._end = None if deadline_ms is None else monotonic() + deadline_ms / 1000 - TAIL_S

    def remaining(self) -> float | None:
        return None if self._end is None else self._end - self._monotonic()

    def timeout(self, cap: float) -> float:
        """The time the next call may take. Raises DeadlineExceeded when none is left."""
        remaining = self.remaining()
        if remaining is None:
            return cap
        if remaining <= 0:
            raise DeadlineExceeded("the deadline passed")
        return min(cap, remaining)

    def allows_retry(self) -> bool:
        remaining = self.remaining()
        return remaining is None or remaining >= RETRY_MIN_S

    def expired(self) -> bool:
        remaining = self.remaining()
        return remaining is not None and remaining <= 0


@dataclass
class Generator:
    model: Model
    nlp: Language
    clips_bucket: str  # the shared clip store (PRD 4.5 G5)
    tts_version: str
    scheme: str = "gs"  # gs on Google Cloud, az on Azure: how the word clips are named
    names: NameList = field(default_factory=data.names)
    blocklist: Blocklist = field(default_factory=data.blocklist)
    taxonomy: Taxonomy = field(default_factory=data.taxonomy)
    monotonic: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def generate(self, request: Request, passage_id: str, listening_passage_id: str) -> Generated:
        clock = _Clock(self.monotonic, request.deadline_ms)
        try:
            return self._generate(request, passage_id, listening_passage_id, clock)
        except UpstreamErrors as error:
            if clock.expired():
                raise DeadlineExceeded("a model call ran past the deadline") from error
            raise

    def _generate(
        self, request: Request, passage_id: str, listening_passage_id: str, clock: _Clock
    ) -> Generated:
        details = safe_details(request.details, self.nlp, self.names, self.blocklist)
        brief = writer.Brief(
            session_id=request.session_id,
            target_arl=request.target_arl,
            length_profile=request.length_profile,
            genre=self.taxonomy.genre(list(request.tags), request.genre_hint),
            topics=tuple(self.taxonomy.topic(tag) for tag in request.tags),
            details=details,
            names=self.names,
        )
        checks: list[Check] = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1 and not clock.allows_retry():
                raise GateFailed(checks, attempt - 1)
            brief = replace(brief, attempt=attempt)
            story, checks = self._attempt(brief, clock)
            if gate.passed(checks):
                return self._generated(
                    story, brief, request, passage_id, listening_passage_id, attempt, checks
                )
            brief = replace(brief, feedback=gate.feedback(checks))
        raise GateFailed(checks, MAX_ATTEMPTS)

    def _attempt(self, brief: writer.Brief, clock: _Clock) -> tuple[dict | None, list[Check]]:
        try:
            story = writer.write(self.model, brief, clock.timeout(WRITER_TIMEOUT_S))
        except ModelError as error:
            return None, [Check("writer_output", False, str(error))]
        request = gate.Request(brief.target_arl, brief.length_profile)
        checks = gate.run(story, request, self.nlp, self.names, self.blocklist)
        if not gate.passed(checks):
            return story, checks
        try:
            checks += critic.review(
                self.model,
                story,
                brief.session_id,
                brief.attempt,
                lambda: clock.timeout(CRITIC_TIMEOUT_S),
            )
        except ModelError as error:
            checks.append(Check("critic_output", False, f"the questions were not checked: {error}"))
        return story, checks

    def _generated(
        self,
        story: dict,
        brief: writer.Brief,
        request: Request,
        passage_id: str,
        listening_passage_id: str,
        attempts: int,
        checks: Sequence[Check],
    ) -> Generated:
        sentences = story["sentences"]
        estimated = round(textlevel.estimate_arl(textlevel.features(sentences, self.names)), 2)
        clip_uri = clips.word_clip_uri(
            self.clips_bucket, request.voice_profile_id, self.tts_version, self.scheme
        )
        tokens = artifact.build_tokens(sentences, self.nlp, self.names, clip_uri)
        passage = {
            "schema_version": PASSAGE_SCHEMA_VERSION,
            "passage_id": passage_id,
            "title": story["title"],
            "mode": "READ",
            "source": "GENERATED",
            "topic_tags": list(request.tags),
            "generation": {
                "model": writer.MODEL,
                "prompt_version": f"{writer.PROMPT_VERSION}+{critic.PROMPT_VERSION}",
                "target_arl": request.target_arl,
                "estimated_arl": estimated,
                "attempts": attempts,
                "gate_results": gate.results(checks),
                "created_at": self.now().isoformat().replace("+00:00", "Z"),
            },
            "genre": brief.genre,
            "arl_level": request.target_arl,
            "word_count": len(tokens),
            "text_content": artifact.text_content(sentences),
            "voice_profile_id": request.voice_profile_id,
            "length_profile": request.length_profile,
            "tokens": tokens,
            "propositions": story["propositions"],
            "items": artifact.artifact_items(story["items"]),
            "paired_listening_passage_id": listening_passage_id,
        }
        return Generated(passage, attempts, estimated)


def choose_listening(passages: Sequence[Mapping], arl: int, length_profile: str) -> str:
    """The bank LISTEN passage to pair with a generated story: the same length profile,
    then the nearest level, the easier one on a tie (PRD 4.5)."""
    fitting = [
        p for p in passages if p["mode"] == "LISTEN" and p.get("length_profile") == length_profile
    ]
    if not fitting:
        raise LookupError(f"no {length_profile} listening passage in the bank")
    best = min(fitting, key=lambda p: (abs(p["arl_level"] - arl), p["arl_level"], p["passage_id"]))
    return best["passage_id"]
