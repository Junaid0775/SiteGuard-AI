"""Identical evaluation procedure for any SiteGuard checkpoint (spec §3 baseline, reused for §9 comparison).

    .venv/bin/python scripts/engineering/evaluate_model.py --weights models/trained/best.pt \
        --name yolo26n --out experiments/engineering_phase/baseline/yolo26n

Produces in --out:
  ultralytics_val/            Ultralytics model.val() plots (confusion matrix, PR/F1 curves, val batches)
  metrics_ultralytics.json    overall + per-class P, R, AP50, AP50-95, instances, speed (val defaults)
  confusion_matrix.csv        Ultralytics confusion matrix (computed at val conf 0.001, so background counts are inflated)
  confusion_matrix_conf0.25.csv  confusion matrix at the app threshold (conf 0.25, class-agnostic IoU 0.5)
  operating_point.json        app settings (conf 0.25, NMS IoU 0.5): TP/FP/FN per class, FP types, confusions
  stratified_recall.csv       recall at the operating point by class x {size, viewpoint, brightness, image group}
  latency.json                model load time, first-call time, warm per-image latency (MPS)
  predictions_conf0.001.npz   raw predictions for all val images (for bootstrap / later comparison)
  examples/                   images with the most errors: GT white, correct green, false positive red
  run_config.json             exact settings, versions, checkpoint hash, timestamps
Nothing outside --out is written. The checkpoint is only read.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.evaluation.live_audit import (  # noqa: E402
    NAMES,
    OP_CONF,
    Predictor,
    box_iou,
    evaluate,
    load_val_samples,
    match_greedy,
)
from src.utils.dataset_tools import prepare_default_dataset  # noqa: E402
from src.utils.paths import PROJECT_ROOT, VIEWPOINT_CSV, configure_ultralytics  # noqa: E402

SIZE_BUCKETS = [("small(<0.01)", 0.0, 0.01), ("medium(0.01-0.10)", 0.01, 0.10), ("large(>=0.10)", 0.10, 9.0)]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gt_matched_at50(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Boolean per GT box: matched by a prediction (same greedy rule as match_greedy, IoU 0.5)."""
    matched = np.zeros(len(gt), bool)
    if len(pred) == 0 or len(gt) == 0:
        return matched
    pred = pred[np.argsort(-pred[:, 4], kind="stable")]
    iou = box_iou(gt[:, 1:5], pred[:, :4]) * (gt[:, 0][:, None] == pred[:, 5][None, :])
    for j in range(len(pred)):
        avail = np.where(matched, 0.0, iou[:, j])
        k = int(np.argmax(avail))
        if avail[k] >= 0.5:
            matched[k] = True
    return matched


def confusion_at_operating_point(samples, preds, conf: float = OP_CONF, iou_thr: float = 0.5) -> np.ndarray:
    """Confusion matrix at the app threshold: class-agnostic greedy matching (descending confidence, IoU >= 0.5).
    Rows = predicted class (+ background row = missed GT), columns = true class (+ background column = false box)."""
    nc = len(NAMES)
    cm = np.zeros((nc + 1, nc + 1), int)
    for s, p in zip(samples, preds):
        po = p[p[:, 4] >= conf] if len(p) else p
        po = po[np.argsort(-po[:, 4], kind="stable")] if len(po) else po
        used = np.zeros(len(s.gt), bool)
        iou = box_iou(po[:, :4], s.gt[:, 1:5]) if len(po) and len(s.gt) else np.zeros((len(po), len(s.gt)))
        for j, row in enumerate(po):
            cand = np.where(used, 0.0, iou[j]) if len(s.gt) else np.zeros(0)
            k = int(np.argmax(cand)) if len(cand) else -1
            if k >= 0 and cand[k] >= iou_thr:
                used[k] = True
                cm[int(row[5]), int(s.gt[k, 0])] += 1
            else:
                cm[int(row[5]), nc] += 1
        for g, u in zip(s.gt, used):
            if not u:
                cm[nc, int(g[0])] += 1
    return cm


def ultralytics_val(weights: Path, out: Path, device: str, imgsz: int, batch: int) -> dict:
    configure_ultralytics()
    from ultralytics import YOLO

    data_yaml = prepare_default_dataset()
    model = YOLO(str(weights))
    t0 = time.time()
    m = model.val(data=str(data_yaml), split="val", imgsz=imgsz, batch=batch, device=device, plots=True,
                  project=str(out), name="ultralytics_val", exist_ok=True, verbose=False)
    seconds = time.time() - t0
    per_class = {}
    for i, cid in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        per_class[model.names[int(cid)]] = {"precision": round(float(p), 4), "recall": round(float(r), 4),
                                            "AP50": round(float(ap50), 4), "AP50-95": round(float(ap), 4),
                                            "instances": int(m.nt_per_class[int(cid)])}
    cm = m.confusion_matrix.matrix
    labels = [model.names[i] for i in range(len(model.names))] + ["background"]
    with open(out / "confusion_matrix.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["predicted \\ true"] + labels)
        for i, row in enumerate(cm):
            w.writerow([labels[i]] + [int(v) for v in row])
    args = m.args if hasattr(m, "args") else None
    res = {
        "dataset_yaml": str(data_yaml), "split": "val", "imgsz": imgsz, "batch": batch, "device": device,
        "conf": 0.001, "iou": 0.7, "note": "Ultralytics val defaults (conf 0.001, NMS IoU 0.7, max_det 300)",
        "seconds": round(seconds, 1),
        "overall": {"precision": round(float(m.box.mp), 4), "recall": round(float(m.box.mr), 4),
                    "mAP50": round(float(m.box.map50), 4), "mAP50-95": round(float(m.box.map), 4)},
        "per_class": per_class, "speed_ms_per_image": {k: round(float(v), 2) for k, v in m.speed.items()},
        "images": int(getattr(m, "seen", 0)) or None,
    }
    (out / "metrics_ultralytics.json").write_text(json.dumps(res, indent=2))
    return res


def latency(weights: Path, samples, device: str, imgsz: int, n: int = 100) -> dict:
    configure_ultralytics()
    from ultralytics import YOLO

    t0 = time.perf_counter()
    model = YOLO(str(weights))
    t_load = time.perf_counter() - t0
    t1 = time.perf_counter()
    model.predict(samples[0].image, imgsz=imgsz, device=device, conf=OP_CONF, verbose=False)
    t_first = time.perf_counter() - t1
    walls, pre, inf, post = [], [], [], []
    for s in (samples * 3)[:n]:
        t = time.perf_counter()
        r = model.predict(s.image, imgsz=imgsz, device=device, conf=OP_CONF, verbose=False)[0]
        walls.append((time.perf_counter() - t) * 1000)
        pre.append(r.speed["preprocess"]); inf.append(r.speed["inference"]); post.append(r.speed["postprocess"])
    stat = lambda v: {"mean": round(float(np.mean(v)), 2), "median": round(float(np.median(v)), 2),
                      "p95": round(float(np.percentile(v, 95)), 2), "max": round(float(np.max(v)), 2)}
    return {"device": device, "imgsz": imgsz, "runs": len(walls), "model_load_s": round(t_load, 3),
            "first_predict_s (incl. backend setup + warm-up)": round(t_first, 3),
            "wall_ms_per_image (full-res val images, incl. decode-free preprocessing)": stat(walls),
            "ultralytics_preprocess_ms": stat(pre), "ultralytics_inference_ms": stat(inf), "ultralytics_postprocess_ms": stat(post)}


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--weights", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--device", default="mps")
    a.add_argument("--imgsz", type=int, default=640)
    a.add_argument("--batch", type=int, default=8)
    args = a.parse_args()
    weights = (PROJECT_ROOT / args.weights).resolve() if not Path(args.weights).is_absolute() else Path(args.weights)
    out = (PROJECT_ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat(timespec="seconds")

    print("1/5 Ultralytics validation ...", flush=True)
    uv = ultralytics_val(weights, out, args.device, args.imgsz, args.batch)
    print("   ", uv["overall"], flush=True)

    print("2/5 operating point (app settings) ...", flush=True)
    samples = load_val_samples()
    pred = Predictor(weights=weights, device=args.device)
    preds = [pred(s.image, imgsz=args.imgsz, conf=0.001, iou=0.5) for s in samples]
    np.savez_compressed(out / "predictions_conf0.001.npz", **{s.name: p for s, p in zip(samples, preds)})
    op = evaluate(samples, preds)
    op["settings"] = {"conf": OP_CONF, "nms_iou": 0.5, "imgsz": args.imgsz, "device": args.device, "agnostic_nms": False}
    (out / "operating_point.json").write_text(json.dumps(op, indent=2))
    cm = confusion_at_operating_point(samples, preds)
    labels = [NAMES[i] for i in range(len(NAMES))] + ["background"]
    with open(out / "confusion_matrix_conf0.25.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["predicted \\ true"] + labels)
        for i, row in enumerate(cm):
            w.writerow([labels[i]] + [int(v) for v in row])
    print(f"    P={op['precision']:.3f} R={op['recall']:.3f} TP={op['tp']} FP={op['fp']} FN={op['fn']}", flush=True)

    print("3/5 stratified recall ...", flush=True)
    vp = {r["filename"]: r["viewpoint"] for r in csv.DictReader(open(VIEWPOINT_CSV))} if VIEWPOINT_CSV.exists() else {}
    grp = {r["filename"]: r["image_group"] for r in csv.DictReader(open(VIEWPOINT_CSV))} if VIEWPOINT_CSV.exists() else {}
    bright = {s.name: float(cv2.cvtColor(s.image, cv2.COLOR_BGR2GRAY).mean()) for s in samples}
    t1, t2 = np.percentile(list(bright.values()), [33.3, 66.7])
    tally = defaultdict(lambda: [0, 0])  # key -> [matched, total]
    for s, p in zip(samples, preds):
        h, w = s.image.shape[:2]
        po = p[p[:, 4] >= OP_CONF] if len(p) else p
        matched = gt_matched_at50(po, s.gt)
        b = bright[s.name]
        bcat = "dark" if b < t1 else ("mid" if b < t2 else "bright")
        for g, ok in zip(s.gt, matched):
            c = NAMES[int(g[0])]
            area = (g[3] - g[1]) * (g[4] - g[2]) / (w * h)
            scat = next(n for n, lo, hi in SIZE_BUCKETS if lo <= area < hi)
            for dim, val in (("size", scat), ("viewpoint", vp.get(s.name, "unknown")), ("brightness", bcat),
                             ("image_group", grp.get(s.name, "unknown")), ("all", "all")):
                tally[(c, dim, val)][0] += int(ok)
                tally[(c, dim, val)][1] += 1
    with open(out / "stratified_recall.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "dimension", "value", "matched", "gt_objects", "recall"])
        for (c, dim, val), (m_, n_) in sorted(tally.items()):
            w.writerow([c, dim, val, m_, n_, round(m_ / n_, 4) if n_ else ""])

    print("4/5 latency ...", flush=True)
    lat = latency(weights, samples, args.device, args.imgsz)
    (out / "latency.json").write_text(json.dumps(lat, indent=2))
    print("   ", lat["ultralytics_inference_ms"], flush=True)

    print("5/5 examples ...", flush=True)
    ex = out / "examples"
    ex.mkdir(exist_ok=True)
    scored = []
    for s, p in zip(samples, preds):
        po = p[p[:, 4] >= OP_CONF] if len(p) else p
        po = po[np.argsort(-po[:, 4], kind="stable")] if len(po) else po
        ok = match_greedy(po, s.gt)[:, 0] if len(po) else np.zeros(0, bool)
        fn = int((~gt_matched_at50(po, s.gt)).sum())
        scored.append((int((~ok).sum()) + fn, s, po, ok))
    for k, (_, s, po, ok) in enumerate(sorted(scored, key=lambda t: -t[0])[:8]):
        img = s.image.copy()
        th = max(1, img.shape[1] // 700)
        for c, x1, y1, x2, y2 in s.gt:
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 255, 255), th)
        for row, good in zip(po, ok):
            color = (60, 170, 60) if good else (40, 40, 220)
            cv2.rectangle(img, (int(row[0]), int(row[1])), (int(row[2]), int(row[3])), color, th + 1)
            cv2.putText(img, f"{NAMES[int(row[5])]} {row[4]:.2f}", (int(row[0]), max(14, int(row[1]) - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45 * th + 0.2, color, th, cv2.LINE_AA)
        cv2.imwrite(str(ex / f"{k}_{Path(s.name).stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    import torch
    import ultralytics

    cfg = {"name": args.name, "weights": str(weights), "weights_sha256": sha256(weights),
           "weights_size_bytes": weights.stat().st_size, "started": started,
           "finished": datetime.now().isoformat(timespec="seconds"), "device": args.device, "imgsz": args.imgsz,
           "val_batch": args.batch, "val_conf": 0.001, "val_nms_iou": 0.7, "operating_conf": OP_CONF,
           "operating_nms_iou": 0.5, "max_det": 300, "precision_mode": "fp32", "val_images": len(samples),
           "versions": {"python": platform.python_version(), "torch": torch.__version__, "ultralytics": ultralytics.__version__},
           "command": " ".join(sys.argv)}
    (out / "run_config.json").write_text(json.dumps(cfg, indent=2))
    print("done ->", out)


if __name__ == "__main__":
    main()
