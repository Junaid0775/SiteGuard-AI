"""Uploaded-video inspection with source-frame synchronisation (R1).

Every output frame shows ONLY the detections computed on that same source frame.

Sampling policy (explicit, never silent):
* `frame_stride = 1` (default): every frame is analysed.
* `frame_stride = N > 1`: frames 0, N, 2N, ... are analysed. Frames in between are
  written WITHOUT boxes and tagged "not analysed", instead of reusing old boxes.

A per-frame integrity log (`<output>.frames.csv`) records, for every source frame,
its index, video time, whether it was analysed, the frame its boxes came from (always
itself, or empty), the number of detections and the inference time.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from src.compliance.compliance_analyzer import ComplianceAnalyzer
from src.detection.annotate import draw_compliance
from src.detection.detector import PPEDetector
from src.events.event_manager import EventManager
from src.events.event_store import SafetyEvent
from src.utils.paths import load_settings

SUPPORTED_VIDEO_TYPES = ("mp4", "mov", "avi", "mkv", "m4v")


class InvalidVideoError(ValueError):
    pass


@dataclass
class VideoSummary:
    output_path: Path
    fps: float
    frames_total: int
    frames_read: int
    frames_processed: int
    seconds_elapsed: float
    frame_stride: int = 1
    frames_not_analysed: int = 0
    person_detections: int = 0
    class_counts: dict[str, int] = field(default_factory=dict)
    worker_status_frames: dict[str, int] = field(default_factory=dict)
    events: list[SafetyEvent] = field(default_factory=list)
    suppressed_repeats: int = 0
    stopped_early: bool = False
    frame_log_path: Path | None = None
    inference_ms: dict | None = None
    output_size: tuple[int, int] | None = None

    @property
    def sampling_policy(self) -> str:
        if self.frame_stride == 1:
            return "every frame analysed"
        return f"every {self.frame_stride}th frame analysed; other frames shown without boxes (tagged 'not analysed')"


def open_writer(path: Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    """Prefer H.264 ('avc1') so browsers can play the file; fall back to mp4v."""
    for fourcc in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), fps, size)
        if writer.isOpened():
            return writer
        writer.release()
    raise RuntimeError("Could not open a video writer (no avc1/mp4v support)")


def tag_not_analysed(frame: np.ndarray) -> np.ndarray:
    out = frame.copy()
    scale = max(0.45, min(1.0, out.shape[1] / 1800))
    text = "not analysed (sampling)"
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    cv2.rectangle(out, (6, 6), (14 + tw, 14 + th + base), (90, 90, 90), -1)
    cv2.putText(out, text, (10, 10 + th), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def process_video(
    input_path: str | Path,
    output_path: str | Path,
    detector: PPEDetector,
    analyzer: ComplianceAnalyzer,
    event_manager: EventManager | None = None,
    frame_stride: int | None = None,
    max_frames: int | None = None,
    confidence: float | None = None,
    image_size: int | None = None,
    progress: Callable[[float, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    write_frame_log: bool = True,
) -> VideoSummary:
    cfg = load_settings()["video"]
    stride = max(1, int(frame_stride or cfg.get("frame_stride") or 1))
    limit = int(max_frames or cfg["max_frames"])
    input_path, output_path = Path(input_path), Path(output_path)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise InvalidVideoError("The video could not be opened (unsupported codec or corrupted file).")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if fps <= 1 or fps > 240:
        fps = 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise InvalidVideoError("The video contains no readable frames.")

    h, w = frame.shape[:2]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_writer(output_path, fps, (w, h))
    summary = VideoSummary(output_path, fps, total, 0, 0, 0.0, frame_stride=stride, output_size=(w, h))
    frame_log: list[dict] = []
    inference_ms: list[float] = []
    start = time.time()
    index = 0
    try:
        while ok and frame is not None:
            if index >= limit or (should_stop and should_stop()):
                summary.stopped_early = True
                break
            media_t = index / fps
            if index % stride == 0:
                t0 = time.perf_counter()
                detections = detector.detect(frame, confidence=confidence, image_size=image_size)
                result = analyzer.analyze(detections)
                inf_ms = (time.perf_counter() - t0) * 1000
                inference_ms.append(inf_ms)
                annotated = draw_compliance(frame, result)  # boxes of frame `index` on frame `index`
                summary.frames_processed += 1
                for d in detections:
                    summary.class_counts[d.class_name] = summary.class_counts.get(d.class_name, 0) + 1
                summary.person_detections += len(result.workers)
                for worker in result.workers:
                    summary.worker_status_frames[worker.status] = summary.worker_status_frames.get(worker.status, 0) + 1
                if event_manager is not None:
                    summary.events += event_manager.process(result, now=media_t, evidence_frame=annotated, media_time_s=media_t)
                frame_log.append({"frame_index": index, "media_time_s": round(media_t, 4), "analysed": 1,
                                  "boxes_from_frame": index, "detections": len(detections), "inference_ms": round(inf_ms, 2)})
            else:
                annotated = tag_not_analysed(frame)
                summary.frames_not_analysed += 1
                frame_log.append({"frame_index": index, "media_time_s": round(media_t, 4), "analysed": 0,
                                  "boxes_from_frame": "", "detections": "", "inference_ms": ""})
            writer.write(annotated)
            index += 1
            summary.frames_read = index
            if progress and (index % 10 == 0):
                frac = min(1.0, index / total) if total else 0.0
                progress(frac, f"Frame {index}/{total or '?'} - {summary.frames_processed} analysed")
            ok, frame = cap.read()
    finally:
        cap.release()
        writer.release()
    summary.seconds_elapsed = round(time.time() - start, 2)
    if inference_ms:
        v = np.asarray(inference_ms)
        summary.inference_ms = {"mean": round(float(v.mean()), 2), "median": round(float(np.median(v)), 2),
                                "p95": round(float(np.percentile(v, 95)), 2), "max": round(float(v.max()), 2), "n": int(len(v))}
    if event_manager is not None:
        summary.suppressed_repeats = event_manager.suppressed
    if write_frame_log:
        log_path = output_path.with_suffix(output_path.suffix + ".frames.csv")
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=["frame_index", "media_time_s", "analysed", "boxes_from_frame", "detections", "inference_ms"])
            wr.writeheader()
            wr.writerows(frame_log)
        summary.frame_log_path = log_path
    if progress:
        progress(1.0, f"Done: {summary.frames_read} frames, {summary.frames_processed} analysed")
    return summary
