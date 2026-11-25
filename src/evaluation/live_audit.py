"""Live / video detection accuracy audit (REPORT-009).

Why this exists
---------------
Live webcam and video detection looked worse than still-image detection. This
module measures, with REAL ground-truth labels, how each difference between the
still-image path and the live/video path changes detection quality.

Ground truth comes from the official validation split (200 images, 2,961 boxes).
Each "condition" transforms those images the way the live/video path would
(capture resolution, WebRTC colour conversion and compression, motion blur, low
light, webcam-style framing, inference size, thresholds, NMS mode, frame
skipping) and scores the detections against the labels. Nothing is estimated:
images that have no labels are never scored.

Run from the SiteGuard-AI folder:

    .venv/bin/python -m src.evaluation.live_audit conditions     # accuracy per condition + threshold sweep
    .venv/bin/python -m src.evaluation.live_audit overlay        # frame-skipping / stale-box test
    .venv/bin/python -m src.evaluation.live_audit latency        # speed per image size and device
    .venv/bin/python -m src.evaluation.live_audit colour         # WebRTC colour-conversion check
    .venv/bin/python -m src.evaluation.live_audit webcam         # captured webcam frames: image vs live pipeline
    .venv/bin/python -m src.evaluation.live_audit webcam-sweep   # labelled webcam frames: imgsz x NMS IoU
    .venv/bin/python -m src.evaluation.live_audit compliance     # detection errors -> compliance statuses
    .venv/bin/python -m src.evaluation.live_audit scale          # object size vs training distribution
    .venv/bin/python -m src.evaluation.live_audit device         # MPS vs CPU accuracy parity
    .venv/bin/python -m src.evaluation.live_audit equivalence    # harness == app detector check
(webcam frames first: .venv/bin/python scripts/capture_webcam_frames.py)
    .venv/bin/python -m src.evaluation.live_audit all

Results: experiments/live_audit/
"""

from __future__ import annotations

import argparse
import io
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from src.utils.paths import EXPERIMENTS_DIR, TRAINED_DIR, class_names, configure_ultralytics, source_dataset_dir
from src.utils.dataset_tools import parse_label_file

AUDIT_DIR = EXPERIMENTS_DIR / "live_audit"
NAMES = class_names()
NAME_TO_ID = {v: k for k, v in NAMES.items()}
PERSON_ID = NAME_TO_ID["Person"]
COMPLEMENT_PAIRS = [("helmet", "no_helmet"), ("vest", "no_vest"), ("gloves", "no_gloves"),
                    ("boots", "no_boots"), ("goggles", "no_goggle")]
COMPLEMENT_IDS = {(NAME_TO_ID[a], NAME_TO_ID[b]) for a, b in COMPLEMENT_PAIRS} | {(NAME_TO_ID[b], NAME_TO_ID[a]) for a, b in COMPLEMENT_PAIRS}
IOUV = np.linspace(0.5, 0.95, 10)
OP_CONF = 0.25  # the application's detection threshold


# ----------------------------------------------------------------------------- data
@dataclass
class Sample:
    """One image with ground truth. Boxes are (n, 5): class, x1, y1, x2, y2 in pixels."""

    name: str
    image: np.ndarray
    gt: np.ndarray
    ignore: np.ndarray = field(default_factory=lambda: np.zeros((0, 5)))


def load_val_samples(limit: int | None = None) -> list[Sample]:
    root = source_dataset_dir()
    samples = []
    for p in sorted((root / "images" / "val").glob("*.jpg"))[:limit]:
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        rows = parse_label_file(root / "labels" / "val" / f"{p.stem}.txt")
        gt = np.array([[r.class_id, (r.x_center - r.width / 2) * w, (r.y_center - r.height / 2) * h,
                        (r.x_center + r.width / 2) * w, (r.y_center + r.height / 2) * h] for r in rows], dtype=float).reshape(-1, 5)
        samples.append(Sample(p.name, img, gt))
    return samples


# ----------------------------------------------------------------------- transforms
def _scaled(s: Sample, img: np.ndarray, sx: float, sy: float, suffix: str) -> Sample:
    k = np.array([1, sx, sy, sx, sy])
    return Sample(s.name + suffix, img, s.gt * k, s.ignore * k)


def resize_long(s: Sample, long_side: int) -> Sample:
    """Resize so the longer side is `long_side` (even dimensions, needed for YUV 4:2:0)."""
    h, w = s.image.shape[:2]
    k = long_side / max(h, w)
    nw, nh = max(2, int(round(w * k / 2)) * 2), max(2, int(round(h * k / 2)) * 2)
    img = cv2.resize(s.image, (nw, nh), interpolation=cv2.INTER_AREA)
    return _scaled(s, img, nw / w, nh / h, "")


def yuv420_roundtrip(img: np.ndarray) -> np.ndarray:
    """BGR -> YUV 4:2:0 -> BGR with PyAV/libswscale, as the WebRTC receive path does."""
    import av

    frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format="bgr24").reformat(format="yuv420p")
    return frame.to_ndarray(format="bgr24")


def add_noise(img: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    return np.clip(img.astype(np.float32) + rng.normal(0, sigma, img.shape), 0, 255).astype(np.uint8)


def codec_roundtrip(img: np.ndarray, codec: str, bitrate: int, hold: int = 15, fps: int = 30,
                    noise_sigma: float = 3.0, seed: int = 0) -> np.ndarray:
    """Encode `hold` frames of a static scene (fresh sensor noise per frame) and return the last decoded frame.

    An approximation of a WebRTC stream: real browsers adapt bitrate and resolution over time.
    """
    import av

    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    buf = io.BytesIO()
    out = av.open(buf, mode="w", format="matroska")
    stream = out.add_stream(codec, rate=fps)
    stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
    stream.bit_rate = int(bitrate)
    if codec == "libx264":
        stream.options = {"preset": "veryfast", "tune": "zerolatency"}
    else:  # libvpx (VP8), the usual WebRTC codec between Chrome and aiortc
        stream.options = {"deadline": "realtime", "cpu-used": "8", "lag-in-frames": "0"}
    for i in range(hold):
        frame = av.VideoFrame.from_ndarray(add_noise(img, noise_sigma, rng) if noise_sigma else img, format="bgr24")
        frame.pts, frame.time_base = i, Fraction(1, fps)
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode():
        out.mux(packet)
    out.close()
    buf.seek(0)
    container = av.open(buf, mode="r")
    last = None
    for frame in container.decode(video=0):
        last = frame
    container.close()
    return last.to_ndarray(format="bgr24")


def motion_blur(img: np.ndarray, length: int) -> np.ndarray:
    kernel = np.zeros((length, length), np.float32)
    kernel[length // 2, :] = 1.0 / length
    return cv2.filter2D(img, -1, kernel)


def low_light(img: np.ndarray, gain: float, noise_sigma: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f = (img.astype(np.float32) / 255.0) ** 1.2 * gain * 255.0
    return np.clip(f + rng.normal(0, noise_sigma, img.shape), 0, 255).astype(np.uint8)


def crop_sample(s: Sample, x1: float, y1: float, x2: float, y2: float, suffix: str,
                keep_person: float = 0.4, keep_other: float = 0.6) -> Sample:
    """Crop and re-map labels. Objects mostly outside the crop become IGNORE regions (not scored)."""
    x1, y1, x2, y2 = int(max(0, x1)), int(max(0, y1)), int(min(s.image.shape[1], x2)), int(min(s.image.shape[0], y2))
    img = s.image[y1:y2, x1:x2].copy()
    gt, ign = [], [list(b) for b in s.ignore]
    for c, bx1, by1, bx2, by2 in s.gt:
        area = max(1e-6, (bx2 - bx1) * (by2 - by1))
        ix1, iy1, ix2, iy2 = max(bx1, x1), max(by1, y1), min(bx2, x2), min(by2, y2)
        vis = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1) / area
        if vis <= 0:
            continue
        box = [c, ix1 - x1, iy1 - y1, ix2 - x1, iy2 - y1]
        thr = keep_person if int(c) == PERSON_ID else keep_other
        (gt if vis >= thr else ign).append(box)
    ign = [b for b in ign if b[3] > 0 and b[4] > 0]
    return Sample(s.name + suffix, img, np.array(gt, float).reshape(-1, 5), np.array(ign, float).reshape(-1, 5))


def webcam_framing(s: Sample, min_person_height: float = 0.3) -> Sample | None:
    """Head-and-torso, 16:9 crop around the largest worker: how a desk webcam frames a person."""
    persons = s.gt[s.gt[:, 0] == PERSON_ID]
    if len(persons) == 0:
        return None
    p = persons[np.argmax((persons[:, 3] - persons[:, 1]) * (persons[:, 4] - persons[:, 2]))]
    ph = p[4] - p[2]
    if ph / s.image.shape[0] < min_person_height:
        return None
    ch = 0.65 * ph
    cw = ch * 16 / 9
    cx = (p[1] + p[3]) / 2
    y1 = p[2] - 0.10 * ph
    return crop_sample(s, cx - cw / 2, y1, cx + cw / 2, y1 + ch, "#webcam")


# ----------------------------------------------------------------------- prediction
class Predictor:
    """Calls Ultralytics exactly like PPEDetector.detect, with optional post-processing variants."""

    def __init__(self, weights: Path | None = None, device: str = "mps", nms_free: bool = False) -> None:
        configure_ultralytics()
        from ultralytics import YOLO

        self.model = YOLO(str(weights or TRAINED_DIR / "best.pt"))
        self.device = device
        self.extra = {"nms": False} if nms_free else {}

    def __call__(self, img: np.ndarray, imgsz: int = 640, conf: float = 0.001, iou: float = 0.5,
                 agnostic: bool = False) -> np.ndarray:
        r = self.model.predict(img, conf=conf, iou=iou, imgsz=imgsz, device=self.device, agnostic_nms=agnostic,
                               verbose=False, **self.extra)[0]
        b = r.boxes
        if b is None or len(b) == 0:
            return np.zeros((0, 6))
        return np.concatenate([b.xyxy.cpu().numpy(), b.conf.cpu().numpy()[:, None], b.cls.cpu().numpy()[:, None]], 1)


# ----------------------------------------------------------------------- evaluation
def box_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU matrix between boxes a (n, 4) and b (m, 4)."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.prod(np.clip(br - tl, 0, None), axis=2)
    area_a = np.prod(a[:, 2:] - a[:, :2], axis=1)
    area_b = np.prod(b[:, 2:] - b[:, :2], axis=1)
    return inter / (area_a[:, None] + area_b[None, :] - inter + 1e-9)


def box_ioa(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Intersection over the area of each box in `a`."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.prod(np.clip(br - tl, 0, None), axis=2)
    return inter / (np.prod(a[:, 2:] - a[:, :2], axis=1)[:, None] + 1e-9)


def match_greedy(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Same rule as Ultralytics 8.4 BaseValidator.match_predictions (greedy, descending confidence).

    `pred` (n, 6) must be sorted by confidence. Returns a boolean (n, 10) array: correct at IoU 0.50:0.95.
    """
    correct = np.zeros((len(pred), len(IOUV)), bool)
    if len(pred) == 0 or len(gt) == 0:
        return correct
    iou = box_iou(gt[:, 1:5], pred[:, :4]) * (gt[:, 0][:, None] == pred[:, 5][None, :])
    matched = np.zeros((len(gt), len(IOUV)), bool)
    cols = np.arange(len(IOUV))
    for j in range(len(pred)):
        available = np.where(matched, 0.0, iou[:, j, None])
        k = available.argmax(0)
        correct[j] = available[k, cols] >= IOUV
        matched[k, cols] |= correct[j]
    return correct


def classify_false_positive(p: np.ndarray, gt: np.ndarray) -> tuple[str, int | None]:
    """Why is this unmatched prediction wrong? Returns (type, overlapping GT class or None)."""
    if len(gt) == 0:
        return "background", None
    iou = box_iou(p[None, :4], gt[:, 1:5])[0]
    same = gt[:, 0] == p[5]
    if same.any() and iou[same].max() >= 0.5:
        return "duplicate", int(p[5])
    other = ~same
    if other.any() and iou[other].max() >= 0.5:
        return "wrong_class", int(gt[other][np.argmax(iou[other]), 0])
    if iou.max() >= 0.1:
        return "localization", int(gt[np.argmax(iou), 0])
    return "background", None


def contradiction_pairs(pred: np.ndarray, iou_thr: float = 0.5) -> int:
    """Pairs of boxes on the same object that say opposite things (e.g. helmet AND no_helmet)."""
    if len(pred) < 2:
        return 0
    iou = box_iou(pred[:, :4], pred[:, :4])
    n = 0
    for i in range(len(pred)):
        for j in range(i + 1, len(pred)):
            if (int(pred[i, 5]), int(pred[j, 5])) in COMPLEMENT_IDS and iou[i, j] >= iou_thr:
                n += 1
    return n


def evaluate(samples: list[Sample], preds: list[np.ndarray], op_conf: float = OP_CONF) -> dict:
    """mAP (Ultralytics ap_per_class) plus counts at the app's confidence threshold."""
    from ultralytics.utils.metrics import ap_per_class

    tp_all, conf_all, cls_all, target_all = [], [], [], []
    op = Counter()
    per_class = {c: Counter() for c in NAMES}
    fp_types, confusion = Counter(), Counter()
    contradictions = 0
    for s, p in zip(samples, preds):
        p = p[np.argsort(-p[:, 4], kind="stable")] if len(p) else p
        correct = match_greedy(p, s.gt)
        if len(s.ignore) and len(p):
            same_cls = s.ignore[:, 0][None, :] == p[:, 5][:, None]
            on_ignore = ((box_ioa(p[:, :4], s.ignore[:, 1:5]) >= 0.5) & same_cls).any(1)
            keep = correct[:, 0] | ~on_ignore
            p, correct = p[keep], correct[keep]
        tp_all.append(correct)
        conf_all.append(p[:, 4] if len(p) else np.zeros(0))
        cls_all.append(p[:, 5] if len(p) else np.zeros(0))
        target_all.append(s.gt[:, 0])
        # Operating point: greedy matching is in confidence order, so the matches of
        # predictions >= op_conf do not depend on lower-confidence predictions.
        m = p[:, 4] >= op_conf if len(p) else np.zeros(0, bool)
        po, co = p[m], correct[m, 0]
        op["tp"] += int(co.sum())
        op["fp"] += int((~co).sum())
        op["gt"] += len(s.gt)
        for c in NAMES:
            pc = po[:, 5] == c if len(po) else np.zeros(0, bool)
            per_class[c]["tp"] += int((co & pc).sum())
            per_class[c]["fp"] += int((~co & pc).sum())
            per_class[c]["gt"] += int((s.gt[:, 0] == c).sum())
        for row in po[~co]:
            kind, gt_cls = classify_false_positive(row, s.gt)
            fp_types[kind] += 1
            if kind == "wrong_class":
                confusion[f"{NAMES[int(row[5])]} (true: {NAMES[gt_cls]})"] += 1
        contradictions += contradiction_pairs(po)
    tp, conf, pcls = np.concatenate(tp_all), np.concatenate(conf_all), np.concatenate(cls_all)
    target = np.concatenate(target_all)
    res = ap_per_class(tp, conf, pcls, target)
    ap, ap_classes = res[5], res[6]
    tp_n, fp_n, gt_n = op["tp"], op["fp"], op["gt"]
    out = {
        "images": len(samples),
        "gt_objects": int(gt_n),
        "mAP50": float(ap[:, 0].mean()) if len(ap) else 0.0,
        "mAP50-95": float(ap.mean()) if len(ap) else 0.0,
        "per_class_mAP50-95": {NAMES[int(c)]: round(float(a.mean()), 4) for c, a in zip(ap_classes, ap)},
        "op_conf": op_conf,
        "tp": tp_n, "fp": fp_n, "fn": gt_n - tp_n,
        "precision": tp_n / (tp_n + fp_n) if tp_n + fp_n else 0.0,
        "recall": tp_n / gt_n if gt_n else 0.0,
        "fp_per_image": fp_n / max(1, len(samples)),
        "fp_types": dict(fp_types),
        "top_confusions": dict(confusion.most_common(8)),
        "contradiction_pairs": contradictions,
        "per_class_op": {
            NAMES[c]: {"tp": v["tp"], "fp": v["fp"], "fn": v["gt"] - v["tp"],
                       "precision": round(v["tp"] / (v["tp"] + v["fp"]), 4) if v["tp"] + v["fp"] else None,
                       "recall": round(v["tp"] / v["gt"], 4) if v["gt"] else None}
            for c, v in per_class.items()
        },
    }
    out["f1"] = 2 * out["precision"] * out["recall"] / (out["precision"] + out["recall"]) if out["precision"] + out["recall"] else 0.0
    return out


def false_positive_log(samples: list[Sample], preds: list[np.ndarray], imgsz: int, condition: str,
                       op_conf: float = OP_CONF) -> list[dict]:
    """One record per false-positive detection (the 'suspicious detections' log)."""
    records = []
    stamp = datetime.now().isoformat(timespec="seconds")
    for s, p in zip(samples, preds):
        if not len(p):
            continue
        p = p[np.argsort(-p[:, 4], kind="stable")]
        correct = match_greedy(p, s.gt)[:, 0]
        h, w = s.image.shape[:2]
        for row, ok in zip(p, correct):
            if ok or row[4] < op_conf:
                continue
            kind, gt_cls = classify_false_positive(row, s.gt)
            if kind != "duplicate" and len(s.ignore):
                if ((box_ioa(row[None, :4], s.ignore[:, 1:5])[0] >= 0.5) & (s.ignore[:, 0] == row[5])).any():
                    continue
            records.append({
                "condition": condition, "image": s.name, "predicted_class": NAMES[int(row[5])],
                "confidence": round(float(row[4]), 4), "box_xyxy": [round(float(v), 1) for v in row[:4]],
                "frame_wh": [w, h], "inference_imgsz": imgsz, "fp_type": kind,
                "overlapping_gt_class": NAMES[gt_cls] if gt_cls is not None else None, "timestamp": stamp,
            })
    return records


# ----------------------------------------------------------------------- conditions
@dataclass
class Condition:
    name: str
    group: str
    transform: Callable[[Sample], Sample | None]
    imgsz: int = 640
    iou: float = 0.5
    agnostic: bool = False
    nms_free: bool = False
    note: str = ""
    key: str = ""  # conditions with the same key share one transformed image set (computed once)


def _with_image(fn: Callable[[np.ndarray], np.ndarray], base: Callable[[Sample], Sample]) -> Callable[[Sample], Sample]:
    def t(s: Sample) -> Sample:
        b = base(s)
        return Sample(b.name, fn(b.image), b.gt, b.ignore)
    return t


def _identity(s: Sample) -> Sample:
    return s


def _cam720(s: Sample) -> Sample:
    return resize_long(s, 1280)


def _cam480(s: Sample) -> Sample:
    return resize_long(s, 640)


def _framing(s: Sample) -> Sample | None:
    w = webcam_framing(s)
    return resize_long(w, 1280) if w is not None else None


def _framing_reference(s: Sample) -> Sample | None:
    """The same images as the webcam-framing test, but uncropped (apples-to-apples reference)."""
    return resize_long(s, 1280) if webcam_framing(s) is not None else None


VP8_1M = _with_image(lambda im: codec_roundtrip(im, "libvpx", 1_000_000), _cam720)


def build_conditions() -> list[Condition]:
    """Every condition is compared against `still_640` (the image-upload configuration)."""
    return [
        Condition("still_640", "A inference size", _identity, 640, note="image-upload configuration (reference)", key="id"),
        Condition("still_320", "A inference size", _identity, 320, key="id"),
        Condition("still_480", "A inference size", _identity, 480, note="current live imgsz on a full-resolution photo", key="id"),
        Condition("still_800", "A inference size", _identity, 800, key="id"),
        Condition("still_960", "A inference size", _identity, 960, key="id"),
        Condition("still_640_agnostic", "H post-processing", _identity, 640, agnostic=True, note="class-agnostic NMS", key="id"),
        Condition("still_640_iou07", "H post-processing", _identity, 640, iou=0.7, note="NMS IoU 0.7 (Ultralytics val default)", key="id"),
        Condition("still_640_nmsfree", "H post-processing", _identity, 640, nms_free=True, note="YOLO26 one-to-one head, no NMS", key="id"),
        Condition("still_640_iou03", "H post-processing", _identity, 640, iou=0.3, note="NMS IoU 0.3 (suppresses nested same-class boxes)", key="id"),
        Condition("cam720_640", "B capture resolution", _cam720, 640, note="frame resized to 1280 px long side (720p-class webcam)", key="cam720"),
        Condition("cam720_480", "B capture resolution", _cam720, 480, note="720p frame at the current live imgsz", key="cam720"),
        Condition("cam480_640", "B capture resolution", _cam480, 640, note="frame resized to 640 px long side (VGA-class webcam)", key="cam480"),
        Condition("cam480_480", "B capture resolution", _cam480, 480, key="cam480"),
        Condition("cam720_yuv420_640", "C WebRTC transport", _with_image(yuv420_roundtrip, _cam720), 640, note="chroma subsampling + colour conversion only", key="yuv"),
        Condition("cam720_noise3_640", "C WebRTC transport", _with_image(lambda im: add_noise(im, 3.0, np.random.default_rng(0)), _cam720), 640, note="sensor-noise control for the codec rows", key="noise3"),
        Condition("cam720_vp8_300k_640", "C WebRTC transport", _with_image(lambda im: codec_roundtrip(im, "libvpx", 300_000), _cam720), 640, note="VP8 300 kbps (WebRTC start-up bitrate)", key="vp8_300k"),
        Condition("cam720_vp8_2500k_640", "C WebRTC transport", _with_image(lambda im: codec_roundtrip(im, "libvpx", 2_500_000), _cam720), 640, note="VP8 2.5 Mbps (typical 720p WebRTC ceiling)", key="vp8_2500k"),
        Condition("cam720_h264_1m_640", "C WebRTC transport", _with_image(lambda im: codec_roundtrip(im, "libx264", 1_000_000), _cam720), 640, note="H.264 1 Mbps", key="h264_1m"),
        Condition("cam720_vp8_1m_640", "C WebRTC transport", VP8_1M, 640, note="VP8 1 Mbps (= live stream at imgsz 640)", key="vp8_1m"),
        Condition("live_now", "G full live path", VP8_1M, 480, note="CURRENT live: 720p + VP8 1 Mbps + imgsz 480", key="vp8_1m"),
        Condition("live_640_agnostic", "H post-processing", VP8_1M, 640, agnostic=True, note="live stream, imgsz 640, class-agnostic NMS", key="vp8_1m"),
        Condition("cam720_blur9_640", "D motion blur", _with_image(lambda im: motion_blur(im, 9), _cam720), 640, note="9 px horizontal blur at 720p", key="blur9"),
        Condition("cam720_blur17_640", "D motion blur", _with_image(lambda im: motion_blur(im, 17), _cam720), 640, note="17 px", key="blur17"),
        Condition("cam720_blur31_640", "D motion blur", _with_image(lambda im: motion_blur(im, 31), _cam720), 640, note="31 px (fast movement)", key="blur31"),
        Condition("cam720_dim_640", "E lighting", _with_image(lambda im: low_light(im, 0.5, 4.0), _cam720), 640, note="brightness x0.5 + noise 4", key="dim"),
        Condition("cam720_dark_640", "E lighting", _with_image(lambda im: low_light(im, 0.25, 8.0), _cam720), 640, note="brightness x0.25 + noise 8", key="dark"),
        Condition("framing_reference_640", "F webcam framing", _framing_reference, 640, note="same images, uncropped 720p (reference)", key="frame_ref"),
        Condition("webcam_framing_640", "F webcam framing", _framing, 640, note="head-and-torso 16:9 crop of the largest worker", key="framing"),
        Condition("webcam_framing_480", "F webcam framing", _framing, 480, key="framing"),
    ]


SWEEP_CONDITIONS = ("still_640", "cam720_vp8_1m_640", "live_now", "webcam_framing_640")
SWEEP_THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55)


def run_conditions(limit: int | None = None, names: list[str] | None = None, device: str = "mps") -> dict:
    samples = load_val_samples(limit)
    predictors: dict[bool, Predictor] = {}
    results, sweep, fp_records, example_preds = {}, {}, [], {}
    cache_key, cache = None, None
    for cond in build_conditions():
        if names and cond.name not in names:
            continue
        t0 = time.time()
        if cond.key and cond.key == cache_key:
            transformed = cache
        else:
            transformed = [t for t in (cond.transform(s) for s in samples) if t is not None]
            cache_key, cache = cond.key, transformed
        t_transform = time.time() - t0
        pred = predictors.setdefault(cond.nms_free, Predictor(device=device, nms_free=cond.nms_free))
        t1 = time.time()
        preds = [pred(t.image, imgsz=cond.imgsz, conf=0.001, iou=cond.iou, agnostic=cond.agnostic) for t in transformed]
        t_pred = time.time() - t1
        res = evaluate(transformed, preds)
        res.update(group=cond.group, imgsz=cond.imgsz, iou=cond.iou, agnostic=cond.agnostic, nms_free=cond.nms_free,
                   note=cond.note, seconds_transform=round(t_transform, 1), seconds_predict=round(t_pred, 1))
        results[cond.name] = res
        if cond.name in SWEEP_CONDITIONS:
            sweep[cond.name] = {}
            for c in SWEEP_THRESHOLDS:
                r = evaluate(transformed, preds, op_conf=c)
                sweep[cond.name][str(c)] = {k: r[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1", "fp_per_image",
                                                              "contradiction_pairs", "fp_types")}
        if cond.name in ("still_640", "live_now", "webcam_framing_640", "webcam_framing_480"):
            fp_records += false_positive_log(transformed, preds, cond.imgsz, cond.name)
            example_preds[cond.name] = (transformed, preds)
        print(f"{cond.name:24s} n={res['images']:3d} gt={res['gt_objects']:4d} mAP50={res['mAP50']:.3f} "
              f"mAP50-95={res['mAP50-95']:.3f} P={res['precision']:.3f} R={res['recall']:.3f} "
              f"FP/img={res['fp_per_image']:.2f} contra={res['contradiction_pairs']}  ({t_transform:.0f}s+{t_pred:.0f}s)", flush=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "conditions.json"
    if names and path.exists():  # partial re-run: add to the existing results instead of replacing them
        out = json.loads(path.read_text(encoding="utf-8"))
        out["conditions"].update(results)
        out.setdefault("threshold_sweep", {}).update(sweep)
        out["updated"] = datetime.now().isoformat(timespec="seconds")
        path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        return out
    out = {"created": datetime.now().isoformat(timespec="seconds"), "weights": str(TRAINED_DIR / "best.pt"),
           "device": device, "op_conf": OP_CONF, "conditions": results, "threshold_sweep": sweep}
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    with open(AUDIT_DIR / "suspicious_detections.jsonl", "w", encoding="utf-8") as f:
        for r in fp_records:
            f.write(json.dumps(r) + "\n")
    save_examples(example_preds)
    return out


def save_examples(example_preds: dict, n: int = 4) -> None:
    """Representative frames with ground truth (white) and detections >= 0.25 (green = correct, red = false positive)."""
    ex_dir = AUDIT_DIR / "examples"
    ex_dir.mkdir(parents=True, exist_ok=True)
    for cond, (samples, preds) in example_preds.items():
        scored = []
        for s, p in zip(samples, preds):
            p = p[p[:, 4] >= OP_CONF] if len(p) else p
            p = p[np.argsort(-p[:, 4], kind="stable")] if len(p) else p
            ok = match_greedy(p, s.gt)[:, 0] if len(p) else np.zeros(0, bool)
            scored.append(((~ok).sum(), s, p, ok))
        for k, (_, s, p, ok) in enumerate(sorted(scored, key=lambda t: -t[0])[:n]):
            img = s.image.copy()
            th = max(1, img.shape[1] // 640)
            for c, x1, y1, x2, y2 in s.gt:
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 255, 255), th)
            for row, good in zip(p, ok):
                color = (60, 170, 60) if good else (40, 40, 220)
                x1, y1, x2, y2 = (int(v) for v in row[:4])
                cv2.rectangle(img, (x1, y1), (x2, y2), color, th + 1)
                cv2.putText(img, f"{NAMES[int(row[5])]} {row[4]:.2f}", (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.4 * th + 0.2, color, th, cv2.LINE_AA)
            cv2.imwrite(str(ex_dir / f"{cond}_{k}_{Path(s.name.split('#')[0]).stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])


# --------------------------------------------------------------- frame skipping test
def pan_sequence(s: Sample, n_frames: int, speed: int) -> list[Sample]:
    """A camera panning `speed` px/frame across a 720p-class frame: objects move left in the image."""
    base = resize_long(s, 1280)
    w = base.image.shape[1] - speed * (n_frames - 1)
    return [crop_sample(base, k * speed, 0, k * speed + w, base.image.shape[0], f"#pan{speed}f{k}") for k in range(n_frames)]


def run_overlay(limit: int = 40, n_frames: int = 15, speeds=(0, 4, 10, 20), every=(1, 3, 5), imgsz: int = 480,
                device: str = "mps") -> dict:
    """Score the boxes DISPLAYED on every frame when only every Nth frame is analysed.

    Skipped frames show the boxes of the last analysed frame (the app's current behaviour), so moving objects are
    drawn where they used to be. Ground truth moves with the pan, so the misplacement is measured directly.
    """
    samples = load_val_samples(limit)
    pred = Predictor(device=device)
    out = {}
    for speed in speeds:
        seqs = [pan_sequence(s, n_frames, speed) for s in samples]
        preds = [[pred(f.image, imgsz=imgsz, conf=OP_CONF) for f in seq] for seq in seqs]
        for n in every:
            frames, shown = [], []
            for seq, pseq in zip(seqs, preds):
                for k, f in enumerate(seq):
                    frames.append(f)
                    shown.append(pseq[k - (k % n)])
            r = evaluate(frames, shown)
            out[f"speed{speed}_every{n}"] = {"speed_px_per_frame": speed, "every_n": n, "frames": len(frames),
                                             **{k: r[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")}}
            print(f"speed={speed:2d}px/f every={n} P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f}")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "overlay_staleness.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


# --------------------------------------------------------------------- latency test
def run_latency(n: int = 40) -> dict:
    """Mean time per frame for detection alone and for the full live callback, per imgsz and device."""
    from src.compliance.compliance_analyzer import ComplianceAnalyzer
    from src.detection.annotate import draw_compliance
    from src.detection.detector import PPEDetector

    frame = resize_long(load_val_samples(1)[0], 1280).image
    frame = cv2.resize(frame, (1280, 720))
    analyzer = ComplianceAnalyzer()
    out = {}
    for device in ("mps", "cpu"):
        det = PPEDetector(device=device).load()
        for imgsz in (320, 480, 640, 800, 960):
            for _ in range(5):
                det.detect(frame, image_size=imgsz)
            t_det, t_full = [], []
            for _ in range(n):
                t0 = time.perf_counter()
                d = det.detect(frame, image_size=imgsz)
                t1 = time.perf_counter()
                draw_compliance(frame, analyzer.analyze(d))
                t2 = time.perf_counter()
                t_det.append((t1 - t0) * 1000)
                t_full.append((t2 - t0) * 1000)
            out[f"{device}_{imgsz}"] = {"device": device, "imgsz": imgsz, "detect_ms_mean": round(float(np.mean(t_det)), 1),
                                        "detect_ms_p95": round(float(np.percentile(t_det, 95)), 1),
                                        "callback_ms_mean": round(float(np.mean(t_full)), 1),
                                        "max_analysed_fps": round(1000 / float(np.mean(t_full)), 1)}
            print(out[f"{device}_{imgsz}"])
    (AUDIT_DIR / "latency.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


# ---------------------------------------------------------------------- colour test
def run_colour() -> dict:
    """Does the WebRTC frame conversion keep the channel order and colours?"""
    patches = {"red": (0, 0, 255), "green": (0, 255, 0), "blue": (255, 0, 0), "hi-vis yellow": (0, 230, 230),
               "hi-vis orange": (0, 120, 255), "white": (255, 255, 255), "grey": (128, 128, 128)}
    tile = np.concatenate([np.full((64, 64, 3), c, np.uint8) for c in patches.values()], 1)
    rt = yuv420_roundtrip(tile)
    res = {}
    for i, (name, bgr) in enumerate(patches.items()):
        got = rt[16:48, i * 64 + 16:i * 64 + 48].reshape(-1, 3).mean(0)
        res[name] = {"in_bgr": list(bgr), "out_bgr": [round(float(v), 1) for v in got],
                     "max_abs_error": round(float(np.abs(got - np.array(bgr)).max()), 1)}
    sample = resize_long(load_val_samples(1)[0], 1280).image
    res["photo_mean_abs_error"] = round(float(np.abs(yuv420_roundtrip(sample).astype(int) - sample.astype(int)).mean()), 2)
    res["channel_order_preserved"] = all(int(np.argmax(r["out_bgr"])) == int(np.argmax(r["in_bgr"])) for k, r in res.items()
                                         if isinstance(r, dict) and k in ("red", "green", "blue"))
    (AUDIT_DIR / "colour_check.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return res


# ------------------------------------------------------------------- webcam frames
WEBCAM_DIR = AUDIT_DIR / "webcam"


def encode_sequence(frames: list[np.ndarray], codec: str = "libvpx", bitrate: int = 1_000_000, fps: float = 30.0) -> list[np.ndarray]:
    """Encode a real frame sequence as one video stream and decode it again (WebRTC-like transport)."""
    import av

    h, w = frames[0].shape[:2]
    buf = io.BytesIO()
    out = av.open(buf, mode="w", format="matroska")
    stream = out.add_stream(codec, rate=int(round(fps)))
    stream.width, stream.height, stream.pix_fmt = w - w % 2, h - h % 2, "yuv420p"
    stream.bit_rate = int(bitrate)
    stream.options = {"deadline": "realtime", "cpu-used": "8", "lag-in-frames": "0"} if codec == "libvpx" else {"preset": "veryfast", "tune": "zerolatency"}
    for i, f in enumerate(frames):
        fr = av.VideoFrame.from_ndarray(np.ascontiguousarray(f[: h - h % 2, : w - w % 2]), format="bgr24")
        fr.pts, fr.time_base = i, Fraction(1, int(round(fps)))
        for packet in stream.encode(fr):
            out.mux(packet)
    for packet in stream.encode():
        out.mux(packet)
    out.close()
    buf.seek(0)
    container = av.open(buf, mode="r")
    decoded = [fr.to_ndarray(format="bgr24") for fr in container.decode(video=0)]
    container.close()
    return decoded


def _load_yolo_boxes(path: Path, w: int, h: int) -> np.ndarray:
    if not path.exists():
        return np.zeros((0, 5))
    rows = parse_label_file(path)
    return np.array([[r.class_id, (r.x_center - r.width / 2) * w, (r.y_center - r.height / 2) * h,
                      (r.x_center + r.width / 2) * w, (r.y_center + r.height / 2) * h] for r in rows], float).reshape(-1, 5)


def _det_rows(dets) -> np.ndarray:
    return np.array([[d.x1, d.y1, d.x2, d.y2, d.confidence, d.class_id] for d in dets], float).reshape(-1, 6)


def _compare_sets(a: np.ndarray, b: np.ndarray) -> tuple[int, int, int]:
    """(matched same class IoU>=0.5, only in a, only in b)."""
    if len(a) == 0 or len(b) == 0:
        return 0, len(a), len(b)
    iou = box_iou(a[:, :4], b[:, :4]) * (a[:, 5][:, None] == b[:, 5][None, :])
    used, m = set(), 0
    for i in np.argsort(-a[:, 4]):
        j = int(np.argmax(iou[i]))
        if iou[i, j] >= 0.5 and j not in used:
            used.add(j)
            m += 1
    return m, len(a) - m, len(b) - m


def run_webcam(every_n: int = 3, live_imgsz: int = 480, image_imgsz: int = 640, bitrate: int = 1_000_000) -> dict:
    """Same captured webcam frames through the image-upload pipeline and the live pipeline."""
    from src.utils.diagnostics import use_temporary_evidence_dir

    use_temporary_evidence_dir()  # Fix 6: replayed webcam frames must never create production evidence

    from src.compliance.compliance_analyzer import ComplianceAnalyzer
    from src.detection.camera_processor import LiveFrameProcessor
    from src.detection.detector import PPEDetector
    from src.detection.image_processor import inspect_image

    frames_dir = WEBCAM_DIR / "frames"
    meta = json.loads((WEBCAM_DIR / "capture_meta.json").read_text())
    files = [frames_dir / m["file"] for m in meta["frames"]]
    stamps = {m["file"]: m["timestamp"] for m in meta["frames"]}
    raw = [cv2.imread(str(f)) for f in files]
    fps = float(meta.get("measured_fps") or 30.0)
    transported = encode_sequence(raw, "libvpx", bitrate, fps)
    assert len(transported) == len(raw), (len(transported), len(raw))

    det = PPEDetector().load()
    analyzer = ComplianceAnalyzer()
    log, summary = [], {"frames": len(raw), "frame_wh": [raw[0].shape[1], raw[0].shape[0]], "fps": fps, "every_n": every_n,
                        "live_imgsz": live_imgsz, "image_imgsz": image_imgsz, "vp8_bitrate": bitrate}

    # 1) image-upload pipeline (Image Inspection page): raw frame, imgsz 640
    image_dets = [_det_rows(inspect_image(f, det, analyzer, confidence=OP_CONF, image_size=image_imgsz).detections) for f in raw]

    # 2) live pipeline (Live Monitoring page): LiveFrameProcessor on the transported stream
    def run_live(stream: list[np.ndarray], imgsz: int) -> tuple[list[np.ndarray], list[np.ndarray], list[bool]]:
        proc = LiveFrameProcessor(det, analyzer, None, process_every_n=every_n, image_size=imgsz, confidence=OP_CONF)
        analysed, displayed, flags = [], [], []
        last = np.zeros((0, 6))
        for f in stream:
            before = proc.stats.frames_analysed
            proc.process(f)
            was_analysed = proc.stats.frames_analysed > before
            if was_analysed:
                last = _det_rows(proc._last_result.all_detections)  # audit-only access to the last result
            analysed.append(last if was_analysed else None)
            displayed.append(last)
            flags.append(was_analysed)
        return analysed, displayed, flags

    live_an, live_disp, live_flag = run_live(transported, live_imgsz)
    raw_an, _, _ = run_live(raw, live_imgsz)  # same code path without the transport, to isolate it

    # 3) log every detection with the requested fields + suspicion flags
    for pipeline, per_frame, imgsz, src in (("image_upload", image_dets, image_imgsz, raw), ("live_analysed", live_an, live_imgsz, transported)):
        prev = None
        for f, rows, frame in zip(files, per_frame, src):
            if rows is None:
                continue
            h, w = frame.shape[:2]
            contra = set()
            if len(rows) > 1:
                iou = box_iou(rows[:, :4], rows[:, :4])
                for i in range(len(rows)):
                    for j in range(i + 1, len(rows)):
                        if (int(rows[i, 5]), int(rows[j, 5])) in COMPLEMENT_IDS and iou[i, j] >= 0.5:
                            contra |= {i, j}
            persons = rows[rows[:, 5] == PERSON_ID] if len(rows) else rows
            for i, r in enumerate(rows):
                flags = []
                if r[4] < 0.4:
                    flags.append("low_confidence")
                if i in contra:
                    flags.append("contradicting_overlap")
                if int(r[5]) != PERSON_ID and (len(persons) == 0 or box_ioa(r[None, :4], persons[:, :4]).max() < 0.6):
                    flags.append("outside_any_person")
                if prev is not None and len(prev):
                    o = box_iou(r[None, :4], prev[:, :4])[0]
                    k = int(np.argmax(o))
                    if o[k] >= 0.5 and int(prev[k, 5]) != int(r[5]):
                        flags.append(f"class_changed_from_{NAMES[int(prev[k, 5])]}")
                log.append({"pipeline": pipeline, "frame": f.name, "timestamp": stamps[f.name], "predicted_class": NAMES[int(r[5])],
                            "confidence": round(float(r[4]), 4), "box_xyxy": [round(float(v), 1) for v in r[:4]],
                            "frame_wh": [w, h], "inference_imgsz": imgsz, "suspicious": flags})
            prev = rows
    WEBCAM_DIR.mkdir(parents=True, exist_ok=True)
    with open(WEBCAM_DIR / "webcam_detections.jsonl", "w", encoding="utf-8") as fh:
        for r in log:
            fh.write(json.dumps(r) + "\n")

    # 4) image-vs-live agreement on the analysed frames
    m_tot = a_only = b_only = 0
    for a, b in zip(image_dets, live_an):
        if b is None:
            continue
        m, x, y = _compare_sets(a, b)
        m_tot, a_only, b_only = m_tot + m, a_only + x, b_only + y
    summary["image_vs_live"] = {"matched": m_tot, "only_image_upload": a_only, "only_live": b_only}
    m_tot = a_only = b_only = 0
    for a, b in zip(raw_an, live_an):
        if a is None:
            continue
        m, x, y = _compare_sets(a, b)
        m_tot, a_only, b_only = m_tot + m, a_only + x, b_only + y
    summary["live_raw_vs_live_transported"] = {"matched": m_tot, "only_raw": a_only, "only_transported": b_only}
    counts = Counter(r["predicted_class"] for r in log if r["pipeline"] == "live_analysed")
    summary["live_class_counts"] = dict(counts)
    summary["image_class_counts"] = dict(Counter(r["predicted_class"] for r in log if r["pipeline"] == "image_upload"))
    summary["suspicious_flag_counts"] = {p: dict(Counter(f for r in log if r["pipeline"] == p for f in r["suspicious"]))
                                         for p in ("image_upload", "live_analysed")}

    # 5) accuracy against manual labels, where they exist
    labelled = [i for i, f in enumerate(files) if (WEBCAM_DIR / "labels" / f"{f.stem}.txt").exists()]
    if labelled:
        pred = Predictor()
        def subset(stream):
            out = []
            for i in labelled:
                h, w = stream[i].shape[:2]
                out.append(Sample(files[i].name, stream[i], _load_yolo_boxes(WEBCAM_DIR / "labels" / f"{files[i].stem}.txt", w, h),
                                  _load_yolo_boxes(WEBCAM_DIR / "labels" / f"{files[i].stem}.ignore.txt", w, h)))
            return out
        raw_s, tr_s = subset(raw), subset(transported)
        acc = {}
        for name, data, imgsz in (("image_upload_640", raw_s, 640), ("live_code_raw_480", raw_s, 480),
                                  ("live_transported_480", tr_s, 480), ("live_transported_640", tr_s, 640),
                                  ("live_transported_800", tr_s, 800)):
            preds = [pred(s.image, imgsz=imgsz, conf=0.001) for s in data]
            r = evaluate(data, preds)
            acc[name] = {k: r[k] for k in ("images", "gt_objects", "tp", "fp", "fn", "precision", "recall", "f1", "fp_per_image",
                                           "fp_types", "top_confusions", "contradiction_pairs", "mAP50", "mAP50-95")}
            for c in SWEEP_THRESHOLDS:
                rc = evaluate(data, preds, op_conf=c)
                acc[name][f"at_conf_{c}"] = {k: rc[k] for k in ("tp", "fp", "fn", "precision", "recall")}
        disp = [Sample(files[i].name, transported[i], tr_s[k].gt, tr_s[k].ignore) for k, i in enumerate(labelled)]
        r = evaluate(disp, [live_disp[i] for i in labelled])
        acc["live_displayed_overlay"] = {k: r[k] for k in ("images", "gt_objects", "tp", "fp", "fn", "precision", "recall", "f1", "fp_types")}
        summary["accuracy_vs_manual_labels"] = acc
    summary["labelled_frames"] = [files[i].name for i in labelled]

    # 6) side-by-side examples: image-upload (left) vs live display (right)
    ex = WEBCAM_DIR / "examples"
    ex.mkdir(parents=True, exist_ok=True)
    picks = sorted(set([0, len(raw) // 3, 2 * len(raw) // 3, len(raw) - 1] + labelled[:6]))
    for i in picks:
        left, right = raw[i].copy(), transported[i].copy()
        for img, rows in ((left, image_dets[i]), (right, live_disp[i])):
            for r in rows:
                color = (40, 40, 220) if NAMES[int(r[5])].startswith("no_") else ((170, 120, 60) if int(r[5]) == PERSON_ID else (60, 170, 60))
                cv2.rectangle(img, (int(r[0]), int(r[1])), (int(r[2]), int(r[3])), color, 2)
                cv2.putText(img, f"{NAMES[int(r[5])]} {r[4]:.2f}", (int(r[0]), max(14, int(r[1]) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        cv2.putText(left, f"IMAGE UPLOAD imgsz {image_imgsz}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(right, f"LIVE {'analysed' if live_flag[i] else 'SKIPPED - stale boxes'} imgsz {live_imgsz}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imwrite(str(ex / f"compare_{files[i].stem}.jpg"), np.concatenate([left, right], 1), [cv2.IMWRITE_JPEG_QUALITY, 88])
    (WEBCAM_DIR / "webcam_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return summary



def run_webcam_sweep(sizes=(320, 416, 480, 512, 640, 800), ious=(0.5, 0.3), bitrate: int = 1_000_000) -> dict:
    """Labelled webcam frames: accuracy per inference size and NMS IoU, raw and VP8-transported."""
    meta = json.loads((WEBCAM_DIR / "capture_meta.json").read_text())
    files = [WEBCAM_DIR / "frames" / m["file"] for m in meta["frames"]]
    raw = [cv2.imread(str(f)) for f in files]
    transported = encode_sequence(raw, "libvpx", bitrate, float(meta.get("measured_fps") or 30.0))
    labelled = [i for i, f in enumerate(files) if (WEBCAM_DIR / "labels" / f"{f.stem}.txt").exists()]
    pred = Predictor()
    out = {}
    for stream_name, stream in (("raw", raw), ("vp8_1m", transported)):
        data = []
        for i in labelled:
            h, w = stream[i].shape[:2]
            data.append(Sample(files[i].name, stream[i], _load_yolo_boxes(WEBCAM_DIR / "labels" / f"{files[i].stem}.txt", w, h),
                               _load_yolo_boxes(WEBCAM_DIR / "labels" / f"{files[i].stem}.ignore.txt", w, h)))
        for imgsz in sizes:
            for iou in ious:
                preds = [pred(s.image, imgsz=imgsz, conf=0.001, iou=iou) for s in data]
                r = evaluate(data, preds)
                key = f"{stream_name}_{imgsz}_iou{iou}"
                out[key] = {k: r[k] for k in ("images", "gt_objects", "tp", "fp", "fn", "precision", "recall", "f1", "mAP50", "mAP50-95", "fp_types")}
                out[key]["per_class_recall"] = {c: v["recall"] for c, v in r["per_class_op"].items() if v["recall"] is not None}
                print(f"{key:22s} TP={r['tp']:2d} FP={r['fp']:2d} FN={r['fn']:2d} P={r['precision']:.3f} R={r['recall']:.3f} "
                      f"mAP50={r['mAP50']:.3f} recall/class={out[key]['per_class_recall']}")
    (WEBCAM_DIR / "webcam_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def _as_detections(rows: np.ndarray):
    from src.detection.detector import Detection

    return [Detection(int(r[5]), NAMES[int(r[5])], float(r[4]), *map(float, r[:4])) for r in rows]


def compliance_effect(samples: list[Sample], preds: list[np.ndarray], op_conf: float = OP_CONF) -> dict:
    """Separate detection errors from rule errors: run the SAME ComplianceAnalyzer on ground-truth boxes
    (confidence 1.0 = what the rules conclude with perfect detection) and on the model's boxes, then compare
    per worker and PPE item. Workers are matched by Person-box IoU >= 0.5."""
    from src.compliance.compliance_analyzer import ComplianceAnalyzer

    analyzer = ComplianceAnalyzer()
    c = Counter()
    for s, p in zip(samples, preds):
        gt_rows = np.concatenate([s.gt[:, 1:5], np.ones((len(s.gt), 1)), s.gt[:, :1]], 1) if len(s.gt) else np.zeros((0, 6))
        ref = analyzer.analyze(_as_detections(gt_rows))
        got = analyzer.analyze(_as_detections(p[p[:, 4] >= op_conf] if len(p) else p))
        gw = np.array([w.person.box for w in ref.workers]).reshape(-1, 4)
        pw = np.array([w.person.box for w in got.workers]).reshape(-1, 4)
        iou = box_iou(gw, pw)
        used = set()
        for i, w in enumerate(ref.workers):
            j = int(np.argmax(iou[i])) if iou.shape[1] else -1
            if j < 0 or iou[i, j] < 0.5 or j in used:
                c["worker_missed"] += 1
                c["violations_in_reference"] += len(w.violations)
                c["violations_lost_with_worker"] += len(w.violations)
                continue
            used.add(j)
            c["workers_matched"] += 1
            for item, a in w.items.items():
                b = got.workers[j].items[item]
                c[f"ref_{a.status}"] += 1
                c[f"ref_{a.status}->pred_{b.status}"] += 1
                if a.status == "potential_violation":
                    c["violations_in_reference"] += 1
        c["pred_workers_unmatched"] += len(got.workers) - len(used)
        c["pred_violations_on_unmatched_workers"] += sum(len(got.workers[j].violations) for j in range(len(got.workers)) if j not in used)
    found = c["ref_potential_violation->pred_potential_violation"]
    false_v = c["ref_compliant_evidence->pred_potential_violation"] + c["ref_uncertain->pred_potential_violation"]
    out = dict(c)
    out["violation_recall"] = round(found / c["violations_in_reference"], 4) if c["violations_in_reference"] else None
    out["false_violations"] = false_v + c["pred_violations_on_unmatched_workers"]
    return out


def run_compliance_effect(device: str = "mps") -> dict:
    samples = load_val_samples()
    pred = Predictor(device=device)
    out = {}
    cam = [resize_long(s, 1280) for s in samples]
    live = [Sample(s.name, codec_roundtrip(s.image, "libvpx", 1_000_000), s.gt) for s in cam]
    for name, data, imgsz in (("still_640", samples, 640), ("still_480", samples, 480), ("live_now", live, 480), ("live_640", live, 640)):
        preds = [pred(s.image, imgsz=imgsz, conf=OP_CONF) for s in data]
        out[name] = compliance_effect(data, preds)
        print(name, {k: out[name][k] for k in ("workers_matched", "worker_missed", "violations_in_reference", "violation_recall", "false_violations")})
    # webcam labelled frames
    if (WEBCAM_DIR / "capture_meta.json").exists():
        meta = json.loads((WEBCAM_DIR / "capture_meta.json").read_text())
        files = [WEBCAM_DIR / "frames" / m["file"] for m in meta["frames"]]
        raw = [cv2.imread(str(f)) for f in files]
        tr = encode_sequence(raw, "libvpx", 1_000_000, float(meta.get("measured_fps") or 30.0))
        lab = [i for i, f in enumerate(files) if (WEBCAM_DIR / "labels" / f"{f.stem}.txt").exists()]
        for name, stream, imgsz in (("webcam_image_640", raw, 640), ("webcam_live_480", tr, 480), ("webcam_live_320", tr, 320)):
            data = [Sample(files[i].name, stream[i], _load_yolo_boxes(WEBCAM_DIR / "labels" / f"{files[i].stem}.txt", 1280, 720)) for i in lab]
            preds = [pred(s.image, imgsz=imgsz, conf=OP_CONF) for s in data]
            out[name] = compliance_effect(data, preds)
            print(name, {k: out[name].get(k) for k in ("workers_matched", "worker_missed", "violations_in_reference", "violation_recall", "false_violations")})
    (AUDIT_DIR / "compliance_effect.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run_object_scale() -> dict:
    """Training-set box sizes (px after letterbox to 640) vs the labelled webcam objects at several imgsz."""
    root = source_dataset_dir()
    ids = {NAME_TO_ID["no_helmet"]: "no_helmet", NAME_TO_ID["no_vest"]: "no_vest", PERSON_ID: "Person"}
    stats = {n: [] for n in ids.values()}
    for p in sorted((root / "images" / "train").glob("*.jpg")):
        h, w = cv2.imread(str(p)).shape[:2]
        k = 640 / max(w, h)
        for r in parse_label_file(root / "labels" / "train" / f"{p.stem}.txt"):
            if r.class_id in ids:
                stats[ids[r.class_id]].append((r.height * h * k, r.width * w * k, (r.width * w) / max(1e-6, r.height * h)))
    out = {}
    for n, v in stats.items():
        v = np.array(v)
        out[n] = {"n": len(v), "height_px_at640": {q: round(float(np.percentile(v[:, 0], q)), 1) for q in (50, 90, 99, 100)},
                  "aspect_w_over_h": {q: round(float(np.percentile(v[:, 2], q)), 2) for q in (1, 50, 99)}}
    lab = WEBCAM_DIR / "labels" / "frame_0000.txt"
    if lab.exists():
        gt = _load_yolo_boxes(lab, 1280, 720)
        for row in gt:
            n = NAMES[int(row[0])]
            if n not in stats:
                continue
            bw, bh = row[3] - row[1], row[4] - row[2]
            v = np.array(stats[n])
            out[n]["webcam"] = {"box_wh_at_1280": [round(float(bw)), round(float(bh))], "aspect_w_over_h": round(float(bw / bh), 2),
                                "height_px_and_training_percentile": {imgsz: [round(float(bh * imgsz / 1280)),
                                                                              round(float((v[:, 0] < bh * imgsz / 1280).mean() * 100), 1)]
                                                                      for imgsz in (320, 480, 640)}}
    (AUDIT_DIR / "object_scale.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


def run_device_parity() -> dict:
    samples = load_val_samples()
    out, preds_by = {}, {}
    for dev in ("mps", "cpu"):
        pr = Predictor(device=dev)
        t = time.time()
        preds_by[dev] = [pr(s.image, imgsz=640, conf=0.001) for s in samples]
        r = evaluate(samples, preds_by[dev])
        out[dev] = {k: r[k] for k in ("mAP50", "mAP50-95", "precision", "recall", "tp", "fp", "fn")}
        out[dev]["seconds_200_images"] = round(time.time() - t, 1)
    same, maxdev = 0, 0.0
    for a, b in zip(preds_by["mps"], preds_by["cpu"]):
        a, b = a[a[:, 4] >= OP_CONF], b[b[:, 4] >= OP_CONF]
        a, b = a[np.lexsort((a[:, 0], a[:, 5]))], b[np.lexsort((b[:, 0], b[:, 5]))]
        if len(a) == len(b) and (a[:, 5] == b[:, 5]).all():
            same += 1
            if len(a):
                maxdev = max(maxdev, float(np.abs(a[:, :5] - b[:, :5]).max()))
    out.update(images_identical_class_sets=same, images=len(samples), max_abs_box_or_conf_difference=round(maxdev, 4))
    (AUDIT_DIR / "device_parity.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return out


def run_equivalence(limit: int = 30) -> dict:
    """The audit harness must reproduce the app's PPEDetector.detect exactly."""
    from src.detection.detector import PPEDetector

    det, pr = PPEDetector().load(), Predictor()
    res = Counter()
    key = lambda x: x[np.lexsort((x[:, 1], x[:, 0], x[:, 5]))]
    for s in load_val_samples(limit):
        for img, imgsz in ((s.image, 640), (resize_long(s, 1280).image, 480)):
            a = _det_rows(det.detect(img, image_size=imgsz))
            b = pr(img, imgsz=imgsz, conf=OP_CONF)
            c = pr(img, imgsz=imgsz, conf=0.001)
            c = c[c[:, 4] >= OP_CONF]
            res["checks"] += 1
            res["app_vs_audit_identical"] += int(len(a) == len(b) and np.allclose(key(a), key(b), atol=1e-3))
            res["filter_equivalence_identical"] += int(len(b) == len(c) and np.allclose(key(b), key(c), atol=1e-3))
    (AUDIT_DIR / "harness_equivalence.json").write_text(json.dumps(dict(res), indent=2), encoding="utf-8")
    print(dict(res))
    return dict(res)


def main() -> None:
    p = argparse.ArgumentParser(description="SiteGuard live/video accuracy audit")
    p.add_argument("what", choices=["conditions", "overlay", "latency", "colour", "webcam", "webcam-sweep", "compliance", "scale", "device", "equivalence", "all"])
    p.add_argument("--limit", type=int, default=None, help="use only the first N val images (quick runs)")
    p.add_argument("--only", nargs="*", default=None, help="condition names to run")
    a = p.parse_args()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    if a.what in ("colour", "all"):
        run_colour()
    if a.what in ("conditions", "all"):
        run_conditions(a.limit, a.only)
    if a.what in ("overlay", "all"):
        run_overlay(limit=a.limit or 40)
    if a.what in ("latency", "all"):
        run_latency()
    if a.what == "webcam":
        run_webcam()
    if a.what == "webcam-sweep":
        run_webcam_sweep()
    if a.what == "compliance":
        run_compliance_effect()
    if a.what == "scale":
        run_object_scale()
    if a.what == "device":
        run_device_parity()
    if a.what == "equivalence":
        run_equivalence()


if __name__ == "__main__":
    main()
