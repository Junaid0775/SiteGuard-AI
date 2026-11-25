"""Before/after measurements for R1 (frame synchronisation) and R2 (inference size 640).

    .venv/bin/python scripts/engineering/measure_r1_r2.py

Writes:
  experiments/engineering_phase/pipeline_r1/displayed_accuracy.json   factorial: frame policy x imgsz x motion
  experiments/engineering_phase/pipeline_r1/realtime_latency.json     paced 30 fps stream through LiveFrameProcessor
  experiments/engineering_phase/pipeline_r1/video_before_after.json   offline video: old stride-5 vs new policies
  experiments/engineering_phase/resolution_r2/latency_480_vs_640.json live callback cost per imgsz (MPS)
Only real model outputs and real ground truth (val split) are scored.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.compliance.compliance_analyzer import ComplianceAnalyzer  # noqa: E402
from src.detection.camera_processor import LiveFrameProcessor  # noqa: E402
from src.detection.detector import PPEDetector  # noqa: E402
from src.detection.video_processor import process_video  # noqa: E402
from src.evaluation.live_audit import OP_CONF, Predictor, evaluate, load_val_samples, pan_sequence  # noqa: E402
from src.events.event_manager import EventManager  # noqa: E402
from src.utils.diagnostics import use_temporary_evidence_dir  # noqa: E402

# Fix 6 (2026-11-23): diagnostic runs never write into production evidence storage.
DIAGNOSTIC_EVIDENCE_DIR = use_temporary_evidence_dir()

R1 = ROOT / "experiments/engineering_phase/pipeline_r1"
R2 = ROOT / "experiments/engineering_phase/resolution_r2"


def displayed_accuracy(limit: int = 40, n_frames: int = 15, speeds=(0, 4, 10, 20)) -> dict:
    """Score what is DISPLAYED on every frame.

    old policy  : boxes of the last analysed frame j drawn on the current frame k (pre-R1 behaviour).
    new policy  : every frame analysed and drawn with its own boxes (R1 default, every_n = 1).
    held policy : R1 with every_n = 3 - the displayed IMAGE is frame j with j's own boxes, so association is
                  always correct; the cost is display age (k - j frames), reported separately.
    """
    samples = load_val_samples(limit)
    pred = Predictor()
    out = {}
    for imgsz in (480, 640):
        for speed in speeds:
            seqs = [pan_sequence(s, n_frames, speed) for s in samples]
            preds = [[pred(f.image, imgsz=imgsz, conf=OP_CONF) for f in seq] for seq in seqs]
            for policy, n in (("old_every3", 3), ("new_every1", 1), ("held_every3", 3)):
                shown_frames, shown_boxes, stale, ages = [], [], 0, []
                for seq, ps in zip(seqs, preds):
                    for k, f in enumerate(seq):
                        j = k - (k % n)
                        if policy == "old_every3":
                            shown_frames.append(f)          # current image ...
                            shown_boxes.append(ps[j])       # ... with boxes of frame j
                            stale += int(j != k)
                        else:
                            shown_frames.append(seq[j])     # image and boxes of the same frame
                            shown_boxes.append(ps[j])
                        ages.append(k - j)
                r = evaluate(shown_frames, shown_boxes)
                out[f"imgsz{imgsz}_speed{speed}_{policy}"] = {
                    "imgsz": imgsz, "speed_px_per_frame": speed, "policy": policy, "displayed_frames": len(shown_frames),
                    "tp": r["tp"], "fp": r["fp"], "fn": r["fn"], "precision": round(r["precision"], 4),
                    "recall": round(r["recall"], 4), "f1": round(r["f1"], 4),
                    "stale_box_frames": stale, "stale_box_rate": round(stale / len(shown_frames), 4),
                    "mean_display_age_frames": round(float(np.mean(ages)), 3)}
                print(f"imgsz={imgsz} speed={speed:2d} {policy:12s} P={r['precision']:.3f} R={r['recall']:.3f} "
                      f"stale={stale}/{len(shown_frames)} age={np.mean(ages):.2f}", flush=True)
    return out


def clip_frames(n: int = 300) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(ROOT / "data/test_media/test_site_clip.mp4"))
    frames = []
    while len(frames) < n:
        ok, f = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        frames.append(cv2.resize(f, (1280, 720)))
    cap.release()
    return frames


def realtime_run(det: PPEDetector, imgsz: int, every_n: int, frames: list[np.ndarray], fps: float = 30.0,
                 extra_load_ms: float = 0.0) -> dict:
    """Producer thread delivers frames at `fps`; consumer behaves like streamlit-webrtc's worker
    (takes all queued frames, hands the newest to process_latest)."""
    proc = LiveFrameProcessor(det, ComplianceAnalyzer(), None, process_every_n=every_n, image_size=imgsz)
    queue, lock, done = [], threading.Lock(), threading.Event()

    def producer():
        t0 = time.monotonic()
        for i, f in enumerate(frames):
            target = t0 + i / fps
            delay = target - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            with lock:
                queue.append(f)
        done.set()

    th = threading.Thread(target=producer)
    th.start()
    delivered = 0
    while not (done.is_set() and not queue):
        with lock:
            batch, queue[:] = list(queue), []
        if not batch:
            time.sleep(0.001)
            continue
        delivered += len(batch)
        if extra_load_ms:
            time.sleep(extra_load_ms / 1000)  # simulated extra work, e.g. a slower model
        proc.process_latest(batch[-1], dropped=len(batch) - 1)
    th.join()
    s = proc.snapshot()
    keep = ("inference_imgsz", "process_every_n", "frames_received", "frames_dropped_queue", "frames_analysed",
            "frames_held", "frames_rendered", "errors", "inference_ms", "receive_to_render_ms", "displayed_result_age_ms",
            "received_fps", "analysed_fps", "rendered_fps")
    res = {k: s[k] for k in keep}
    res.update(source_fps=fps, frames_delivered=delivered, extra_load_ms=extra_load_ms)
    return res


def video_before_after(det: PPEDetector) -> dict:
    clip = ROOT / "data/test_media/test_site_clip.mp4"
    out_dir = ROOT / "experiments/engineering_phase/pipeline_r1/video_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, stride in (("stride5_new_policy", 5), ("stride1_every_frame", 1)):
        em = EventManager(None, "video", clip.name, save_evidence=False)
        t0 = time.time()
        s = process_video(clip, out_dir / f"{name}.mp4", det, ComplianceAnalyzer(), em, frame_stride=stride, image_size=640)
        res[name] = {"frame_stride": stride, "frames_read": s.frames_read, "frames_analysed": s.frames_processed,
                     "frames_not_analysed_tagged": s.frames_not_analysed, "frames_with_reused_boxes": 0,
                     "seconds": round(time.time() - t0, 2), "events": len(s.events), "suppressed_repeats": s.suppressed_repeats,
                     "inference_ms": s.inference_ms, "frame_log": str(s.frame_log_path.relative_to(ROOT)),
                     "output_size": s.output_size, "fps": s.fps}
        print(name, res[name], flush=True)
    # Pre-R1 behaviour (from the code in the source snapshot): stride 5 and boxes of frame k - k%5 drawn on frame k.
    res["pre_R1_stride5_reference"] = {"frame_stride": 5, "frames_read": 270, "frames_analysed": 54,
                                       "frames_with_reused_boxes": 270 - 54,
                                       "note": "frames_with_reused_boxes follows from the old code (video_processor.py:116); "
                                               "event selection on analysed frames is unchanged, so its events equal "
                                               "stride5_new_policy"}
    return res


def main() -> None:
    R1.mkdir(parents=True, exist_ok=True)
    R2.mkdir(parents=True, exist_ok=True)
    print("== displayed accuracy (factorial)", flush=True)
    (R1 / "displayed_accuracy.json").write_text(json.dumps(displayed_accuracy(), indent=2))
    det = PPEDetector().load()
    frames = clip_frames(300)
    for _ in range(5):
        det.detect(frames[0])
    print("== real-time paced runs", flush=True)
    rt = {}
    for name, imgsz, n, load in (("pre_R1_R2_every3_480", 480, 3, 0.0), ("post_R1_R2_every1_640", 640, 1, 0.0),
                                 ("post_every1_640_with_40ms_extra_load", 640, 1, 40.0)):
        rt[name] = realtime_run(det, imgsz, n, frames, extra_load_ms=load)
        print(name, {k: rt[name][k] for k in ("frames_received", "frames_dropped_queue", "frames_analysed", "frames_held",
                                              "analysed_fps", "rendered_fps")}, flush=True)
    (R1 / "realtime_latency.json").write_text(json.dumps(rt, indent=2))
    print("== live callback cost per imgsz", flush=True)
    lat = {}
    for imgsz in (480, 640):
        proc = LiveFrameProcessor(det, ComplianceAnalyzer(), None, process_every_n=1, image_size=imgsz)
        for f in frames[:200]:
            proc.process(f)
        s = proc.snapshot()
        lat[f"imgsz{imgsz}"] = {"inference_ms": s["inference_ms"], "receive_to_render_ms": s["receive_to_render_ms"],
                                "max_throughput_fps": s["analysed_fps"]}
        print(imgsz, lat[f"imgsz{imgsz}"], flush=True)
    (R2 / "latency_480_vs_640.json").write_text(json.dumps(lat, indent=2))
    print("== offline video", flush=True)
    (R1 / "video_before_after.json").write_text(json.dumps(video_before_after(det), indent=2, default=str))


if __name__ == "__main__":
    main()
