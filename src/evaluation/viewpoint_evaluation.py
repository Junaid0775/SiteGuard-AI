"""Viewpoint generalisation experiment.

Research question: does a model trained only on frontal / eye-level images keep
its accuracy on unseen side and overhead camera viewpoints?

Steps (run from the SiteGuard-AI folder):

    # 1. write image lists + dataset YAMLs from data/viewpoint_metadata.csv
    .venv/bin/python -m src.evaluation.viewpoint_evaluation prepare
    # 2. train a frontal-only model (separate from the main application model)
    .venv/bin/python -m src.training.train --data data/generated/viewpoint/frontal_train.yaml \
        --name viewpoint_frontal_only --no-promote
    # 3. evaluate that model on each viewpoint group
    .venv/bin/python -m src.evaluation.viewpoint_evaluation evaluate \
        --weights experiments/viewpoint_frontal_only/weights/best.pt --name viewpoint_frontal_only
    # 4. (comparison) the main app model on the val-split groups only - it was trained on the
    #    whole train split, so train-split side/overhead images are NOT unseen for it
    .venv/bin/python -m src.evaluation.viewpoint_evaluation evaluate \
        --weights models/trained/best.pt --name main_model_all_views --val-only

    # or all of the above in one go:
    zsh scripts/run_viewpoint_experiment.sh

Split rules
- Training set: train-split images labelled `frontal`.
- Validation during training: val-split images labelled `frontal`.
- Held-out test groups: every `side`, `overhead` and `low_angle` image from BOTH
  splits. None of them is used for training, so all are unseen by this model.
- `unclear` images (no visible workers) are excluded from every group.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from src.utils.paths import (  # noqa: I001
    EXPERIMENTS_DIR,
    GENERATED_DATA_DIR,
    VIEWPOINT_CSV,
    configure_ultralytics,
    project_path,
)
from src.utils.dataset_tools import build_mirror, write_dataset_yaml, write_image_list

VIEWPOINT_DIR = GENERATED_DATA_DIR / "viewpoint"
RESULTS_DIR = EXPERIMENTS_DIR / "viewpoint_results"
NON_FRONTAL = ("side", "overhead", "low_angle")


def load_metadata(csv_path: Path = VIEWPOINT_CSV) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_groups(rows: list[dict]) -> dict[str, list[dict]]:
    """Return the image rows for every split/test group defined in the module docstring."""
    groups: dict[str, list[dict]] = {
        "frontal_train": [r for r in rows if r["viewpoint"] == "frontal" and r["source_split"] == "train"],
        "frontal_val": [r for r in rows if r["viewpoint"] == "frontal" and r["source_split"] == "val"],
    }
    for vp in NON_FRONTAL:
        groups[f"{vp}_all"] = [r for r in rows if r["viewpoint"] == vp]
    groups["non_frontal_all"] = [r for r in rows if r["viewpoint"] in NON_FRONTAL]
    # Same-source comparison: only val-split images (frontal_val vs non_frontal_val).
    groups["non_frontal_val"] = [r for r in rows if r["viewpoint"] in NON_FRONTAL and r["source_split"] == "val"]
    # Image-type controls. Viewpoint is confounded with image group (close-up vs wide scene):
    # - close-up comparison: frontal close-ups vs side close-ups (same image style, different viewpoint)
    # - scene comparison: wide frontal scenes vs overhead scenes (only 7 frontal scene val images!)
    groups["frontal_closeup_val"] = [r for r in rows if r["viewpoint"] == "frontal" and r["image_group"] == "close_up" and r["source_split"] == "val"]
    groups["side_closeup_all"] = [r for r in rows if r["viewpoint"] == "side" and r["image_group"] == "close_up"]
    groups["frontal_scene_val"] = [r for r in rows if r["viewpoint"] == "frontal" and r["image_group"] == "scene" and r["source_split"] == "val"]
    groups["overhead_scene_all"] = [r for r in rows if r["viewpoint"] == "overhead" and r["image_group"] == "scene"]
    # Val-split-only groups: also unseen by the main application model (trained on the full train split),
    # so both models can be compared on exactly the same images.
    groups["side_val"] = [r for r in rows if r["viewpoint"] == "side" and r["source_split"] == "val"]
    groups["overhead_val"] = [r for r in rows if r["viewpoint"] == "overhead" and r["source_split"] == "val"]
    return groups


def val_only_group_names(rows: list[dict] | None = None) -> list[str]:
    """Groups whose images all come from the official val split (safe for the main model)."""
    groups = build_groups(rows if rows is not None else load_metadata())
    return [n for n, members in groups.items() if members and n != "frontal_train" and all(r["source_split"] == "val" for r in members)]


def check_no_leakage(groups: dict[str, list[dict]]) -> None:
    train = {r["filename"] for r in groups["frontal_train"]}
    for name, members in groups.items():
        if name == "frontal_train":
            continue
        overlap = train & {r["filename"] for r in members}
        if overlap:
            raise RuntimeError(f"Leakage: {len(overlap)} training images found in group {name}")


def prepare() -> dict[str, int]:
    mirror = build_mirror()
    groups = build_groups(load_metadata())
    check_no_leakage(groups)
    counts = {}
    for name, members in groups.items():
        images = [mirror / "images" / r["source_split"] / r["filename"] for r in members]
        write_image_list(VIEWPOINT_DIR / f"{name}.txt", images)
        counts[name] = len(images)
    # Training YAML: train on frontal_train, validate on frontal_val.
    write_dataset_yaml(
        VIEWPOINT_DIR / "frontal_train.yaml",
        train=VIEWPOINT_DIR / "frontal_train.txt",
        val=VIEWPOINT_DIR / "frontal_val.txt",
        root=mirror,
    )
    # One evaluation YAML per group (Ultralytics evaluates the `val` entry).
    for name in groups:
        if name == "frontal_train":
            continue
        write_dataset_yaml(VIEWPOINT_DIR / f"eval_{name}.yaml", train=VIEWPOINT_DIR / "frontal_train.txt", val=VIEWPOINT_DIR / f"{name}.txt", root=mirror)
    (VIEWPOINT_DIR / "group_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    return counts


def evaluate(
    weights: Path,
    imgsz: int = 640,
    device: str = "auto",
    batch: int = 8,
    groups: list[str] | None = None,
    run_name: str | None = None,
    description: str = "",
) -> dict:
    configure_ultralytics()
    from ultralytics import YOLO

    from src.training.train import pick_device

    device = pick_device(device)
    run_name = run_name or Path(weights).parent.parent.name
    counts = json.loads((VIEWPOINT_DIR / "group_counts.json").read_text(encoding="utf-8"))
    results = {
        "weights": str(weights),
        "run_name": run_name,
        "description": description,
        "created": datetime.now().isoformat(timespec="seconds"),
        "groups": {},
    }
    model = YOLO(str(weights))
    for name in counts:
        if name == "frontal_train" or counts[name] == 0 or (groups is not None and name not in groups):
            continue
        m = model.val(
            data=str(VIEWPOINT_DIR / f"eval_{name}.yaml"),
            imgsz=imgsz,
            batch=batch,
            device=device,
            plots=True,
            project=str(RESULTS_DIR / run_name),
            name=name,
            exist_ok=True,
            verbose=False,
        )
        per_class = {}
        for i, cid in enumerate(m.box.ap_class_index):
            p, r, ap50, ap = m.box.class_result(i)
            per_class[model.names[int(cid)]] = {"precision": float(p), "recall": float(r), "mAP50": float(ap50), "mAP50-95": float(ap)}
        results["groups"][name] = {
            "images": counts[name],
            "instances": int(sum(m.nt_per_class)) if hasattr(m, "nt_per_class") else None,
            "precision": float(m.box.mp),
            "recall": float(m.box.mr),
            "mAP50": float(m.box.map50),
            "mAP50-95": float(m.box.map),
            "per_class": per_class,
        }
    g = results["groups"]
    if "frontal_val" in g:
        results["mAP50-95_difference"] = {
            f"frontal_val_minus_{k}": round(g["frontal_val"]["mAP50-95"] - g[k]["mAP50-95"], 4)
            for k in g
            if k != "frontal_val"
        }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"viewpoint_metrics_{run_name}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved {out}")
    return results


def main() -> None:
    p = argparse.ArgumentParser(description="Viewpoint generalisation experiment")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--weights", required=True)
    ev.add_argument("--imgsz", type=int, default=640)
    ev.add_argument("--device", default="auto")
    ev.add_argument("--name", default=None, help="result name (default: run folder of the weights)")
    ev.add_argument("--description", default="", help="shown on the dashboard")
    ev.add_argument("--val-only", action="store_true",
                    help="evaluate only groups made of official val-split images (required for the main app model, "
                         "which was trained on the whole train split)")
    args = p.parse_args()
    if args.cmd == "prepare":
        print(json.dumps(prepare(), indent=2))
    else:
        selected = val_only_group_names() if args.val_only else None
        res = evaluate(project_path(args.weights), imgsz=args.imgsz, device=args.device, groups=selected,
                       run_name=args.name, description=args.description)
        for name, m in res["groups"].items():
            print(f"{name:20s} n={m['images']:4d} P={m['precision']:.3f} R={m['recall']:.3f} mAP50={m['mAP50']:.3f} mAP50-95={m['mAP50-95']:.3f}")
        print(json.dumps(res.get("mAP50-95_difference", {}), indent=2))


if __name__ == "__main__":
    main()
