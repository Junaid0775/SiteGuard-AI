"""Evaluation protocol v1 for the accuracy-improvement programme (specification §4, REPORT-020).

    .venv/bin/python scripts/accuracy/evaluate.py --weights <pt> --split dev --out <dir> [--imgsz 640]
    .venv/bin/python scripts/accuracy/evaluate.py --weights <pt> --split test --out <dir> \
        --locked-test-purpose "<why>" --frozen-sha256 <sha256 of the weights>

Splits come from experiments/accuracy_improvement/splits/{train,dev,test}.txt and are read through the derived
dataset experiments/accuracy_improvement/datasets/v1_original_labels/ (symlinks to the original files).

Outputs in --out:
  metrics_ultralytics.json      Ultralytics val (conf 0.001, NMS IoU 0.7, max_det 300): P, R, mAP50, mAP50-95,
                                per-class P/R/AP50/AP50-95/instances   [primary, comparable with earlier reports]
  confusion_matrix_ultralytics.csv  Ultralytics matrix (computed at conf 0.001: background counts are inflated)
  operating_point.json          application settings (conf --op-conf, NMS IoU --op-nms): TP/FP/FN and P/R per class,
                                FP types (duplicate / wrong_class / localization / background), contradiction pairs,
                                plus mAP50/mAP50-95 from the same predictions ("audit evaluator", NMS --op-nms)
  confusion_matrix_op.csv       class-agnostic greedy matching at the operating point (+ background row/column)
  size_strata.csv               recall at the operating point per class x size band (short side at 640 px; area band)
  family_strata.json            operating-point and AP results per filename family (source / ultralytics-ppe)
  predictions.npz               all predictions at conf 0.001 (NMS --op-nms), keyed by image file name
  latency.json                  synchronised per-image wall clock (predict + copy to numpy) and MPS memory
  run_config.json               settings, versions, weights SHA-256, split-list SHA-256, timestamps
  summary.json                  headline numbers used by the comparison tables
The locked test (--split test) requires --locked-test-purpose and --frozen-sha256 equal to the weights' SHA-256,
and every use is appended to experiments/accuracy_improvement/qualification/locked_test_access_log.csv.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "engineering"))
from src.evaluation.live_audit import NAMES, Predictor, Sample, box_iou, evaluate  # noqa: E402
from src.utils.dataset_tools import parse_label_file  # noqa: E402
from evaluate_model import confusion_at_operating_point  # noqa: E402

AI = ROOT / "experiments" / "accuracy_improvement"
SPLITS = AI / "splits"
DEFAULT_DS = AI / "datasets" / "v1_original_labels"
LEDGER = AI / "qualification" / "locked_test_access_log.csv"
MISSING = ["no_helmet", "no_gloves", "no_goggle", "no_boots", "no_vest"]
SHORT_BANDS = [("<8px", 0, 8), ("8-16px", 8, 16), ("16-32px", 16, 32), (">=32px", 32, 1e9)]
AREA_BANDS = [("tiny(<0.1%)", 0, 0.001), ("small(0.1-1%)", 0.001, 0.01), ("medium(1-10%)", 0.01, 0.10), ("large(>=10%)", 0.10, 9)]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def family(name: str) -> str:
    return "source" if name.startswith("source-") else "ultralytics-ppe"


def split_yaml(ds: Path, split: str, out: Path) -> Path:
    if split == "dev":
        return ds / "dev.yaml"
    if split == "test":
        # Ultralytics 8.4 requires a 'train:' key in every data YAML. locked_test.yaml deliberately has none and stays
        # unchanged; a derived copy with an EMPTY 'train:' (no images, unusable for training) is written next to the
        # results and used for validation only. (Fix of 2026-11-23: the first two locked-test attempts failed on this
        # check before any image or label was read; see qualification/locked_test_access_notes.md.)
        y = out / "_locked_test_eval.yaml"
        y.write_text((ds / "locked_test.yaml").read_text().rstrip("\n") + "\ntrain:  # empty on purpose: evaluation only\n")
        return y
    y = out / f"_{split}.yaml"
    names = "\n".join(f"  {k}: {v}" for k, v in NAMES.items())
    y.write_text(f"path: {ds}\ntrain:  # empty on purpose: evaluation only\nval: images/{split}\nnames:\n{names}\n")
    return y


def ultralytics_val(weights: Path, data: Path, out: Path, imgsz: int, batch: int, device: str) -> dict:
    from ultralytics import YOLO
    model = YOLO(str(weights))
    t0 = time.time()
    m = model.val(data=str(data), split="val", imgsz=imgsz, batch=batch, device=device, conf=0.001, iou=0.7,
                  plots=True, project=str(out), name="ultralytics_val", exist_ok=True, verbose=False)
    per_class = {}
    for i, cid in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        per_class[model.names[int(cid)]] = {"precision": round(float(p), 4), "recall": round(float(r), 4),
                                            "AP50": round(float(ap50), 4), "AP50-95": round(float(ap), 4),
                                            "instances": int(m.nt_per_class[int(cid)])}
    labels = [model.names[i] for i in range(len(model.names))] + ["background"]
    with open(out / "confusion_matrix_ultralytics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["predicted \\ true"] + labels)
        for i, row in enumerate(m.confusion_matrix.matrix):
            w.writerow([labels[i]] + [int(v) for v in row])
    res = {"settings": {"conf": 0.001, "nms_iou": 0.7, "max_det": 300, "imgsz": imgsz, "batch": batch, "device": device,
                        "data": str(data.relative_to(ROOT))},
           "seconds": round(time.time() - t0, 1),
           "overall": {"precision": round(float(m.box.mp), 4), "recall": round(float(m.box.mr), 4),
                       "mAP50": round(float(m.box.map50), 4), "mAP50-95": round(float(m.box.map), 4)},
           "per_class": per_class, "speed_ms_per_image": {k: round(float(v), 2) for k, v in m.speed.items()}}
    (out / "metrics_ultralytics.json").write_text(json.dumps(res, indent=2))
    return res


def load_gt(ds: Path, rel: str) -> tuple[np.ndarray, tuple[int, int]]:
    img = cv2.imread(str(ds / rel))
    h, w = img.shape[:2]
    rows = parse_label_file(ds / rel.replace("images/", "labels/", 1).rsplit(".", 1)[0].__add__(".txt"))
    gt = np.array([[r.class_id, (r.x_center - r.width / 2) * w, (r.y_center - r.height / 2) * h,
                    (r.x_center + r.width / 2) * w, (r.y_center + r.height / 2) * h] for r in rows], dtype=float).reshape(-1, 5)
    return gt, img


def matched_gt(pred: np.ndarray, gt: np.ndarray, op_conf: float) -> np.ndarray:
    """Per GT box: matched by a same-class prediction >= op_conf (greedy by confidence, IoU >= 0.5)."""
    matched = np.zeros(len(gt), bool)
    p = pred[pred[:, 4] >= op_conf] if len(pred) else pred
    if len(p) == 0 or len(gt) == 0:
        return matched
    p = p[np.argsort(-p[:, 4], kind="stable")]
    iou = box_iou(gt[:, 1:5], p[:, :4]) * (gt[:, 0][:, None] == p[:, 5][None, :])
    for j in range(len(p)):
        avail = np.where(matched, 0.0, iou[:, j])
        k = int(np.argmax(avail))
        if avail[k] >= 0.5:
            matched[k] = True
    return matched


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--weights", required=True)
    a.add_argument("--split", choices=["dev", "test", "train"], default="dev")
    a.add_argument("--out", required=True)
    a.add_argument("--dataset", default=str(DEFAULT_DS))
    a.add_argument("--imgsz", type=int, default=640)
    a.add_argument("--batch", type=int, default=8)
    a.add_argument("--device", default="mps")
    a.add_argument("--op-conf", type=float, default=0.25)
    a.add_argument("--op-nms", type=float, default=0.5)
    a.add_argument("--latency-images", type=int, default=60)
    a.add_argument("--locked-test-purpose", default=None)
    a.add_argument("--frozen-sha256", default=None)
    a.add_argument("--skip-ultralytics", action="store_true")
    args = a.parse_args()

    weights = Path(args.weights) if Path(args.weights).is_absolute() else ROOT / args.weights
    ds = Path(args.dataset) if Path(args.dataset).is_absolute() else ROOT / args.dataset
    out = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    wsha = sha256(weights)
    if args.split == "test":
        if not args.locked_test_purpose or args.frozen_sha256 != wsha:
            raise SystemExit("LOCKED TEST: --locked-test-purpose and --frozen-sha256 <exact sha256 of the weights> are required")
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        new = not LEDGER.exists()
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "weights", "sha256", "imgsz", "op_conf", "purpose", "out"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), str(weights.relative_to(ROOT)), wsha, args.imgsz,
                        args.op_conf, args.locked_test_purpose, str(out.relative_to(ROOT))])
    started = datetime.now().isoformat(timespec="seconds")
    rels = (SPLITS / f"{args.split}.txt").read_text().split()

    uv = None
    if not args.skip_ultralytics:
        print("1/4 Ultralytics val ...", flush=True)
        uv = ultralytics_val(weights, split_yaml(ds, args.split, out), out, args.imgsz, args.batch, args.device)
        print("   ", uv["overall"], flush=True)

    print("2/4 predictions at conf 0.001 ...", flush=True)
    pred = Predictor(weights=weights, device=args.device)
    samples, preds, meta = [], [], []
    for rel in rels:
        gt, img = load_gt(ds, rel)
        p = pred(img, imgsz=args.imgsz, conf=0.001, iou=args.op_nms)
        h, w = img.shape[:2]
        samples.append(Sample(Path(rel).name, np.zeros((1, 1, 3), np.uint8), gt))
        preds.append(p)
        meta.append({"w": w, "h": h})
    np.savez_compressed(out / "predictions.npz", **{s.name: p for s, p in zip(samples, preds)})

    print("3/4 operating point, strata ...", flush=True)
    op = evaluate(samples, preds, op_conf=args.op_conf)
    op["settings"] = {"conf": args.op_conf, "nms_iou": args.op_nms, "imgsz": args.imgsz, "matching": "greedy by confidence, same class, IoU >= 0.5"}
    (out / "operating_point.json").write_text(json.dumps(op, indent=2))
    cm = confusion_at_operating_point(samples, preds, conf=args.op_conf)
    labels = [NAMES[i] for i in range(len(NAMES))] + ["background"]
    with open(out / "confusion_matrix_op.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["predicted \\ true"] + labels)
        for i, row in enumerate(cm):
            w.writerow([labels[i]] + [int(v) for v in row])
    tally = defaultdict(lambda: [0, 0])
    for s, p, m in zip(samples, preds, meta):
        hit = matched_gt(p, s.gt, args.op_conf)
        scale = args.imgsz / max(m["w"], m["h"])
        for g, ok in zip(s.gt, hit):
            c = NAMES[int(g[0])]
            short = min(g[3] - g[1], g[4] - g[2]) * scale
            area = (g[3] - g[1]) * (g[4] - g[2]) / (m["w"] * m["h"])
            sb = next(n for n, lo, hi in SHORT_BANDS if lo <= short < hi)
            ab = next(n for n, lo, hi in AREA_BANDS if lo <= area < hi)
            for key in ((c, "short_side_at_imgsz", sb), (c, "area", ab), ("ALL", "short_side_at_imgsz", sb), ("ALL", "area", ab)):
                tally[key][0] += int(ok)
                tally[key][1] += 1
    with open(out / "size_strata.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "dimension", "band", "matched", "gt", "recall"])
        for (c, d, b), (mt, n) in sorted(tally.items()):
            w.writerow([c, d, b, mt, n, round(mt / n, 4) if n else ""])
    fam = {}
    for fname in ("source", "ultralytics-ppe"):
        idx = [i for i, s in enumerate(samples) if family(s.name) == fname]
        if idx:
            e = evaluate([samples[i] for i in idx], [preds[i] for i in idx], op_conf=args.op_conf)
            fam[fname] = {"images": len(idx), "gt_objects": e["gt_objects"], "mAP50": round(e["mAP50"], 4), "mAP50-95": round(e["mAP50-95"], 4),
                          "precision_op": round(e["precision"], 4), "recall_op": round(e["recall"], 4),
                          "missing_ppe_recall_op": {c: e["per_class_op"][c]["recall"] for c in MISSING},
                          "fp_types": e["fp_types"]}
    (out / "family_strata.json").write_text(json.dumps(fam, indent=2))

    print("4/4 latency ...", flush=True)
    import torch
    times = []
    for rel in rels[: args.latency_images]:
        img = cv2.imread(str(ds / rel))
        t = time.perf_counter()
        pred(img, imgsz=args.imgsz, conf=args.op_conf, iou=args.op_nms)
        times.append((time.perf_counter() - t) * 1000)
    lat = {"images": len(times), "note": "wall clock of predict + copy to numpy (forces MPS completion); full-resolution dataset images",
           "mean_ms": round(float(np.mean(times)), 2), "median_ms": round(float(np.median(times)), 2),
           "p95_ms": round(float(np.percentile(times, 95)), 2), "max_ms": round(float(np.max(times)), 2),
           "mps_driver_allocated_mb": round(torch.mps.driver_allocated_memory() / 1e6, 1) if torch.backends.mps.is_available() else None}
    (out / "latency.json").write_text(json.dumps(lat, indent=2))

    import ultralytics
    cfg = {"started": started, "finished": datetime.now().isoformat(timespec="seconds"), "weights": str(weights.relative_to(ROOT)),
           "weights_sha256": wsha, "split": args.split, "images": len(rels), "split_list_sha256": sha256(SPLITS / f"{args.split}.txt"),
           "dataset": str(ds.relative_to(ROOT)), "imgsz": args.imgsz, "op_conf": args.op_conf, "op_nms_iou": args.op_nms,
           "device": args.device, "ultralytics": ultralytics.__version__, "torch": torch.__version__, "python": platform.python_version(),
           "protocol": "evaluation protocol v1 (REPORT-020)"}
    (out / "run_config.json").write_text(json.dumps(cfg, indent=2))
    summary = {"split": args.split, "images": len(rels), "gt_objects": op["gt_objects"],
               "ultralytics": uv["overall"] if uv else None,
               "audit_evaluator": {"mAP50": round(op["mAP50"], 4), "mAP50-95": round(op["mAP50-95"], 4)},
               "operating_point": {"conf": args.op_conf, "precision": round(op["precision"], 4), "recall": round(op["recall"], 4),
                                   "f1": round(op["f1"], 4), "tp": op["tp"], "fp": op["fp"], "fn": op["fn"],
                                   "background_fp": op["fp_types"].get("background", 0)},
               "missing_ppe_recall_op": {c: op["per_class_op"][c]["recall"] for c in MISSING},
               "person_recall_op": op["per_class_op"]["Person"]["recall"],
               "latency_ms_mean": lat["mean_ms"], "weights_sha256": wsha}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
