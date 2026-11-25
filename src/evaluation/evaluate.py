"""Evaluate a trained checkpoint on the official validation split.

    .venv/bin/python -m src.evaluation.evaluate                       # models/trained/best.pt
    .venv/bin/python -m src.evaluation.evaluate --weights path/to/best.pt

Writes experiments/evaluation/<name>/metrics.json plus Ultralytics plots
(confusion matrix, PR curves). The dashboard's Model Evaluation page reads them.

NOTE: this is ordinary validation on the dataset's own val split. It is not a
viewpoint generalisation test (see viewpoint_evaluation.py for that).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.utils.paths import EXPERIMENTS_DIR, configure_ultralytics, load_settings, project_path
from src.utils.dataset_tools import prepare_default_dataset

EVAL_DIR = EXPERIMENTS_DIR / "evaluation"


def evaluate(weights: Path, name: str = "trained_best", imgsz: int = 640, batch: int = 8, device: str = "auto") -> dict:
    configure_ultralytics()
    from ultralytics import YOLO

    from src.training.train import pick_device

    data_yaml = prepare_default_dataset()
    model = YOLO(str(weights))
    m = model.val(
        data=str(data_yaml), split="val", imgsz=imgsz, batch=batch, device=pick_device(device),
        plots=True, project=str(EVAL_DIR), name=name, exist_ok=True, verbose=False,
    )
    per_class = {}
    for i, cid in enumerate(m.box.ap_class_index):
        p, r, ap50, ap = m.box.class_result(i)
        per_class[model.names[int(cid)]] = {
            "precision": round(float(p), 4), "recall": round(float(r), 4),
            "mAP50": round(float(ap50), 4), "mAP50-95": round(float(ap), 4),
            "instances": int(m.nt_per_class[int(cid)]) if hasattr(m, "nt_per_class") else None,
        }
    out_dir = Path(m.save_dir)
    metrics = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "weights": str(weights),
        "dataset_yaml": str(data_yaml),
        "split": "val (official dataset validation split, 200 images)",
        "image_size": imgsz,
        "overall": {
            "precision": round(float(m.box.mp), 4),
            "recall": round(float(m.box.mr), 4),
            "mAP50": round(float(m.box.map50), 4),
            "mAP50-95": round(float(m.box.map), 4),
        },
        "per_class": per_class,
        "speed_ms_per_image": {k: round(float(v), 2) for k, v in m.speed.items()},
        "plots_dir": str(out_dir),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    settings = load_settings()
    p = argparse.ArgumentParser()
    p.add_argument("--weights", default=settings["model"]["trained_weights"])
    p.add_argument("--name", default="trained_best")
    p.add_argument("--imgsz", type=int, default=settings["training"]["image_size"])
    args = p.parse_args()
    metrics = evaluate(project_path(args.weights), args.name, args.imgsz)
    o = metrics["overall"]
    print(f"Overall  P={o['precision']:.3f}  R={o['recall']:.3f}  mAP50={o['mAP50']:.3f}  mAP50-95={o['mAP50-95']:.3f}")
    for cls, v in metrics["per_class"].items():
        print(f"  {cls:10s} P={v['precision']:.3f} R={v['recall']:.3f} mAP50={v['mAP50']:.3f} mAP50-95={v['mAP50-95']:.3f} n={v['instances']}")
    print(f"Saved to {metrics['plots_dir']}/metrics.json")


if __name__ == "__main__":
    main()
