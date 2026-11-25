"""Correctness tests for the live-audit evaluator (src/evaluation/live_audit.py)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.live_audit import (
    NAME_TO_ID,
    Sample,
    classify_false_positive,
    codec_roundtrip,
    contradiction_pairs,
    crop_sample,
    evaluate,
    match_greedy,
    resize_long,
    yuv420_roundtrip,
)

H, P, NH = NAME_TO_ID["helmet"], NAME_TO_ID["Person"], NAME_TO_ID["no_helmet"]


def sample(gt, ignore=None, shape=(400, 600, 3)):
    return Sample("t", np.zeros(shape, np.uint8), np.array(gt, float).reshape(-1, 5),
                  np.array(ignore or [], float).reshape(-1, 5))


def pred(rows):
    return np.array(rows, float).reshape(-1, 6)  # x1 y1 x2 y2 conf cls


def test_perfect_predictions_score_one():
    s = sample([[H, 10, 10, 50, 50], [P, 100, 100, 200, 380]])
    r = evaluate([s], [pred([[10, 10, 50, 50, 0.9, H], [100, 100, 200, 380, 0.8, P]])])
    assert r["tp"] == 2 and r["fp"] == 0 and r["fn"] == 0
    assert r["precision"] == 1.0 and r["recall"] == 1.0
    # Ultralytics' ap_per_class interpolation reports 0.995 for a perfect detector (library convention).
    assert r["mAP50"] == pytest.approx(0.995, abs=1e-3) and r["mAP50-95"] == pytest.approx(0.995, abs=1e-3)


def test_duplicate_box_is_a_duplicate_false_positive():
    s = sample([[H, 10, 10, 50, 50]])
    p = pred([[10, 10, 50, 50, 0.9, H], [11, 11, 51, 51, 0.6, H]])
    r = evaluate([s], [p])
    assert (r["tp"], r["fp"], r["fn"]) == (1, 1, 0)
    assert r["fp_types"] == {"duplicate": 1}


def test_wrong_class_and_contradiction_counted():
    s = sample([[H, 10, 10, 50, 50]])
    p = pred([[10, 10, 50, 50, 0.9, NH], [10, 10, 50, 50, 0.5, H]])
    r = evaluate([s], [p])
    assert r["fp_types"] == {"wrong_class": 1}
    assert r["contradiction_pairs"] == 1
    assert r["tp"] == 1  # the helmet box still matches


def test_background_and_localization_types():
    gt = np.array([[H, 10, 10, 50, 50]], float)
    assert classify_false_positive(np.array([300, 300, 340, 340, 0.9, H]), gt)[0] == "background"
    assert classify_false_positive(np.array([30, 30, 70, 70, 0.9, H]), gt)[0] == "localization"


def test_low_confidence_predictions_do_not_change_operating_point():
    s = sample([[H, 10, 10, 50, 50]])
    high = pred([[10, 10, 50, 50, 0.9, H]])
    both = pred([[10, 10, 50, 50, 0.9, H], [300, 300, 320, 320, 0.1, H]])
    a, b = evaluate([s], [high]), evaluate([s], [both])
    assert (a["tp"], a["fp"], a["fn"]) == (b["tp"], b["fp"], b["fn"]) == (1, 0, 0)


def test_ignore_regions_are_not_scored():
    s = sample([], ignore=[[H, 10, 10, 50, 50]])
    r = evaluate([s], [pred([[12, 12, 48, 48, 0.9, H]])])
    assert r["fp"] == 0 and r["fn"] == 0


def test_match_greedy_prefers_higher_confidence():
    gt = np.array([[H, 0, 0, 10, 10]], float)
    p = pred([[0, 0, 10, 10, 0.9, H], [0, 0, 10, 10, 0.8, H]])
    c = match_greedy(p, gt)
    assert c[0, 0] and not c[1, 0]


def test_contradiction_needs_overlap():
    p = pred([[0, 0, 10, 10, 0.9, H], [100, 100, 110, 110, 0.9, NH]])
    assert contradiction_pairs(p) == 0


def test_resize_and_crop_remap_ground_truth():
    s = sample([[H, 100, 100, 200, 200], [P, 0, 0, 30, 300]], shape=(400, 600, 3))
    r = resize_long(s, 300)
    assert r.image.shape[:2] == (200, 300)
    assert np.allclose(r.gt[0, 1:], [50, 50, 100, 100])
    c = crop_sample(s, 150, 0, 600, 400, "#c")  # helmet 50 % visible -> ignore; person not visible -> dropped
    assert len(c.gt) == 0 and len(c.ignore) == 1
    assert np.allclose(c.ignore[0, 1:], [0, 100, 50, 200])


def test_yuv_roundtrip_keeps_channel_order():
    img = np.zeros((32, 96, 3), np.uint8)
    img[:, :32] = (0, 0, 255)    # red (BGR)
    img[:, 32:64] = (0, 255, 0)  # green
    img[:, 64:] = (255, 0, 0)    # blue
    out = yuv420_roundtrip(img)
    assert np.argmax(out[16, 16]) == 2 and np.argmax(out[16, 48]) == 1 and np.argmax(out[16, 80]) == 0


def test_codec_roundtrip_returns_same_size_frame():
    img = (np.random.default_rng(0).integers(0, 255, (128, 160, 3))).astype(np.uint8)
    out = codec_roundtrip(img, "libvpx", 500_000, hold=3)
    assert out.shape == img.shape


def test_encode_sequence_keeps_frame_count_and_size():
    from src.evaluation.live_audit import encode_sequence

    rng = np.random.default_rng(1)
    frames = [rng.integers(0, 255, (120, 160, 3)).astype(np.uint8) for _ in range(6)]
    out = encode_sequence(frames, "libvpx", 400_000, fps=30)
    assert len(out) == 6 and out[0].shape == frames[0].shape


def test_compliance_effect_perfect_and_missing_detections():
    from src.evaluation.live_audit import compliance_effect

    nv = NAME_TO_ID["no_vest"]
    gt = [[P, 100, 100, 200, 400], [NH, 130, 90, 170, 130], [nv, 110, 160, 190, 260]]
    s = sample(gt, shape=(500, 400, 3))
    perfect = pred([[100, 100, 200, 400, 0.9, P], [130, 90, 170, 130, 0.9, NH], [110, 160, 190, 260, 0.9, nv]])
    r = compliance_effect([s], [perfect])
    assert r["violations_in_reference"] == 2 and r["violation_recall"] == 1.0 and r["false_violations"] == 0
    weak = pred([[100, 100, 200, 400, 0.9, P], [130, 90, 170, 130, 0.3, NH]])  # below the 0.5 violation threshold
    r = compliance_effect([s], [weak])
    assert r["violation_recall"] == 0.0 and r["ref_potential_violation->pred_uncertain"] == 2
