"""Controlled YOLO26n vs YOLO26m comparison (spec §9). Same images, labels, classes, imgsz, thresholds and evaluator.

    .venv/bin/python scripts/engineering/compare_models.py

Inputs : experiments/engineering_phase/baseline/yolo26n/ and experiments/yolo26m/validation/ (both from evaluate_model.py)
Outputs: experiments/yolo26m/benchmarks/comparison.json, per_class_comparison.csv, bootstrap.json, latency_comparison.json,
         experiments/yolo26m/predictions/visual_comparison/*.jpg + visual_examples.csv, webcam_style.json
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.evaluation.live_audit import (  # noqa: E402
    NAMES,
    OP_CONF,
    Predictor,
    Sample,
    _load_yolo_boxes,
    box_iou,
    evaluate,
    load_val_samples,
    match_greedy,
    resize_long,
    webcam_framing,
)

N_DIR = ROOT / "experiments/engineering_phase/baseline/yolo26n"
M_DIR = ROOT / "experiments/yolo26m/validation"
OUT = ROOT / "experiments/yolo26m/benchmarks"
VIS = ROOT / "experiments/yolo26m/predictions/visual_comparison"
WEIGHTS = {"yolo26n": ROOT / "models/trained/best.pt",
           "yolo26m": ROOT / "experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt"}


def load_preds(d: Path, samples) -> list[np.ndarray]:
    z = np.load(d / "predictions_conf0.001.npz")
    return [z[s.name] for s in samples]


def per_image_tp(samples, preds):
    """Per-image (tp matrix, conf, cls) for bootstrap, using the same matching as evaluate()."""
    out = []
    for s, p in zip(samples, preds):
        p = p[np.argsort(-p[:, 4], kind="stable")] if len(p) else p
        out.append((match_greedy(p, s.gt), p[:, 4] if len(p) else np.zeros(0), p[:, 5] if len(p) else np.zeros(0), s.gt[:, 0]))
    return out


def map_from(items):
    from ultralytics.utils.metrics import ap_per_class

    tp = np.concatenate([i[0] for i in items]); conf = np.concatenate([i[1] for i in items])
    cls = np.concatenate([i[2] for i in items]); tgt = np.concatenate([i[3] for i in items])
    ap = ap_per_class(tp, conf, cls, tgt)[5]
    # recall at the operating threshold
    m = conf >= OP_CONF
    rec = tp[m, 0].sum() / max(1, len(tgt))
    return float(ap[:, 0].mean()), float(ap.mean()), float(rec)


def bootstrap(samples, pn, pm, B: int = 1000, seed: int = 0) -> dict:
    a, b = per_image_tp(samples, pn), per_image_tp(samples, pm)
    rng = np.random.default_rng(seed)
    n = len(samples)
    diffs = []
    for _ in range(B):
        idx = rng.integers(0, n, n)
        ma, mb = map_from([a[i] for i in idx]), map_from([b[i] for i in idx])
        diffs.append([mb[k] - ma[k] for k in range(3)])
    diffs = np.array(diffs)
    full_a, full_b = map_from(a), map_from(b)
    res = {"method": f"paired bootstrap over val images (B={B}, seed {seed}); metric recomputed on the same resample for both models; "
                     "evaluator = audit evaluator at NMS IoU 0.5 (app setting)",
           "point": {"yolo26n": dict(zip(("mAP50", "mAP50-95", "recall@0.25"), full_a)),
                     "yolo26m": dict(zip(("mAP50", "mAP50-95", "recall@0.25"), full_b))}}
    for k, name in enumerate(("mAP50", "mAP50-95", "recall@0.25")):
        lo, hi = np.percentile(diffs[:, k], [2.5, 97.5])
        res[f"diff_{name}"] = {"m_minus_n": round(full_b[k] - full_a[k], 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
                               "share_of_resamples_m_better": round(float((diffs[:, k] > 0).mean()), 3)}
    return res


def latency(samples) -> dict:
    """Synchronised wall clock (detect() converts boxes to numpy) on identical inputs, MPS, imgsz 640."""
    import torch

    from src.detection.detector import PPEDetector

    cap = cv2.VideoCapture(str(ROOT / "data/test_media/test_site_clip.mp4"))
    frames = []
    while len(frames) < 60:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.resize(f, (1280, 720)))
    cap.release()
    full = [s.image for s in samples[:60]]
    out = {}
    for name, w in WEIGHTS.items():
        loads = []
        for _ in range(5):
            t = time.perf_counter(); PPEDetector(weights=w).load(); loads.append(time.perf_counter() - t)
        det = PPEDetector(weights=w).load()
        t = time.perf_counter(); det.detect(frames[0]); first = time.perf_counter() - t
        for _ in range(5):
            det.detect(frames[0])
        res = {}
        for label, imgs in (("frames_1280x720", frames), ("val_full_resolution", full)):
            ms = []
            for im in imgs:
                t = time.perf_counter(); det.detect(im); ms.append((time.perf_counter() - t) * 1000)
            v = np.array(ms)
            res[label] = {"n": len(v), "mean": round(float(v.mean()), 2), "median": round(float(np.median(v)), 2),
                          "p95": round(float(np.percentile(v, 95)), 2), "max": round(float(v.max()), 2),
                          "throughput_fps_sequential": round(1000 / float(v.mean()), 1)}
        model = det.model.model
        out[name] = {"weights": str(w.relative_to(ROOT)), "sha256": hashlib.sha256(w.read_bytes()).hexdigest(),
                     "size_bytes": w.stat().st_size, "params_unfused": sum(p.numel() for p in model.parameters()),
                     "load_s_median_of_5": round(float(np.median(loads)), 3), "first_detect_s": round(first, 3),
                     "mps_driver_allocated_mb_after": round(torch.mps.driver_allocated_memory() / 1e6, 1), **res}
        del det
        torch.mps.empty_cache()
    return out


def visual_examples(samples, pn, pm) -> list[dict]:
    """Rule-based selection (not cherry-picked) of images for side-by-side comparison."""
    import csv as _csv

    vp = {r["filename"]: r["viewpoint"] for r in _csv.DictReader(open(ROOT / "data/viewpoint_metadata.csv"))}
    stats = []
    for i, (s, a, b) in enumerate(zip(samples, pn, pm)):
        h, w = s.image.shape[:2]
        rec = []
        for p in (a, b):
            po = p[p[:, 4] >= OP_CONF] if len(p) else p
            po = po[np.argsort(-po[:, 4], kind="stable")] if len(po) else po
            ok = match_greedy(po, s.gt)[:, 0] if len(po) else np.zeros(0, bool)
            rec.append((po, ok))
        areas = (s.gt[:, 3] - s.gt[:, 1]) * (s.gt[:, 4] - s.gt[:, 2]) / (w * h) if len(s.gt) else np.zeros(0)
        n_tp = int(rec[0][1].sum()); n_fp = int((~rec[0][1]).sum())
        stats.append({"i": i, "recall_n": n_tp / max(1, len(s.gt)), "fp_n": n_fp, "small": int((areas < 0.01).sum()),
                      "persons": int((s.gt[:, 0] == 5).sum()), "brightness": float(cv2.cvtColor(s.image, cv2.COLOR_BGR2GRAY).mean()),
                      "viewpoint": vp.get(s.name, "?")})
    pick = {}
    order = lambda key, rev=True: sorted(stats, key=lambda r: r[key], reverse=rev)
    rules = [("easy", order("recall_n")[:2]), ("difficult", order("recall_n", False)[:2]), ("small_objects", order("small")[:2]),
             ("crowded_occlusion_proxy", order("persons")[:2]), ("overhead_view", [r for r in stats if r["viewpoint"] == "overhead"][:2]),
             ("side_view", [r for r in stats if r["viewpoint"] == "side"][:1]), ("low_light", order("brightness", False)[:2]),
             ("false_positive_heavy", order("fp_n")[:2])]
    # conflicting boxes: images where YOLO26n produced a contradicting pair
    from src.evaluation.live_audit import contradiction_pairs

    conf_imgs = [r for r in stats if contradiction_pairs(pn[r["i"]][pn[r["i"]][:, 4] >= OP_CONF]) > 0][:2]
    rules.append(("conflicting_boxes", conf_imgs))
    rules.append(("false_negative_heavy", sorted(stats, key=lambda r: -(len(samples[r["i"]].gt) * (1 - r["recall_n"])))[:2]))
    VIS.mkdir(parents=True, exist_ok=True)
    rows = []
    for cat, sel in rules:
        for r in sel:
            if r["i"] in pick:
                continue
            pick[r["i"]] = cat
            s = samples[r["i"]]
            panels = []
            for model, p in (("yolo26n", pn[r["i"]]), ("yolo26m", pm[r["i"]])):
                po = p[p[:, 4] >= OP_CONF] if len(p) else p
                po = po[np.argsort(-po[:, 4], kind="stable")] if len(po) else po
                ok = match_greedy(po, s.gt)[:, 0] if len(po) else np.zeros(0, bool)
                iou = box_iou(po[:, :4], s.gt[:, 1:5]) if len(po) and len(s.gt) else np.zeros((len(po), 0))
                img = s.image.copy(); th = max(1, img.shape[1] // 700)
                for g in s.gt:
                    cv2.rectangle(img, (int(g[1]), int(g[2])), (int(g[3]), int(g[4])), (255, 255, 255), th)
                for j, (row, good) in enumerate(zip(po, ok)):
                    k = int(np.argmax(iou[j])) if iou.shape[1] else -1
                    rows.append({"file": s.name, "category": cat, "model": model, "predicted_class": NAMES[int(row[5])],
                                 "confidence": round(float(row[4]), 3), "best_gt_class": NAMES[int(s.gt[k, 0])] if k >= 0 else "",
                                 "best_iou": round(float(iou[j, k]), 3) if k >= 0 else 0.0, "correct": bool(good)})
                    color = (60, 170, 60) if good else (40, 40, 220)
                    cv2.rectangle(img, (int(row[0]), int(row[1])), (int(row[2]), int(row[3])), color, th + 1)
                    cv2.putText(img, f"{NAMES[int(row[5])]} {row[4]:.2f}", (int(row[0]), max(14, int(row[1]) - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45 * th + 0.2, color, th, cv2.LINE_AA)
                fn = int(len(s.gt) - ok.sum())
                cv2.putText(img, f"{model}: TP {int(ok.sum())} FP {int((~ok).sum())} FN {fn}", (10, 40 * th), cv2.FONT_HERSHEY_SIMPLEX,
                            1.0 * th, (0, 255, 255), 2 * th)
                panels.append(img)
            cv2.imwrite(str(VIS / f"{cat}_{Path(s.name).stem}.jpg"), np.concatenate(panels, 1), [cv2.IMWRITE_JPEG_QUALITY, 80])
    with open(VIS / "visual_examples.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["file", "category", "model", "predicted_class", "confidence", "best_gt_class", "best_iou", "correct"])
        wr.writeheader(); wr.writerows(rows)
    return [{"file": samples[i].name, "category": c} for i, c in pick.items()]


def webcam_style() -> dict:
    """Both models on (a) webcam-style head-and-torso crops of val images, (b) the 10 manually labelled webcam frames."""
    out = {}
    samples = load_val_samples()
    framed = [w for w in (webcam_framing(s) for s in samples) if w is not None]
    framed = [resize_long(w, 1280) for w in framed]
    wdir = ROOT / "experiments/live_audit/webcam"
    labelled = sorted((wdir / "labels").glob("frame_*.txt")) if (wdir / "labels").exists() else []
    labelled = [p for p in labelled if not p.name.endswith(".ignore.txt")]
    cam = []
    for p in labelled:
        img = cv2.imread(str(wdir / "frames" / f"{p.stem}.jpg"))
        h, w = img.shape[:2]
        cam.append(Sample(p.stem, img, _load_yolo_boxes(p, w, h), _load_yolo_boxes(wdir / "labels" / f"{p.stem}.ignore.txt", w, h)))
    for name, wts in WEIGHTS.items():
        pr = Predictor(weights=wts)
        r1 = evaluate(framed, [pr(s.image, imgsz=640, conf=0.001) for s in framed])
        out[f"{name}_val_webcam_style_crops"] = {k: r1[k] for k in ("images", "gt_objects", "tp", "fp", "fn", "precision", "recall", "mAP50", "mAP50-95", "fp_types")}
        if cam:
            for imgsz in (640, 320):
                r2 = evaluate(cam, [pr(s.image, imgsz=imgsz, conf=0.001) for s in cam])
                out[f"{name}_real_webcam_10frames_imgsz{imgsz}"] = {k: r2[k] for k in ("images", "gt_objects", "tp", "fp", "fn", "precision", "recall", "fp_types")}
    out["note"] = ("real webcam = 10 frames of ONE indoor scene with one person (REPORT-009 §5.6); results describe that scene only. "
                   "Frames are private and are not reproduced in reports.")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    samples = load_val_samples()
    pn, pm = load_preds(N_DIR, samples), load_preds(M_DIR, samples)
    mn, mm = json.loads((N_DIR / "metrics_ultralytics.json").read_text()), json.loads((M_DIR / "metrics_ultralytics.json").read_text())
    on, om = json.loads((N_DIR / "operating_point.json").read_text()), json.loads((M_DIR / "operating_point.json").read_text())
    comp = {"overall_ultralytics_val": {k: {"yolo26n": mn["overall"][k], "yolo26m": mm["overall"][k],
                                            "abs_diff": round(mm["overall"][k] - mn["overall"][k], 4),
                                            "pct_change": round(100 * (mm["overall"][k] - mn["overall"][k]) / mn["overall"][k], 1)}
                                        for k in ("precision", "recall", "mAP50", "mAP50-95")},
            "operating_point_conf0.25_iou0.5": {k: {"yolo26n": round(on[k], 4) if isinstance(on[k], float) else on[k],
                                                    "yolo26m": round(om[k], 4) if isinstance(om[k], float) else om[k]}
                                                for k in ("precision", "recall", "f1", "tp", "fp", "fn", "fp_per_image", "contradiction_pairs", "fp_types")}}
    with open(OUT / "per_class_comparison.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["class", "val_instances", "n_P", "m_P", "n_R", "m_R", "n_AP50", "m_AP50", "d_AP50", "n_AP50-95", "m_AP50-95",
                     "d_AP50-95", "n_FP@0.25", "m_FP@0.25", "n_FN@0.25", "m_FN@0.25", "verdict"])
        for c in mn["per_class"]:
            a, b = mn["per_class"][c], mm["per_class"][c]
            oa, ob = on["per_class_op"][c], om["per_class_op"][c]
            d50, d = b["AP50"] - a["AP50"], b["AP50-95"] - a["AP50-95"]
            verdict = ("too few instances for a confident conclusion" if a["instances"] < 100 else
                       "improved" if d >= 0.02 else "regressed" if d <= -0.02 else "unchanged (|diff| < 0.02)")
            wr.writerow([c, a["instances"], a["precision"], b["precision"], a["recall"], b["recall"], a["AP50"], b["AP50"], round(d50, 4),
                         a["AP50-95"], b["AP50-95"], round(d, 4), oa["fp"], ob["fp"], oa["fn"], ob["fn"], verdict])
    print("bootstrap ...", flush=True)
    comp["bootstrap"] = bootstrap(samples, pn, pm)
    print("latency ...", flush=True)
    comp["latency_memory"] = latency(samples)
    print("visual examples ...", flush=True)
    comp["visual_examples"] = visual_examples(samples, pn, pm)
    print("webcam-style ...", flush=True)
    comp["webcam_style"] = webcam_style()
    sn = {r["class"] + "|" + r["value"]: r for r in csv.DictReader(open(N_DIR / "stratified_recall.csv")) if r["dimension"] == "size"}
    sm = {r["class"] + "|" + r["value"]: r for r in csv.DictReader(open(M_DIR / "stratified_recall.csv")) if r["dimension"] == "size"}
    comp["small_object_recall"] = {k: {"gt": int(sn[k]["gt_objects"]), "yolo26n": float(sn[k]["recall"]), "yolo26m": float(sm[k]["recall"])}
                                   for k in sn if k.endswith("small(<0.01)") and k in sm}
    (OUT / "comparison.json").write_text(json.dumps(comp, indent=2, default=str))
    print(json.dumps({k: comp[k] for k in ("overall_ultralytics_val", "bootstrap")}, indent=1, default=str))


if __name__ == "__main__":
    main()
