"""Live camera processing with source-frame synchronisation (R1).

Architecture (traced in REPORT-010 §4.3)
-----------------------------------------
Browser camera -> WebRTC -> streamlit-webrtc worker thread. That thread collects
every frame that arrived since its previous call and hands the list to our
`queued_video_frames_callback`, which calls `LiveFrameProcessor.process_queue`.

Rules enforced here
-------------------
1. Every frame gets a `FramePacket` with a session id, a unique frame id and the
   monotonic time it reached SiteGuard.
2. Every inference result is a `DetectionPacket` that keeps the id of its source
   frame and its own start/end timestamps.
3. A result is rendered ONLY on its source frame. `render()` refuses any other
   frame (`StaleResultError`). Old boxes are never drawn on a newer frame.
4. Latest-frame policy: when several frames are queued, only the newest is
   analysed; older ones are dropped and counted (`frames_dropped_queue`).
5. Optional reduced analysis (`process_every_n > 1`): frames that are not analysed
   are NOT drawn with old boxes; the last correctly annotated frame is shown again
   (counted as `frames_held`). Default is 1 = analyse every delivered frame.
6. A new session (camera restart) gets a new session id; results and held frames of
   the old session can never be shown in the new one.
7. Inference errors are caught: the raw frame is shown (no boxes), the error is
   counted, and processing continues.
All counters and timing buffers are bounded.

`OpenCVFrameSource` is a small helper for non-browser sources (camera index or a
future RTSP URL). It is not used by the browser webcam.
"""

from __future__ import annotations

import itertools
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

import cv2
import numpy as np

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceResult
from src.detection.annotate import draw_compliance
from src.detection.detector import Detection, PPEDetector
from src.events.event_manager import EventManager
from src.events.event_store import EventStore, SafetyEvent
from src.utils.paths import load_settings

TIMING_WINDOW = 600  # bounded number of samples kept for latency / rate statistics


class StaleResultError(RuntimeError):
    """Raised when a result would be drawn on a frame other than its source frame."""


@dataclass(frozen=True)
class FramePacket:
    session_id: str
    frame_id: int                 # unique and increasing within a session
    received_at: float            # time.monotonic() when the frame reached SiteGuard
    media_time_s: float | None    # WebRTC presentation time (pts * time_base), if known
    frame: np.ndarray             # BGR; treated as read-only


@dataclass(frozen=True)
class DetectionPacket:
    session_id: str
    source_frame_id: int
    inference_started_at: float
    inference_completed_at: float
    detections: tuple[Detection, ...]
    compliance: ComplianceResult | None
    error: str | None = None

    @property
    def inference_ms(self) -> float:
        return (self.inference_completed_at - self.inference_started_at) * 1000


@dataclass
class LiveStats:
    frames_received: int = 0        # frames that reached SiteGuard (including dropped ones)
    frames_dropped_queue: int = 0   # superseded by a newer queued frame (latest-frame policy)
    frames_analysed: int = 0        # inference executed on this exact frame
    frames_held: int = 0            # reduced-analysis mode: previous annotated frame shown again
    frames_rendered: int = 0        # frames returned for display
    errors: int = 0
    last_inference_ms: float = 0.0
    person_detections: int = 0
    class_counts: dict[str, int] = field(default_factory=dict)
    last_detections: list[dict] = field(default_factory=list)
    last_worker_rows: list[dict] = field(default_factory=list)
    recent_events: deque = field(default_factory=lambda: deque(maxlen=20))
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    inference_ms: deque = field(default_factory=lambda: deque(maxlen=TIMING_WINDOW))
    receive_to_render_ms: deque = field(default_factory=lambda: deque(maxlen=TIMING_WINDOW))
    displayed_result_age_ms: deque = field(default_factory=lambda: deque(maxlen=TIMING_WINDOW))
    received_times: deque = field(default_factory=lambda: deque(maxlen=TIMING_WINDOW))
    analysed_times: deque = field(default_factory=lambda: deque(maxlen=TIMING_WINDOW))
    rendered_times: deque = field(default_factory=lambda: deque(maxlen=TIMING_WINDOW))


def _summary(values) -> dict | None:
    if not values:
        return None
    v = np.asarray(values, float)
    return {"mean": round(float(v.mean()), 2), "median": round(float(np.median(v)), 2),
            "p95": round(float(np.percentile(v, 95)), 2), "max": round(float(v.max()), 2), "n": int(len(v))}


def _rate(times) -> float | None:
    """Measured events per second over the bounded window (needs at least 2 samples)."""
    if len(times) < 2:
        return None
    span = times[-1] - times[0]
    return round((len(times) - 1) / span, 2) if span > 0 else None


class LiveFrameProcessor:
    def __init__(
        self,
        detector: PPEDetector,
        analyzer: ComplianceAnalyzer,
        store: EventStore | None,
        process_every_n: int | None = None,
        image_size: int | None = None,
        confidence: float | None = None,
        cooldown_seconds: float | None = None,
        source_name: str = "browser webcam",
        min_consecutive_hits: int | None = None,
    ) -> None:
        live_cfg = load_settings()["live"]
        self.detector = detector
        self.analyzer = analyzer
        self.every_n = max(1, int(process_every_n or live_cfg.get("process_every_n_frames") or 1))
        # R2: one authoritative inference size. None -> the detector's configured size (inference.image_size).
        override = image_size if image_size is not None else live_cfg.get("image_size")
        self.image_size = int(override) if override else int(detector.image_size)
        self.confidence = confidence
        self.store = store
        self.source_name = source_name
        self.cooldown_seconds = cooldown_seconds
        self.min_consecutive_hits = min_consecutive_hits
        self._lock = threading.Lock()
        self.closed = False
        self._start_session()

    # ---------------------------------------------------------------- sessions
    def _start_session(self) -> None:
        self.session_id = uuid.uuid4().hex[:12]
        self._ids = itertools.count(1)
        self.events = EventManager(self.store, "live_camera", self.source_name, cooldown_seconds=self.cooldown_seconds,
                                   min_consecutive_hits=self.min_consecutive_hits)
        self.stats = LiveStats()
        self._last_result: ComplianceResult | None = None
        self._last_packet: DetectionPacket | None = None
        self._held: tuple[FramePacket, np.ndarray] | None = None  # last correctly annotated frame

    def reset_session(self) -> str:
        """Start a new session (camera restart). Nothing from the old session can be shown afterwards."""
        with self._lock:
            self._start_session()
            self.closed = False
            return self.session_id

    def close(self) -> None:
        """Stop: drop references to frames/results so nothing can be shown or leak into a later session."""
        with self._lock:
            self._held = None
            self._last_result = None
            self._last_packet = None
            self.closed = True

    # ----------------------------------------------------------------- packets
    def new_packet(self, frame_bgr: np.ndarray, media_time_s: float | None = None) -> FramePacket:
        with self._lock:
            fid = next(self._ids)
            self.stats.frames_received += 1
            now = time.monotonic()
            self.stats.received_times.append(now)
            return FramePacket(self.session_id, fid, now, media_time_s, frame_bgr)

    def infer(self, packet: FramePacket) -> DetectionPacket:
        """Run detection + compliance on exactly this frame. Never raises."""
        t0 = time.monotonic()
        try:
            detections = self.detector.detect(packet.frame, confidence=self.confidence, image_size=self.image_size)
            compliance = self.analyzer.analyze(detections)
            return DetectionPacket(packet.session_id, packet.frame_id, t0, time.monotonic(), tuple(detections), compliance)
        except Exception as exc:  # keep the stream alive and report the problem
            return DetectionPacket(packet.session_id, packet.frame_id, t0, time.monotonic(), (), None, f"{type(exc).__name__}: {exc}")

    def render(self, packet: FramePacket, result: DetectionPacket) -> np.ndarray:
        """Draw `result` on its own source frame only."""
        if result.session_id != packet.session_id or result.source_frame_id != packet.frame_id:
            raise StaleResultError(
                f"result of frame {result.session_id}/{result.source_frame_id} cannot be drawn on frame "
                f"{packet.session_id}/{packet.frame_id}")
        if result.compliance is None:  # inference failed: show the frame without boxes
            return packet.frame
        return draw_compliance(packet.frame, result.compliance)

    # -------------------------------------------------------------- processing
    def process_queue(self, frames: list[np.ndarray], media_times: list[float | None] | None = None) -> np.ndarray:
        """Latest-frame policy for a batch of queued frames: analyse only the newest, count the rest as dropped."""
        if not frames:
            raise ValueError("process_queue() needs at least one frame")
        media_times = media_times or [None] * len(frames)
        return self.process_latest(frames[-1], dropped=len(frames) - 1, media_time_s=media_times[-1])

    def process_latest(self, frame_bgr: np.ndarray, dropped: int = 0, media_time_s: float | None = None) -> np.ndarray:
        """Entry point for the WebRTC queued-frames callback: `dropped` older frames were superseded by this one.

        The superseded frames are never decoded or analysed; they consume frame ids (so ids follow arrival
        order) and are counted in `frames_dropped_queue`."""
        if dropped > 0:
            with self._lock:
                now = time.monotonic()
                for _ in range(dropped):
                    next(self._ids)
                    self.stats.received_times.append(now)
                self.stats.frames_received += dropped
                self.stats.frames_dropped_queue += dropped
        return self.process(frame_bgr, media_time_s)

    def process(self, frame_bgr: np.ndarray, media_time_s: float | None = None) -> np.ndarray:
        """Process one frame and return the image to display. Never raises, never shows stale boxes."""
        if self.closed:
            return frame_bgr
        packet = self.new_packet(frame_bgr, media_time_s)
        if (packet.frame_id - 1) % self.every_n != 0:
            return self._show_held_or_raw(packet)
        result = self.infer(packet)
        image = self.render(packet, result)
        with self._lock:  # a session reset/stop while this frame was in flight discards its result entirely
            valid = packet.session_id == self.session_id and not self.closed
        if not valid:
            return frame_bgr
        now = time.monotonic()
        new_events = []
        if result.compliance is not None:
            new_events = self.events.process(result.compliance, now=now, evidence_frame=image)
        with self._lock:
            s = self.stats
            s.frames_analysed += 1
            s.frames_rendered += 1
            s.analysed_times.append(result.inference_completed_at)
            s.rendered_times.append(now)
            s.inference_ms.append(result.inference_ms)
            s.receive_to_render_ms.append((now - packet.received_at) * 1000)
            s.displayed_result_age_ms.append((now - packet.received_at) * 1000)
            s.last_inference_ms = result.inference_ms
            self._last_packet = result
            if result.error:
                s.errors += 1
                s.error = result.error
                self._held = None  # never hold a frame whose analysis failed
            else:
                s.error = None
                self._last_result = result.compliance
                self._held = (packet, image)
                s.person_detections += len(result.compliance.workers)
                for d in result.detections:
                    s.class_counts[d.class_name] = s.class_counts.get(d.class_name, 0) + 1
                s.last_detections = [{"Class": d.class_name, "Confidence": round(d.confidence, 2)} for d in result.detections]
                s.last_worker_rows = result.compliance.table_rows()
                for e in new_events:
                    s.recent_events.appendleft(e)
        return image

    def _show_held_or_raw(self, packet: FramePacket) -> np.ndarray:
        """Reduced-analysis mode: show the last annotated frame as it was (its boxes belong to it)."""
        now = time.monotonic()
        with self._lock:
            s = self.stats
            s.frames_rendered += 1
            s.rendered_times.append(now)
            if self._held is not None and self._held[0].session_id == packet.session_id:
                held_packet, held_image = self._held
                s.frames_held += 1
                s.displayed_result_age_ms.append((now - held_packet.received_at) * 1000)
                return held_image
        return packet.frame  # nothing analysed yet in this session: raw frame, no boxes

    # --------------------------------------------------------------- reporting
    def snapshot(self) -> dict:
        with self._lock:
            s = self.stats
            return {
                "session_id": self.session_id,
                "inference_imgsz": self.image_size,
                "process_every_n": self.every_n,
                "frames_received": s.frames_received,
                "frames_dropped_queue": s.frames_dropped_queue,
                "frames_analysed": s.frames_analysed,
                "frames_held": s.frames_held,
                "frames_rendered": s.frames_rendered,
                "errors": s.errors,
                "last_inference_ms": round(s.last_inference_ms, 1),
                "inference_ms": _summary(s.inference_ms),
                "receive_to_render_ms": _summary(s.receive_to_render_ms),
                "displayed_result_age_ms": _summary(s.displayed_result_age_ms),
                "received_fps": _rate(s.received_times),
                "analysed_fps": _rate(s.analysed_times),
                "rendered_fps": _rate(s.rendered_times),
                "person_detections": s.person_detections,
                "class_counts": dict(s.class_counts),
                "last_detections": list(s.last_detections),
                "last_worker_rows": list(s.last_worker_rows),
                "recent_events": list(s.recent_events),
                "error": s.error,
                "running_seconds": round(time.time() - s.started_at, 1),
            }


class OpenCVFrameSource:
    """Read frames from a local camera index or a stream URL (future RTSP support)."""

    def __init__(self, source: int | str = 0) -> None:
        self.source = source
        self.cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.source)
        return bool(self.cap.isOpened())

    def read(self) -> np.ndarray | None:
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def recent_event_rows(events: list[SafetyEvent]) -> list[dict]:
    return [{"Time": e.timestamp, "Category": e.category, "Confidence": e.confidence, "Worker": e.worker_ref} for e in events]
