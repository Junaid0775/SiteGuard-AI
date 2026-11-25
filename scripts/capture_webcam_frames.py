"""Capture a short burst of raw webcam frames for the live-detection audit (REPORT-009).

    .venv/bin/python scripts/capture_webcam_frames.py --seconds 5

Frames are saved (JPEG quality 98) to experiments/live_audit/webcam/frames/ together
with capture timestamps. They are used to run the SAME frames through the
image-upload pipeline and the live pipeline (python -m src.evaluation.live_audit webcam).

Privacy: the frames show whoever/whatever is in front of the camera. They stay on
this computer (the folder is git-ignored). Delete the folder when the audit is done.
On macOS the first run may ask for camera permission for the terminal / VS Code.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.paths import EXPERIMENTS_DIR  # noqa: E402

OUT_DIR = EXPERIMENTS_DIR / "live_audit" / "webcam" / "frames"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--seconds", type=float, default=5.0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--warmup", type=float, default=1.5, help="seconds to let auto-exposure settle (not saved)")
    a = p.parse_args()

    cap = cv2.VideoCapture(a.camera, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        raise SystemExit("Camera could not be opened (no camera, or camera permission denied for this app).")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    t_end_warmup = time.time() + a.warmup
    while time.time() < t_end_warmup:
        cap.read()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta, start = [], time.time()
    i = 0
    while time.time() - start < a.seconds:
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        name = f"frame_{i:04d}.jpg"
        cv2.imwrite(str(OUT_DIR / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 98])
        meta.append({"file": name, "t": round(time.time() - start, 4), "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                     "width": frame.shape[1], "height": frame.shape[0]})
        i += 1
    cap.release()
    if not meta:
        raise SystemExit("No frames received (camera busy or permission denied).")
    fps = len(meta) / max(1e-6, meta[-1]["t"])
    (OUT_DIR.parent / "capture_meta.json").write_text(json.dumps({"frames": meta, "measured_fps": round(fps, 2),
                                                                   "requested": [a.width, a.height]}, indent=2))
    print(f"Saved {len(meta)} frames ({meta[0]['width']}x{meta[0]['height']}, {fps:.1f} fps) to {OUT_DIR}")


if __name__ == "__main__":
    main()
