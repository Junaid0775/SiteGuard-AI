"""Phase 3 small-object investigation at INFERENCE time (specification §5.3), dev split only.

    .venv/bin/python scripts/accuracy/phase3_inference_scale.py --weights <pt> --out <dir> [--sizes 640 768 896 1024 1280]

Uses an existing checkpoint (trained at 640) and changes only how it is applied:
  full_<s>    whole image at inference size s
  tiled_2x2   whole image at 640 + a 2x2 grid of overlapping tiles (20 % overlap), each at 640.
              Tile boxes touching an inner tile edge are dropped (the neighbouring tile or the whole image covers
              that object). Then class-aware NMS (IoU 0.5) and a same-class suppression on intersection-over-
              smaller >= 0.8 remove duplicates.
For every configuration: audit-evaluator mAP50 / mAP50-95 (conf 0.001, NMS 0.5), operating point (conf 0.25),
missing-PPE recall, recall by ground-truth short side measured at the 640 reference scale, per-family results,
remaining duplicate pairs at the operating point (same class, IoU >= 0.5 or IoS >= 0.8), and synchronised latency.
The locked test is never touched. Threshold and training settings are not changed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torchvision

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "accuracy"))
from evaluate import DEFAULT_DS, MISSING, SPLITS, family, load_gt, matched_gt  # noqa: E402
from src.evaluation.live_audit import NAMES, Predictor, Sample, box_iou, evaluate  # noqa: E402

BANDS = [("<8px", 0, 8), ("8-16px", 8, 16), ("16-32px", 16, 32), (">=32px", 32, 1e9)]


def ios(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ix1 = np.maximum(a[:, None, 0], b[None, :, 0]); iy1 = np.maximum(a[:, None, 1], b[None, :, 1])
    ix2 = np.minimum(a[:, None, 2], b[None, :, 2]); iy2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]); ab = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(np.minimum(aa[:, None], ab[None, :]), 1e-9)


def merge(p: np.ndarray, iou_thr: float = 0.5, ios_thr: float = 0.8) -> np.ndarray:
    if len(p) == 0:
        return p
    t = torch.from_numpy(p).float()
    keep = torchvision.ops.batched_nms(t[:, :4], t[:, 4], t[:, 5].long(), iou_thr).numpy()
    p = p[keep]
    p = p[np.argsort(-p[:, 4], kind="stable")]
    drop = np.zeros(len(p), bool)
    m = ios(p[:, :4], p[:, :4])
    for i in range(len(p)):
        if drop[i]:
            continue
        dup = (m[i] >= ios_thr) & (p[:, 5] == p[i, 5]) & (np.arange(len(p)) > i)
        drop |= dup
    return p[~drop]


def tiled(pred: Predictor, img: np.ndarray, conf: float, nms: float, grid: int = 2, overlap: float = 0.2) -> np.ndarray:
    h, w = img.shape[:2]
    out = [pred(img, imgsz=640, conf=conf, iou=nms)]
    tw, th = int(w / grid * (1 + overlap)), int(h / grid * (1 + overlap))
    xs = np.linspace(0, w - tw, grid).astype(int); ys = np.linspace(0, h - th, grid).astype(int)
    for y0 in ys:
        for x0 in xs:
            p = pred(img[y0:y0 + th, x0:x0 + tw], imgsz=640, conf=conf, iou=nms)
            if len(p) == 0:
                continue
            p = p.copy(); p[:, [0, 2]] += x0; p[:, [1, 3]] += y0
            edge = 2.0
            inner = ((p[:, 0] <= x0 + edge) & (x0 > 0)) | ((p[:, 2] >= x0 + tw - edge) & (x0 + tw < w)) | \
                    ((p[:, 1] <= y0 + edge) & (y0 > 0)) | ((p[:, 3] >= y0 + th - edge) & (y0 + th < h))
            out.append(p[~inner])
    return merge(np.concatenate(out, 0), iou_thr=nms)


def duplicates(p: np.ndarray, conf: float) -> int:
    q = p[p[:, 4] >= conf] if len(p) else p
    if len(q) < 2:
        return 0
    iou = box_iou(q[:, :4], q[:, :4]); s = ios(q[:, :4], q[:, :4])
    same = q[:, 5][:, None] == q[:, 5][None, :]
    m = ((iou >= 0.5) | (s >= 0.8)) & same
    return int(np.triu(m, 1).sum())


def run(cfg: str, pred: Predictor, rels: list[str], ds: Path, op_conf: float = 0.25) -> dict:
    samples, preds, times, dup, tally = [], [], [], 0, {}
    for rel in rels:
        gt, img = load_gt(ds, rel)
        t = time.perf_counter()
        if cfg.startswith("full_"):
            p = pred(img, imgsz=int(cfg.split("_")[1]), conf=0.001, iou=0.5)
        else:
            p = tiled(pred, img, conf=0.001, nms=0.5)
        times.append((time.perf_counter() - t) * 1000)
        samples.append(Sample(Path(rel).name, np.zeros((1, 1, 3), np.uint8), gt))
        preds.append(p)
        dup += duplicates(p, op_conf)
        hit = matched_gt(p, gt, op_conf)
        scale = 640 / max(img.shape[:2])
        for g, ok in zip(gt, hit):
            short = min(g[3] - g[1], g[4] - g[2]) * scale
            band = next(n for n, lo, hi in BANDS if lo <= short < hi)
            for key in (band, f"{NAMES[int(g[0])]}|{band}" if NAMES[int(g[0])] in MISSING else None):
                if key:
                    tally.setdefault(key, [0, 0]); tally[key][0] += int(ok); tally[key][1] += 1
    e = evaluate(samples, preds, op_conf=op_conf)
    fam = {}
    for f in ("source", "ultralytics-ppe"):
        idx = [i for i, s in enumerate(samples) if family(s.name) == f]
        ef = evaluate([samples[i] for i in idx], [preds[i] for i in idx], op_conf=op_conf)
        fam[f] = {"mAP50": round(ef["mAP50"], 4), "precision_op": round(ef["precision"], 4), "recall_op": round(ef["recall"], 4),
                  "missing_recall_op": {c: ef["per_class_op"][c]["recall"] for c in MISSING}}
    return {"config": cfg, "mAP50": round(e["mAP50"], 4), "mAP50-95": round(e["mAP50-95"], 4),
            "precision_op": round(e["precision"], 4), "recall_op": round(e["recall"], 4), "f1_op": round(e["f1"], 4),
            "fp": e["fp"], "fp_types": e["fp_types"], "missing_recall_op": {c: e["per_class_op"][c]["recall"] for c in MISSING},
            "person_recall_op": e["per_class_op"]["Person"]["recall"], "duplicate_pairs_op": dup,
            "recall_by_short_side_at_640": {k: round(v[0] / v[1], 4) for k, v in sorted(tally.items()) if "|" not in k},
            "missing_recall_by_short_side": {k: [round(v[0] / v[1], 3), v[1]] for k, v in sorted(tally.items()) if "|" in k},
            "family": fam, "latency_ms_mean": round(float(np.mean(times[5:])), 1), "latency_ms_p95": round(float(np.percentile(times[5:], 95)), 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sizes", type=int, nargs="+", default=[640, 768, 896, 1024, 1280])
    ap.add_argument("--no-tiling", action="store_true")
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    rels = (SPLITS / "dev.txt").read_text().split()
    pred = Predictor(weights=ROOT / a.weights, device="mps")
    results = []
    for cfg in [f"full_{s}" for s in a.sizes] + ([] if a.no_tiling else ["tiled_2x2"]):
        r = run(cfg, pred, rels, DEFAULT_DS)
        results.append(r)
        print(f"{cfg:10s} mAP50 {r['mAP50']:.4f} mAP50-95 {r['mAP50-95']:.4f} P {r['precision_op']:.3f} R {r['recall_op']:.3f} "
              f"src R {r['family']['source']['recall_op']:.3f} gen R {r['family']['ultralytics-ppe']['recall_op']:.3f} "
              f"<8px R {r['recall_by_short_side_at_640'].get('<8px', 0):.3f} dup {r['duplicate_pairs_op']} lat {r['latency_ms_mean']} ms", flush=True)
    (out / "inference_scale_results.json").write_text(json.dumps({"weights": a.weights, "split": "dev", "results": results}, indent=2))


if __name__ == "__main__":
    main()
