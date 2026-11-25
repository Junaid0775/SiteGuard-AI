"""Phase 5: compare evaluated models on the same split (protocol v1, REPORT-020) and sweep thresholds on dev.

    .venv/bin/python scripts/accuracy/compare_candidates.py --split dev --reference dev_E1_m640_base \
        --runs dev_yolo26n_active_baseline dev_yolo26m_e30_b4_baseline dev_E1_m640_base dev_E3_m896 ... \
        --out experiments/accuracy_improvement/error_analysis/comparison_dev [--sweep dev_E3_m896]

Reads evaluation/<run>/{summary.json, predictions.npz, metrics_ultralytics.json, family_strata.json, size_strata.csv}.
Ground truth is re-read from the derived dataset (same loader as evaluate.py). Writes:
  comparison.csv / comparison.json   headline metrics per run
  bootstrap_vs_reference.json        paired image-level bootstrap (B=1000, seed 0) of each run minus the reference:
                                     mAP50 (audit evaluator), recall at 0.25, mean missing-PPE recall at 0.25, and at the
                                     alert threshold (compliance.violation_confidence) for the missing-PPE classes
  bootstrap_absolute.json            from the same resamples: 95 % interval of each run's own mAP50 (audit evaluator),
                                     precision / recall at 0.25 and per missing-PPE class recall at 0.25
  threshold_sweep.csv                (with --sweep) per class precision / recall / F1 for confidence 0.05 ... 0.80
Predictions of different image sizes are compared only as whole systems (model + its inference size).
--split test reads locked-test labels: it requires --locked-test-purpose and appends one row per run to
experiments/accuracy_improvement/qualification/locked_test_access_log.csv (same ledger as evaluate.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "accuracy"))
from evaluate import DEFAULT_DS, MISSING, SPLITS, load_gt  # noqa: E402
from src.evaluation.live_audit import NAMES, Sample, evaluate, match_greedy  # noqa: E402
from src.utils.paths import load_settings  # noqa: E402

EVAL = ROOT / "experiments" / "accuracy_improvement" / "evaluation"
ALERT = float(load_settings()["compliance"]["violation_confidence"])


def gt_samples(split: str) -> list[Sample]:
    out = []
    for rel in (SPLITS / f"{split}.txt").read_text().split():
        gt, _ = load_gt(DEFAULT_DS, rel)
        out.append(Sample(Path(rel).name, np.zeros((1, 1, 3), np.uint8), gt))
    return out


def per_image_counts(samples, preds, conf: float):
    """Per image and class: TP, FP, GT at confidence >= conf (greedy, same class, IoU 0.5)."""
    tp = np.zeros((len(samples), 12)); fp = np.zeros((len(samples), 12)); gt = np.zeros((len(samples), 12))
    for i, (s, p) in enumerate(zip(samples, preds)):
        p = p[np.argsort(-p[:, 4], kind="stable")] if len(p) else p
        ok = match_greedy(p, s.gt)[:, 0] if len(p) else np.zeros(0, bool)
        keep = p[:, 4] >= conf if len(p) else np.zeros(0, bool)
        for c in range(12):
            pc = (p[:, 5] == c) & keep if len(p) else np.zeros(0, bool)
            tp[i, c] = (ok & pc).sum(); fp[i, c] = (~ok & pc).sum(); gt[i, c] = (s.gt[:, 0] == c).sum()
    return tp, fp, gt


def recall_stats(tp, gt, idx):
    t, g = tp[idx].sum(0), gt[idx].sum(0)
    miss = [NAMES.index(c) if isinstance(NAMES, list) else [k for k, v in NAMES.items() if v == c][0] for c in MISSING]
    per = np.where(g > 0, t / np.maximum(g, 1), np.nan)
    return float(t.sum() / max(g.sum(), 1)), float(np.nanmean(per[miss]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--reference", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sweep", default=None)
    ap.add_argument("--B", type=int, default=1000)
    ap.add_argument("--locked-test-purpose", default=None)
    a = ap.parse_args()
    out = ROOT / a.out
    if a.split == "test":
        if not a.locked_test_purpose:
            raise SystemExit("LOCKED TEST: --locked-test-purpose is required for --split test")
        import csv as _csv
        from datetime import datetime as _dt
        from evaluate import LEDGER
        with open(LEDGER, "a", newline="") as f:
            for run in dict.fromkeys([a.reference] + a.runs):
                rc = json.loads((EVAL / run / "run_config.json").read_text())
                _csv.writer(f).writerow([_dt.now().isoformat(timespec="seconds"), f"analysis of evaluation/{run} (predictions.npz)",
                                         rc["weights_sha256"], rc["imgsz"], 0.25, a.locked_test_purpose, str(out.relative_to(ROOT))])
    out.mkdir(parents=True, exist_ok=True)
    samples = gt_samples(a.split)
    names = [s.name for s in samples]

    def preds_of(run):
        z = np.load(EVAL / run / "predictions.npz")
        return [z[n] if n in z.files else np.zeros((0, 6)) for n in names]

    rows, P = [], {}
    for run in dict.fromkeys([a.reference] + a.runs):
        sm = json.loads((EVAL / run / "summary.json").read_text())
        cfg = json.loads((EVAL / run / "run_config.json").read_text())
        fam = json.loads((EVAL / run / "family_strata.json").read_text())
        P[run] = preds_of(run)
        tp_a, fp_a, gt_a = per_image_counts(samples, P[run], ALERT)
        miss_ids = [[k for k, v in NAMES.items() if v == c][0] for c in MISSING]
        alert_p = {c: (tp_a[:, k].sum() / max(tp_a[:, k].sum() + fp_a[:, k].sum(), 1)) for c, k in zip(MISSING, miss_ids)}
        alert_r = {c: (tp_a[:, k].sum() / max(gt_a[:, k].sum(), 1)) for c, k in zip(MISSING, miss_ids)}
        u = sm["ultralytics"] or {}
        rows.append({"run": run, "imgsz": cfg["imgsz"], "weights_sha256": cfg["weights_sha256"][:16],
                     "P_ultra": u.get("precision"), "R_ultra": u.get("recall"), "mAP50": u.get("mAP50"), "mAP50-95": u.get("mAP50-95"),
                     "P@0.25": sm["operating_point"]["precision"], "R@0.25": sm["operating_point"]["recall"],
                     "F1@0.25": sm["operating_point"]["f1"], "background_FP@0.25": sm["operating_point"]["background_fp"],
                     **{f"R@0.25 {c}": sm["missing_ppe_recall_op"][c] for c in MISSING},
                     "mean_missing_R@0.25": round(float(np.mean([sm["missing_ppe_recall_op"][c] for c in MISSING])), 4),
                     **{f"alertP@{ALERT} {c}": round(float(alert_p[c]), 4) for c in MISSING},
                     **{f"alertR@{ALERT} {c}": round(float(alert_r[c]), 4) for c in MISSING},
                     "Person R@0.25": sm["person_recall_op"],
                     "source mAP50": fam["source"]["mAP50"], "source R@0.25": fam["source"]["recall_op"],
                     "generated mAP50": fam["ultralytics-ppe"]["mAP50"], "generated R@0.25": fam["ultralytics-ppe"]["recall_op"],
                     "latency_ms_mean": sm["latency_ms_mean"]})
    with open(out / "comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (out / "comparison.json").write_text(json.dumps(rows, indent=2))

    # paired bootstrap vs reference
    rng = np.random.default_rng(0)
    n = len(samples)
    boot = {}
    ref = a.reference
    cnt = {r: per_image_counts(samples, P[r], 0.25) for r in P}
    miss_ids = [[k for k, v in NAMES.items() if v == c][0] for c in MISSING]
    absolute = {r: {"mAP50_audit": [], "precision@0.25": [], "recall@0.25": [], **{f"recall@0.25 {c}": [] for c in MISSING}} for r in P}

    def record(r, e, idx):
        """Absolute values of run r on this resample (no extra random draws, so the paired results are unchanged)."""
        t, f_, g = cnt[r][0][idx].sum(0), cnt[r][1][idx].sum(0), cnt[r][2][idx].sum(0)
        absolute[r]["mAP50_audit"].append(e["mAP50"])
        absolute[r]["precision@0.25"].append(t.sum() / max(t.sum() + f_.sum(), 1))
        absolute[r]["recall@0.25"].append(t.sum() / max(g.sum(), 1))
        for c, k in zip(MISSING, miss_ids):
            absolute[r][f"recall@0.25 {c}"].append(t[k] / g[k] if g[k] else np.nan)

    for run in P:
        if run == ref:
            continue
        first = not absolute[ref]["mAP50_audit"]
        diffs = {"mAP50_audit": [], "recall@0.25": [], "mean_missing_recall@0.25": []}
        for _ in range(a.B):
            idx = rng.integers(0, n, n)
            ss = [samples[i] for i in idx]
            e_r = evaluate(ss, [P[ref][i] for i in idx]); e_c = evaluate(ss, [P[run][i] for i in idx])
            record(run, e_c, idx)
            if first:
                record(ref, e_r, idx)
            diffs["mAP50_audit"].append(e_c["mAP50"] - e_r["mAP50"])
            rr, mr = recall_stats(cnt[ref][0], cnt[ref][2], idx)
            rc, mc = recall_stats(cnt[run][0], cnt[run][2], idx)
            diffs["recall@0.25"].append(rc - rr); diffs["mean_missing_recall@0.25"].append(mc - mr)
        boot[run] = {k: {"mean": round(float(np.mean(v)), 4), "ci95": [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)],
                         "share_positive": round(float(np.mean(np.array(v) > 0)), 3)} for k, v in diffs.items()}
        print(run, json.dumps(boot[run]), flush=True)
    (out / "bootstrap_vs_reference.json").write_text(json.dumps({"reference": ref, "B": a.B, "seed": 0, "split": a.split,
                                                                  "unit": "image (paired)", "results": boot}, indent=2))
    (out / "bootstrap_absolute.json").write_text(json.dumps({
        "B": a.B, "seed": 0, "split": a.split, "unit": "image", "note": "same resamples as bootstrap_vs_reference.json",
        "results": {r: {k: {"mean": round(float(np.nanmean(v)), 4),
                            "ci95": [round(float(np.nanpercentile(v, 2.5)), 4), round(float(np.nanpercentile(v, 97.5)), 4)]}
                        for k, v in d.items() if len(v)} for r, d in absolute.items()}}, indent=2))

    if a.sweep:
        pr = P.get(a.sweep) or preds_of(a.sweep)
        with open(out / f"threshold_sweep_{a.sweep}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["conf", "class", "precision", "recall", "f1", "tp", "fp", "gt"])
            for conf in np.round(np.arange(0.05, 0.81, 0.05), 2):
                tp, fp, gt = per_image_counts(samples, pr, float(conf))
                for k, c in NAMES.items():
                    t, fpos, g = tp[:, k].sum(), fp[:, k].sum(), gt[:, k].sum()
                    p_ = t / max(t + fpos, 1); r_ = t / max(g, 1)
                    w.writerow([conf, c, round(p_, 4), round(r_, 4), round(2 * p_ * r_ / max(p_ + r_, 1e-9), 4), int(t), int(fpos), int(g)])
                t, fpos, g = tp.sum(), fp.sum(), gt.sum()
                p_ = t / max(t + fpos, 1); r_ = t / max(g, 1)
                w.writerow([conf, "ALL", round(p_, 4), round(r_, 4), round(2 * p_ * r_ / max(p_ + r_, 1e-9), 4), int(t), int(fpos), int(g)])
    print("written", out)


if __name__ == "__main__":
    main()
