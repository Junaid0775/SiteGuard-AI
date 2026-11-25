"""End-to-end tests with the real trained model (skipped if best.pt is missing)."""

from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from src.compliance.compliance_analyzer import ComplianceAnalyzer
from src.compliance.worker_association import iou
from src.detection.camera_processor import LiveFrameProcessor
from src.detection.image_processor import inspect_image, load_image
from src.detection.video_processor import InvalidVideoError, process_video
from src.events.event_manager import EventManager
from src.events.event_store import EventStore
from src.utils.paths import DATA_DIR

TEST_VIDEO = DATA_DIR / "test_media" / "test_site_clip.mp4"


def test_real_image_inspection(detector, sample_val_image):
    insp = inspect_image(load_image(sample_val_image), detector, ComplianceAnalyzer())
    assert insp.annotated.shape == insp.image.shape
    assert len(insp.detections) > 0
    assert sum(insp.compliance.counts.values()) == len(insp.compliance.workers)


def test_real_video_processing_with_dedup(detector, tmp_path):
    if not TEST_VIDEO.exists():
        pytest.skip("run scripts/make_test_video.py first")
    store = EventStore(tmp_path / "ev.db")
    em = EventManager(store, "video", TEST_VIDEO.name, save_evidence=False)
    out = tmp_path / "out.mp4"
    progress_calls = []
    s = process_video(TEST_VIDEO, out, detector, ComplianceAnalyzer(), em, frame_stride=5, max_frames=90,
                      progress=lambda p, t: progress_calls.append(p))
    assert s.frames_read == 90 and s.frames_processed == 18
    assert s.stopped_early is True
    assert progress_calls and progress_calls[-1] == 1.0
    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened() and int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 90
    cap.release()
    # Repeated frames of the same scene must not create one event per frame:
    # no two events may share a category and an overlapping worker box inside the cooldown.
    assert s.suppressed_repeats > 0
    for i, a in enumerate(s.events):
        for b in s.events[i + 1:]:
            if a.category == b.category and iou(a.worker_box, b.worker_box) >= em.match_iou:
                assert abs(b.media_time_s - a.media_time_s) >= em.cooldown, (a, b)
    assert store.count_events() == len(s.events)


def test_invalid_video_rejected(detector, tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(InvalidVideoError):
        process_video(bad, tmp_path / "o.mp4", detector, ComplianceAnalyzer())


def test_live_frame_processor_on_real_frames(detector, sample_val_image, tmp_path):
    proc = LiveFrameProcessor(detector, ComplianceAnalyzer(), EventStore(tmp_path / "live.db"), process_every_n=2, image_size=480)
    frame = load_image(sample_val_image)
    for _ in range(6):
        out = proc.process(frame)
        assert out.shape == frame.shape
    snap = proc.snapshot()
    assert snap["frames_received"] == 6 and snap["frames_analysed"] == 3
    assert snap["error"] is None
