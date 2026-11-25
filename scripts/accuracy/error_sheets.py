"""Phase 5 error analysis on DEV data only (spec §7): error manifest and contact sheets per safety-critical class.

    .venv/bin/python scripts/accuracy/error_sheets.py --run dev_<name> --out experiments/accuracy_improvement/error_analysis/<name>

For each of no_helmet, no_gloves, no_goggle, no_boots, no_vest and Person, at the operating point (conf 0.25):
  * false negatives: ground-truth boxes with no same-class prediction at IoU >= 0.5, with their annotation ID,
    short side at 640, and what the model predicted there instead (best-overlapping prediction of any class)
  * false positives: predictions with no same-class ground truth at IoU >= 0.5, typed as duplicate / wrong_class /
    localization / background (live_audit.classify_false_positive)
Writes error_manifest.csv and sheets <class>_FN.jpg / <class>_FP.jpg (up to 12 random cases each, seed 0).
The locked test is never read.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "accuracy"))
from evaluate import DEFAULT_DS, SPLITS  # noqa: E402
from src.evaluation.live_audit import NAMES, box_iou, classify_false_positive, match_greedy  # noqa: E402
from src.utils.dataset_tools import parse_label_file  # noqa: E402

FOCUS = ["no_helmet", "no_gloves", "no_goggle", "no_boots", "no_vest", "Person"]
ID = {v: k for k, v in NAMES.items()}


def crop(img, box, colour, label):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    side = max(160.0, 4 * max(x2 - x1, y2 - y1))
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    X1, Y1 = int(max(0, min(w - side, cx - side / 2))), int(max(0, min(h - side, cy - side / 2)))
    X2, Y2 = int(min(w, X1 + side)), int(min(h, Y1 + side))
    c = img[Y1:Y2, X1:X2].copy()
    s = 240 / max(c.shape[:2])
    c = cv2.resize(c, (int(c.shape[1] * s), int(c.shape[0] * s)))
    cv2.rectangle(c, (int((x1 - X1) * s), int((y1 - Y1) * s)), (int((x2 - X1) * s), int((y2 - Y1) * s)), colour, 2)
    c = cv2.copyMakeBorder(c, 0, 240 - c.shape[0], 0, 240 - c.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(c, label[:34], (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3)
    cv2.putText(c, label[:34], (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--conf", type=float, default=0.25)
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(ROOT / "experiments/accuracy_improvement/evaluation" / a.run / "predictions.npz")
    rows = []
    for rel in (SPLITS / "dev.txt").read_text().split():
        name = Path(rel).name
        img = cv2.imread(str(DEFAULT_DS / rel))
        h, w = img.shape[:2]
        lab = parse_label_file(DEFAULT_DS / rel.replace("images/", "labels/", 1).rsplit(".", 1)[0].__add__(".txt"))
        gt = np.array([[r.class_id, (r.x_center - r.width / 2) * w, (r.y_center - r.height / 2) * h,
                        (r.x_center + r.width / 2) * w, (r.y_center + r.height / 2) * h] for r in lab], float).reshape(-1, 5)
        p = z[name] if name in z.files else np.zeros((0, 6))
        p = p[p[:, 4] >= a.conf] if len(p) else p
        p = p[np.argsort(-p[:, 4], kind="stable")] if len(p) else p
        ok = match_greedy(p, gt)[:, 0] if len(p) else np.zeros(0, bool)
        matched = np.zeros(len(gt), bool)
        if len(p) and len(gt):
            iou = box_iou(gt[:, 1:5], p[:, :4]) * (gt[:, 0][:, None] == p[:, 5][None, :])
            for j in range(len(p)):
                av = np.where(matched, 0.0, iou[:, j]); k = int(np.argmax(av))
                if av[k] >= 0.5:
                    matched[k] = True
        scale = 640 / max(w, h)
        stem = Path(rel).stem
        for gi, (g, m_) in enumerate(zip(gt, matched)):
            c = NAMES[int(g[0])]
            if c in FOCUS and not m_:
                inst = ""
                if len(p):
                    ious = box_iou(g[None, 1:5], p[:, :4])[0]
                    j = int(np.argmax(ious))
                    inst = f"{NAMES[int(p[j, 5])]} {p[j, 4]:.2f} IoU {ious[j]:.2f}" if ious[j] >= 0.3 else "nothing (IoU < 0.3)"
                rows.append({"type": "FN", "class": c, "image": rel, "annotation_id": f"dev/{stem}#L{gi + 1}",
                             "x1": round(g[1], 1), "y1": round(g[2], 1), "x2": round(g[3], 1), "y2": round(g[4], 1),
                             "short_side_640": round(min(g[3] - g[1], g[4] - g[2]) * scale, 1), "conf": "", "detail": f"predicted instead: {inst or 'nothing'}"})
        for row, o in zip(p, ok):
            c = NAMES[int(row[5])]
            if c in FOCUS and not o:
                kind, gcls = classify_false_positive(row, gt)
                rows.append({"type": "FP", "class": c, "image": rel, "annotation_id": "", "x1": round(row[0], 1), "y1": round(row[1], 1),
                             "x2": round(row[2], 1), "y2": round(row[3], 1), "short_side_640": round(min(row[2] - row[0], row[3] - row[1]) * scale, 1),
                             "conf": round(float(row[4]), 3), "detail": kind + (f" (true: {NAMES[gcls]})" if gcls is not None else "")})
    with open(out / "error_manifest.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    rng = np.random.default_rng(0)
    summary = Counter()
    for c in FOCUS:
        for t, col in (("FN", (0, 165, 255)), ("FP", (0, 0, 255))):
            sel = [r for r in rows if r["class"] == c and r["type"] == t]
            summary[f"{c} {t}"] = len(sel)
            if not sel:
                continue
            pick = [sel[i] for i in rng.choice(len(sel), min(12, len(sel)), replace=False)]
            tiles = []
            for r in pick:
                img = cv2.imread(str(DEFAULT_DS / r["image"]))
                lab = f"{t} {r['short_side_640']}px {r['conf']} {r['detail'][:22]}"
                tiles.append(crop(img, (r["x1"], r["y1"], r["x2"], r["y2"]), col, lab))
            while len(tiles) % 6:
                tiles.append(np.full((240, 240, 3), 255, np.uint8))
            sheet = np.vstack([np.hstack(tiles[k:k + 6]) for k in range(0, len(tiles), 6)])
            cv2.imwrite(str(out / f"{c}_{t}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(dict(summary))


if __name__ == "__main__":
    main()
