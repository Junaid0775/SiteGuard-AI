"""Read-only loaders for the evaluation results shown on the Model Evaluation and Overview pages.

Every number comes from a file written by an evaluation script; nothing is computed or estimated here. Each loader
returns None when its file is missing or unreadable, and the page then omits that block instead of guessing.
Sources: experiments/evaluation/trained_best/ (YOLO26n, development set) and experiments/accuracy_improvement/
(YOLO26m accuracy programme, REPORT-022 to REPORT-025).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.utils.paths import EXPERIMENTS_DIR, TRAINED_DIR

AI = EXPERIMENTS_DIR / "accuracy_improvement"
E3_KEY = "yolo26m_e3_896_v1"
E3_CARD = TRAINED_DIR / "yolo26m_accuracy_candidate" / E3_KEY / "model_card.json"
MISSING_PPE = ["no_helmet", "no_gloves", "no_goggle", "no_boots", "no_vest"]
# Targets defined before the accuracy programme (SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md §0).
TARGETS = {"mAP50": 0.93, "precision": 0.90, "recall": 0.90, "missing_recall": 0.90, "mAP50-95 (stretch)": 0.80}
REPORTS = {
    "decision": "experiments/accuracy_improvement/reports/REPORT-025-final-research-decision.md",
    "qualification": "experiments/accuracy_improvement/reports/REPORT-024-qualification-and-integration.md",
    "comparison": "experiments/accuracy_improvement/reports/REPORT-023-model-comparison-and-error-analysis.md",
}


def _json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def active_model_dev_metrics() -> dict | None:
    """YOLO26n on the development set (original val split, 200 images): experiments/evaluation/trained_best/metrics.json."""
    return _json(EXPERIMENTS_DIR / "evaluation" / "trained_best" / "metrics.json")


def dev_comparison() -> dict | None:
    """Same-split comparison on the development set (200 images, protocol v1) for YOLO26n and the E3 candidate."""
    path = AI / "error_analysis" / "comparison_dev_vs_E1" / "comparison.csv"
    if not path.exists():
        return None
    try:
        rows = {r["run"]: r for r in csv.DictReader(path.open(encoding="utf-8"))}
    except (OSError, csv.Error, KeyError):
        return None
    want = {"dev_yolo26n_active_baseline": "YOLO26n (active, 640 px)", "dev_E3_m896": "E3 research candidate (896 px)"}
    if not all(k in rows for k in want):
        return None

    def f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    out = []
    for run, label in want.items():
        r = rows[run]
        out.append({
            "Model": label,
            "mAP50": f(r.get("mAP50")), "mAP50-95": f(r.get("mAP50-95")),
            "Precision @0.25": f(r.get("P@0.25")), "Recall @0.25": f(r.get("R@0.25")),
            **{f"{c} recall @0.25": f(r.get(f"R@0.25 {c}")) for c in MISSING_PPE},
        })
    boot = _json(AI / "error_analysis" / "comparison_dev_vs_yolo26n" / "bootstrap_vs_reference.json")
    diff = (boot or {}).get("results", {}).get("dev_E3_m896")
    return {"rows": out, "bootstrap_e3_minus_yolo26n": diff, "source": str(path.relative_to(EXPERIMENTS_DIR.parent)),
            "split": "development set = original val split, 200 images, 2,961 objects"}


def e3_research() -> dict | None:
    """E3 research candidate (not promoted): model card, held-back test results, intervals, runtime replay."""
    card = _json(E3_CARD)
    summary = _json(AI / "evaluation" / "test_E3_m896" / "summary.json")
    if not card or not summary:
        return None
    absolute = (_json(AI / "qualification" / "locked_test_analysis" / "bootstrap_absolute.json") or {}).get("results", {})
    ci = absolute.get("test_E3_m896", {})
    family = _json(AI / "evaluation" / "test_E3_m896" / "family_strata.json") or {}
    replay = _json(AI / "qualification" / "realtime" / "realtime_webcam_replay.json") or {}
    low_light = _json(AI / "qualification" / "realtime" / "realtime_low_light.json") or {}
    per_class = (_json(AI / "evaluation" / "test_E3_m896" / "metrics_ultralytics.json") or {}).get("per_class", {})
    u, op = summary.get("ultralytics") or {}, summary.get("operating_point") or {}

    def perf(name):
        p = ((replay.get(name) or {}).get("raw") or {}).get("performance") or {}
        return {"received_fps": p.get("received_fps"), "analysed_fps": p.get("analysed_fps"),
                "dropped": p.get("frames_dropped_queue"), "frames": p.get("frames_received"),
                "inference_mean_ms": (p.get("inference_ms") or {}).get("mean"),
                "inference_p95_ms": (p.get("inference_ms") or {}).get("p95")} if p else None

    return {
        "card": {k: card.get(k) for k in ("model_key", "status", "architecture", "image_size", "checkpoint",
                                          "checkpoint_sha256", "created", "registered_in_settings", "active_default")},
        "test": {
            "images": summary.get("images"), "objects": summary.get("gt_objects"),
            "mAP50": u.get("mAP50"), "mAP50-95": u.get("mAP50-95"),
            "precision_op": op.get("precision"), "recall_op": op.get("recall"),
            "missing_recall": {c: (summary.get("missing_ppe_recall_op") or {}).get(c) for c in MISSING_PPE},
            "missing_recall_ci": {c: (ci.get(f"recall@0.25 {c}") or {}).get("ci95") for c in MISSING_PPE},
            "missing_instances": {c: (per_class.get(c) or {}).get("instances") for c in MISSING_PPE},
            "precision_ci": (ci.get("precision@0.25") or {}).get("ci95"),
            "recall_ci": (ci.get("recall@0.25") or {}).get("ci95"),
        },
        "family": {k: {"images": v.get("images"), "mAP50": v.get("mAP50")} for k, v in family.items()},
        "replay": {"e3": perf("e3_candidate"), "yolo26n": perf("yolo26n")},
        "dark": {m: ((low_light.get(m) or {}).get("cam720_dark") or {}).get("mAP50") for m in ("e3_candidate", "yolo26n")},
        "sources": {"test": "experiments/accuracy_improvement/evaluation/test_E3_m896/summary.json",
                    "card": str(E3_CARD.relative_to(EXPERIMENTS_DIR.parent)), **REPORTS},
    }
