"""Report assembly (SDD 7 step 6).

The report needs the reconciled grading and the Phase 1 telemetry, so assembly runs
after both final grading and phase1.scored, and only the second of the two finds
both. The report is created only if absent, so it is written once however often
either event is delivered; report.ready is published whenever the report exists,
and consumers drop duplicates.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .. import contracts
from ..events import Publisher, envelope
from ..store import Store, require
from . import paths
from .report import ReportInputs, build_report


def _now() -> datetime:
    return datetime.now(UTC)


def _new_event_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class ReportAssembler:
    store: Store
    publisher: Publisher
    clock: Callable[[], datetime] = _now
    new_event_id: Callable[[], str] = _new_event_id

    def assemble(self, session_id: str) -> bool:
        """True if the report exists after this call."""
        grading = self.store.get(paths.grading(session_id))
        telemetry = self.store.get(paths.telemetry(session_id))
        if grading is None or telemetry is None:
            return False
        report = self.store.get(paths.report(session_id))
        if report is None:
            report = self._write(session_id, grading, telemetry)
        data = {
            "session_id": session_id,
            "report_ref": paths.report(session_id),
            "profile": report["profile"]["code"],
            "provisional": report["profile"]["provisional"],
        }
        self.publisher.publish(
            envelope(
                "report.ready", session_id, data, event_id=self.new_event_id(), now=self.clock()
            )
        )
        return True

    def _write(self, session_id: str, grading: dict, telemetry: dict) -> dict:
        session = require(self.store, paths.session(session_id))
        report = build_report(
            ReportInputs(
                session_id=session_id,
                session=session,
                child=require(self.store, paths.child(session["child_id"])),
                passage=require(self.store, paths.passage(session["passage_id"])),
                telemetry=telemetry,
                grading=grading,
                quick=self.store.get(paths.quick_result(session_id)),
                previous_reported_arl=self._previous_reported_arl(session_id, session["child_id"]),
                now=self.clock(),
            )
        )
        contracts.READING_REPORT.validate(report)
        if not self.store.create(paths.report(session_id), report):
            return require(self.store, paths.report(session_id))
        self.store.merge(
            paths.child(session["child_id"]),
            {"next_passage_arl": report["level"]["next_passage_arl"]},
        )
        return report

    def _previous_reported_arl(self, session_id: str, child_id: str) -> int | None:
        earlier = [
            report
            for report in self.store.where("reports", "child_id", child_id)
            if report["session_id"] != session_id
        ]
        if not earlier:
            return None
        return max(earlier, key=lambda report: report["timestamp_iso"])["level"]["reported_arl"]
