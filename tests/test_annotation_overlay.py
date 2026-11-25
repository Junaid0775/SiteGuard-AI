"""Camera-quality Fix 4 (2026-11-23): overlay legibility without changing coordinates or semantics."""

from __future__ import annotations

import hashlib
import time

import numpy as np

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules
from src.detection.annotate import NEGATIVE_COLOR, STATUS_COLORS, draw_compliance, overlay_style


def analyze(make_det, dets):
    return ComplianceAnalyzer(ComplianceRules(required_ppe=("helmet",))).analyze([make_det(*d) for d in dets])


def test_shape_dtype_and_input_are_preserved(make_det):
    img = np.full((270, 480, 3), 90, np.uint8)
    before = hashlib.sha256(img.tobytes()).hexdigest()
    out = draw_compliance(img, analyze(make_det, [("Person", 0.9, 100, 60, 180, 250), ("no_helmet", 0.8, 120, 50, 160, 80)]))
    assert out.shape == img.shape and out.dtype == img.dtype
    assert hashlib.sha256(img.tobytes()).hexdigest() == before  # drawing happens on a copy


def test_box_lines_keep_exact_detection_coordinates(make_det):
    img = np.full((720, 1280, 3), 128, np.uint8)
    result = analyze(make_det, [("Person", 0.9, 300, 200, 500, 650), ("no_helmet", 0.8, 360, 205, 420, 260)])
    out = draw_compliance(img, result)
    status = result.workers[0].status
    assert tuple(out[425, 300]) == STATUS_COLORS[status]          # left edge of the worker box, mid-height
    assert tuple(out[425, 500]) == STATUS_COLORS[status]          # right edge
    assert tuple(out[240, 360]) == NEGATIVE_COLOR                  # left edge of the no_helmet box
    assert tuple(out[650, 400]) == STATUS_COLORS[status]          # bottom edge


def test_small_live_frames_get_readable_minimum_sizes():
    small, hd, full = overlay_style((270, 480, 3)), overlay_style((720, 1280, 3)), overlay_style((1080, 1920, 3))
    assert small["item_thick"] >= 2 and small["worker_thick"] >= 2       # was 1 px for items below 900 px width
    assert small["worker_font"] >= 0.42 and small["item_font"] >= 0.38   # item font was 0.32 at 480 px width
    assert hd["worker_thick"] >= small["worker_thick"] and full["worker_font"] > hd["worker_font"]
    assert full["worker_font"] <= 0.95 and full["worker_thick"] <= 6     # bounded so overlays do not hide workers


def test_labels_stay_inside_the_image_at_the_edges(make_det):
    img = np.zeros((300, 400, 3), np.uint8)
    result = analyze(make_det, [("Person", 0.9, 370, 0, 399, 100)])   # top-right corner: no room above the box
    out = draw_compliance(img, result)
    # label moved below the box and shifted left so it ends inside the frame
    assert out[104:112, 300:396].max() > 0
    assert out[0:2, 0:200].max() == 0                                  # nothing drawn far away from the worker


def test_drawing_is_deterministic_and_fast(make_det):
    img = np.full((720, 1280, 3), 100, np.uint8)
    dets = []
    for i in range(10):
        x = 40 + i * 120
        dets += [("Person", 0.9, x, 200, x + 100, 600), ("no_helmet", 0.7, x + 20, 190, x + 70, 240)]
    result = analyze(make_det, dets)
    assert np.array_equal(draw_compliance(img, result), draw_compliance(img, result))
    t0 = time.perf_counter()
    for _ in range(10):
        draw_compliance(img, result)
    assert (time.perf_counter() - t0) / 10 < 0.025  # 20 boxes + labels on a 1280x720 frame in under 25 ms
