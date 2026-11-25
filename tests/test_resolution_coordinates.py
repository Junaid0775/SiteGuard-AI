"""R2 resolution parity and coordinate-transform tests (spec §5, §12.2)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.detection.annotate import draw_compliance
from src.detection.camera_processor import LiveFrameProcessor
from src.detection.detector import Detection
from src.events.event_manager import EventManager
from src.utils.paths import load_settings


class SizeRecorder:
    image_size = load_settings()["inference"]["image_size"]

    def __init__(self):
        self.sizes = []

    def detect(self, img, confidence=None, image_size=None):
        self.sizes.append(image_size)
        return []


def test_settings_have_one_authoritative_inference_size():
    s = load_settings()
    assert s["inference"]["image_size"] == 640
    assert s["live"]["image_size"] is None          # live follows inference.image_size
    assert s["live"]["process_every_n_frames"] == 1 and s["video"]["frame_stride"] == 1


def test_live_processor_infers_at_640():
    det = SizeRecorder()
    p = LiveFrameProcessor(det, ComplianceAnalyzer(), None)
    assert p.image_size == 640
    p.process(np.zeros((720, 1280, 3), np.uint8))
    assert det.sizes == [640]


def test_dashboard_live_processor_uses_image_setting(tmp_path, monkeypatch):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SITEGUARD_EVENTS_DB", str(tmp_path / "db.sqlite"))
    app = str(Path(__file__).resolve().parents[1] / "app.py")
    at = AppTest.from_file(app, default_timeout=120).run()
    if any("Model not trained" in m.value for m in at.sidebar.markdown):
        pytest.skip("no trained model")
    at.sidebar.radio[0].set_value("Live Monitoring").run()
    proc = at.session_state["live_processor"]
    assert proc.image_size == at.session_state["cfg"]["image_size"] == 640
    assert proc.every_n == 1


@pytest.mark.parametrize("h,w", [(720, 1280), (1280, 720), (1000, 1000), (480, 640), (2160, 3840), (1350, 1080)])
def test_letterbox_roundtrip_restores_original_coordinates(h, w):
    """Ultralytics predict path: LetterBox to 640 (auto, stride 32) -> boxes scaled back with scale_boxes."""
    import torch
    from ultralytics.data.augment import LetterBox
    from ultralytics.utils import ops

    img = np.zeros((h, w, 3), np.uint8)
    x1, y1, x2, y2 = int(w * 0.21), int(h * 0.33), int(w * 0.58), int(h * 0.81)
    img[y1:y2, x1:x2] = 255
    lb = LetterBox(new_shape=(640, 640), auto=True, stride=32)(image=img)
    ys, xs = np.where(lb[:, :, 0] > 127)
    found = torch.tensor([[xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]], dtype=torch.float32)
    back = ops.scale_boxes(lb.shape[:2], found, (h, w))[0].numpy()
    tol = max(2.0, max(h, w) / 640 * 1.5)  # one letterboxed pixel, in original pixels
    assert np.allclose(back, [x1, y1, x2, y2], atol=tol), (back, (x1, y1, x2, y2))
    assert max(lb.shape[:2]) == 640


def _variants(sample):
    from src.evaluation.live_audit import crop_sample, resize_long

    h, w = sample.image.shape[:2]
    return {
        "original_landscape": sample,
        "portrait_crop": crop_sample(sample, w / 2 - 0.28 * h, 0, w / 2 + 0.28 * h, h, "#p"),
        "square_crop": crop_sample(sample, w / 2 - h / 2, 0, w / 2 + h / 2, h, "#s"),
        "downscaled_640": resize_long(sample, 640),
        "upscaled_2560": resize_long(sample, 2560),
    }


@pytest.mark.parametrize("name", ["ultralytics-ppe-nov2026-022.jpg", "source-00f1fbfd9c8193a3c5a071512cf8c0a7.jpg",
                                  "ultralytics-ppe-nov2026-121.jpg"])
def test_real_detections_align_with_ground_truth_across_shapes(detector, name):
    from src.evaluation.live_audit import box_iou, load_val_samples

    samples = {s.name: s for s in load_val_samples()}
    if name not in samples:
        pytest.skip(f"{name} not in val split")
    for vname, s in _variants(samples[name]).items():
        h, w = s.image.shape[:2]
        dets = detector.detect(s.image, image_size=640)
        boxes = np.array([[d.x1, d.y1, d.x2, d.y2, d.class_id] for d in dets]).reshape(-1, 5)
        assert (boxes[:, 0] >= -1).all() and (boxes[:, 1] >= -1).all(), vname
        assert (boxes[:, 2] <= w + 1).all() and (boxes[:, 3] <= h + 1).all(), vname
        if len(s.gt) == 0 or len(boxes) == 0:
            continue
        iou = box_iou(s.gt[:, 1:5], boxes[:, :4]) * (s.gt[:, 0][:, None] == boxes[:, 4][None, :])
        best = iou.max(1)
        matched = best[best >= 0.5]
        assert len(matched) >= 0.3 * len(s.gt), f"{vname}: only {len(matched)}/{len(s.gt)} GT matched - coordinate error?"
        assert np.median(matched) >= 0.7, f"{vname}: median matched IoU {np.median(matched):.2f}"


def test_evidence_image_uses_source_frame_coordinates(tmp_path):
    frame = np.full((480, 640, 3), 128, np.uint8)
    dets = [Detection(5, "Person", 0.9, 200, 100, 300, 400), Detection(6, "no_helmet", 0.9, 230, 90, 270, 130)]
    result = ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",))).analyze(dets)
    annotated = draw_compliance(frame, result)
    assert annotated.shape == frame.shape  # rendering never resizes
    em = EventManager(None, "image", "t.jpg", evidence_dir=tmp_path)
    ev = em.process(result, now=0.0, evidence_frame=annotated)[0]
    img = cv2.imread(ev.evidence_path)
    assert img.shape == frame.shape
    assert ev.worker_box == [200.0, 100.0, 300.0, 400.0]
    # the evidence outline (orange, BGR 0,110,255) sits exactly on the worker box edge
    assert np.abs(img[250, 200].astype(int) - np.array([0, 110, 255])).max() < 60
