"""Turn compliance results into deduplicated safety events.

Why deduplication matters: a worker without a helmet standing in front of a
camera for 10 seconds appears in hundreds of frames. Without deduplication that
would be hundreds of events.

How it works (no identity tracking - only box overlap):
1. Every potential violation becomes a *candidate* keyed by its category and the
   worker box.
2. In video / live mode, a candidate must be seen in `min_consecutive_hits`
   processed frames (matched by IoU >= `match_iou`) before an event is raised.
   Single images need only one hit.
3. After an event is raised, any new candidate with the same category and an
   overlapping worker box (IoU >= `match_iou`) is suppressed for
   `cooldown_seconds`.
4. Candidates not seen for `candidate_timeout_seconds` are forgotten.

Time is passed in by the caller: video time for uploaded videos, wall-clock
(monotonic) time for the live camera.
"""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from src.compliance.compliance_analyzer import NEGATIVE_CLASS, ComplianceResult
from src.compliance.worker_association import iou
from src.events.event_store import EventStore, SafetyEvent
from src.utils.paths import load_settings, project_path


@dataclass
class _Candidate:
    category: str
    box: tuple[float, float, float, float]
    hits: int
    last_seen: float
    best_conf: float
    worker_ref: str


@dataclass
class _Recent:
    category: str
    box: tuple[float, float, float, float]
    time: float


def new_event_id() -> str:
    return f"EVT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


class EventManager:
    def __init__(
        self,
        store: EventStore | None,
        source_type: str,
        source_name: str = "",
        cooldown_seconds: float | None = None,
        match_iou: float | None = None,
        min_consecutive_hits: int | None = None,
        candidate_timeout_seconds: float | None = None,
        evidence_dir: str | Path | None = None,
        save_evidence: bool = True,
    ) -> None:
        cfg = load_settings()["events"]
        self.store = store
        self.source_type = source_type
        self.source_name = source_name
        self.cooldown = float(cfg["cooldown_seconds"] if cooldown_seconds is None else cooldown_seconds)
        self.match_iou = float(cfg["match_iou"] if match_iou is None else match_iou)
        default_hits = 1 if source_type == "image" else int(cfg["min_consecutive_hits"])
        self.min_hits = int(default_hits if min_consecutive_hits is None else min_consecutive_hits)
        self.timeout = float(cfg["candidate_timeout_seconds"] if candidate_timeout_seconds is None else candidate_timeout_seconds)
        # SITEGUARD_EVIDENCE_DIR lets tests and diagnostic scripts use throw-away evidence storage (like
        # SITEGUARD_EVENTS_DB for the database). Production runs leave it unset: events.evidence_dir from settings.
        self.evidence_dir = project_path(evidence_dir or os.environ.get("SITEGUARD_EVIDENCE_DIR") or cfg["evidence_dir"])
        self.save_evidence = save_evidence
        self._candidates: list[_Candidate] = []
        self._recent: list[_Recent] = []
        self._lock = threading.Lock()
        self.events_created: list[SafetyEvent] = []
        self.suppressed = 0

    def _in_cooldown(self, category: str, box, now: float) -> bool:
        return any(r.category == category and now - r.time < self.cooldown and iou(r.box, box) >= self.match_iou for r in self._recent)

    def process(self, result: ComplianceResult, now: float, evidence_frame: np.ndarray | None = None, media_time_s: float | None = None) -> list[SafetyEvent]:
        """Update candidates with one frame's result and return the NEW events (already stored)."""
        new_events: list[SafetyEvent] = []
        with self._lock:
            self._candidates = [c for c in self._candidates if now - c.last_seen <= self.timeout]
            self._recent = [r for r in self._recent if now - r.time < self.cooldown]
            matched_this_frame: set[int] = set()
            for worker in result.workers:
                for assessment in worker.violations:
                    category = NEGATIVE_CLASS[assessment.item]
                    box = worker.person.box
                    conf = float(assessment.confidence or 0.0)
                    cand = self._match_candidate(category, box, matched_this_frame)
                    if cand is None:
                        cand = _Candidate(category, box, 0, now, conf, worker.worker_ref)
                        self._candidates.append(cand)
                    matched_this_frame.add(id(cand))
                    cand.hits += 1
                    cand.box, cand.last_seen, cand.worker_ref = box, now, worker.worker_ref
                    cand.best_conf = max(cand.best_conf, conf)
                    if cand.hits < self.min_hits:
                        continue
                    if self._in_cooldown(category, box, now):
                        self.suppressed += 1
                        continue
                    event = self._create_event(cand, evidence_frame, media_time_s)
                    self._recent.append(_Recent(category, box, now))
                    new_events.append(event)
            self.events_created.extend(new_events)
        return new_events

    def _match_candidate(self, category: str, box, used: set[int]) -> _Candidate | None:
        best, best_iou = None, self.match_iou
        for c in self._candidates:
            if c.category != category or id(c) in used:
                continue
            o = iou(c.box, box)
            if o >= best_iou:
                best, best_iou = c, o
        return best

    def _create_event(self, cand: _Candidate, frame: np.ndarray | None, media_time_s: float | None) -> SafetyEvent:
        event_id = new_event_id()
        evidence_path = None
        if self.save_evidence and frame is not None:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            path = self.evidence_dir / f"{event_id}.jpg"
            evidence = frame.copy()
            x1, y1, x2, y2 = (int(v) for v in cand.box)
            cv2.rectangle(evidence, (x1, y1), (x2, y2), (0, 110, 255), max(3, frame.shape[1] // 300))
            cv2.imwrite(str(path), evidence, [cv2.IMWRITE_JPEG_QUALITY, 85])
            evidence_path = str(path)
        event = SafetyEvent(
            event_id=event_id,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            source_type=self.source_type,
            source_name=self.source_name,
            category=cand.category,
            confidence=round(cand.best_conf, 4),
            worker_ref=cand.worker_ref,
            worker_box=[round(v, 1) for v in cand.box],
            media_time_s=None if media_time_s is None else round(media_time_s, 2),
            evidence_path=evidence_path,
        )
        if self.store is not None:
            self.store.add_event(event)
        return event
