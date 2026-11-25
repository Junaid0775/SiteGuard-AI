"""Fix 1: rate-distortion of the real aiortc VP8 encoder on demanding synthetic video (no camera, no network).

Content: a dataset image panned about 4 px per frame, with Gaussian sensor-like noise (sigma 3), and the real pipeline's
YOLO26n detections drawn on every frame (draw_compliance). Every frame is encoded by aiortc's Vp8Encoder at a fixed target
and decoded by its Vp8Decoder. PSNR compares the decoded frame with the frame given to the encoder, so it isolates the loss
of the return-video encode. The first 30 frames are excluded while rate control settles. Nothing is saved except numbers.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.utils.paths import source_dataset_dir  # noqa: E402  (sets YOLO_CONFIG_DIR before ultralytics)

import aiortc.codecs.vpx as vpx  # noqa: E402
import av  # noqa: E402
from aiortc.jitterbuffer import JitterFrame  # noqa: E402

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceRules  # noqa: E402
from src.detection.annotate import draw_compliance  # noqa: E402
from src.detection.detector import PPEDetector  # noqa: E402

SIZES = ((640, 360), (960, 540), (1280, 720))
BITRATES = (1_500_000, 2_500_000, 4_000_000, 6_000_000, 8_000_000)  # 1.5 Mbit/s = aiortc's library cap
N, SKIP, FPS = 150, 30, 30


def make_frames(src, w, h, det, analyzer):
    s = max(1.25 * w / src.shape[1], 1.25 * h / src.shape[0])
    big = cv2.resize(src, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
    rng, (H, W), out = np.random.default_rng(0), big.shape[:2], []
    for i in range(N):
        phase = abs((i % 120) / 60 - 1)
        x, y = int((W - w) * phase), int((H - h) * (1 - phase))
        f = np.clip(big[y:y + h, x:x + w].astype(np.float32) + rng.normal(0, 3.0, (h, w, 3)), 0, 255).astype(np.uint8)
        out.append(draw_compliance(f, analyzer.analyze(det.detect(f))))
    return out


def psnr(a, b):
    mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def run(frames, bitrate):
    vpx.DEFAULT_BITRATE, vpx.MIN_BITRATE, vpx.MAX_BITRATE = bitrate, bitrate, bitrate
    enc, dec = vpx.Vp8Encoder(), vpx.Vp8Decoder()
    values, ms, size, empty = [], [], 0, 0
    for i, img in enumerate(frames):
        f = av.VideoFrame.from_ndarray(img, format="bgr24")
        f.pts, f.time_base = i * 3000, Fraction(1, 90000)
        t0 = time.perf_counter()
        payloads, ts = enc.encode(f, force_keyframe=i == 0)
        dt = (time.perf_counter() - t0) * 1000
        data = b"".join(vpx.vp8_depayload(p) for p in payloads)
        if i >= SKIP:
            ms.append(dt)
            size += len(data)
            empty += not data
        if data:
            decoded = dec.decode(JitterFrame(data=data, timestamp=ts))
            if decoded and i >= SKIP:
                values.append(psnr(img, decoded[0].to_ndarray(format="bgr24")))
    ms.sort()
    return {"psnr_db": round(statistics.mean(values), 2), "psnr_p05_db": round(sorted(values)[int(len(values) * .05)], 2),
            "actual_kbps": round(size * 8 / ((N - SKIP) / FPS) / 1000), "enc_ms_mean": round(statistics.mean(ms), 2),
            "enc_ms_p95": round(ms[int(len(ms) * .95)], 2), "frames_not_encoded": empty}


det = PPEDetector().load()
analyzer = ComplianceAnalyzer(ComplianceRules.from_settings())
src = cv2.imread(str(source_dataset_dir() / "images" / "val" / "ultralytics-ppe-nov2026-022.jpg"))
results = {}
for w, h in SIZES:
    frames = make_frames(src, w, h, det, analyzer)
    results[f"{w}x{h}"] = {f"{b / 1e6:g}M": run(frames, b) for b in BITRATES}
    for k, v in results[f"{w}x{h}"].items():
        print(f"{w}x{h} {k}: {v}", flush=True)
    del frames
(ROOT / "experiments/camera_quality_audit/logs/bench_codec_rd.json").write_text(json.dumps(results, indent=1))
