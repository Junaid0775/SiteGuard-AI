"""Verify the identity of the existing checkpoints (accuracy-improvement specification, Phase 0).

    .venv/bin/python scripts/accuracy/model_identity.py <out_dir> [--val]

For each checkpoint it records sha256, size, architecture YAML, class count, class names (checked against
configs/dataset.yaml and the original data.yaml), parameter count, the training arguments stored inside the
checkpoint, epoch, Ultralytics version and creation date, and compares the sha256 with the value recorded in
REPORT-014/015.

--val re-runs Ultralytics validation with the historical procedure (imgsz 640, batch 8, conf 0.001,
NMS IoU 0.7, MPS) on the original 200-image val split through the project's symlink mirror, and compares
the result with the historical metrics. Checkpoints and data are only read.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
import src.utils.paths  # noqa: E402,F401  (sets YOLO_CONFIG_DIR to the project's Ultralytics config)
import yaml  # noqa: E402

CHECKPOINTS = {
    "yolo26n_active": {
        "path": "models/trained/best.pt",
        "expected_sha256": "890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b",
        "historical": {"precision": 0.8322, "recall": 0.6809, "mAP50": 0.7339, "mAP50-95": 0.5227},
        "source": "REPORT-010 §10 / REPORT-015 §1",
    },
    "yolo26m_previous": {
        "path": "experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt",
        "expected_sha256": "399c4e5be335e3544afe185c7abb08d5fc894a382b891d970f71b94df3f1773f",
        "historical": {"precision": 0.8909, "recall": 0.7773, "mAP50": 0.8311, "mAP50-95": 0.6195},
        "source": "REPORT-014 §10 / REPORT-015 §1",
    },
}
PRETRAINED = {"yolo26n.pt": None, "yolo26m.pt": "401cea9a"}  # REPORT-013 recorded the yolo26m.pt prefix
ARG_KEYS = ("model", "data", "epochs", "batch", "imgsz", "seed", "deterministic", "optimizer", "lr0", "lrf",
            "momentum", "weight_decay", "warmup_epochs", "patience", "cos_lr", "close_mosaic", "mosaic", "mixup",
            "copy_paste", "fliplr", "scale", "translate", "hsv_h", "hsv_s", "hsv_v", "nbs", "amp", "device",
            "project", "name", "fraction", "cache", "workers", "pretrained")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(path: Path) -> dict:
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model = ck.get("ema") or ck.get("model")
    myaml = getattr(model, "yaml", {}) or {}
    names = {int(k): str(v) for k, v in getattr(model, "names", {}).items()}
    args = ck.get("train_args") or {}
    return {
        "sha256": sha256(path), "size_bytes": path.stat().st_size,
        "architecture_yaml": myaml.get("yaml_file"), "nc": myaml.get("nc"), "scale": myaml.get("scale"),
        "names": names, "parameters": int(sum(p.numel() for p in model.parameters())),
        "epoch_field": ck.get("epoch"), "best_fitness": ck.get("best_fitness"),
        "ultralytics_version_in_checkpoint": ck.get("version"), "date": ck.get("date"),
        "train_args": {k: args.get(k) for k in ARG_KEYS if k in args},
    }


def main(out_dir: Path, run_val: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    project_names = {int(k): v for k, v in yaml.safe_load((PROJECT / "configs/dataset.yaml").read_text())["names"].items()}
    original_names = {int(k): v for k, v in yaml.safe_load((PROJECT.parent / "construction-ppe/data.yaml").read_text())["names"].items()}
    settings = yaml.safe_load((PROJECT / "configs/settings.yaml").read_text())
    report: dict = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "active_checkpoint_setting": settings["model"]["trained_weights"],
        "class_mapping": {"configs/dataset.yaml": project_names, "construction-ppe/data.yaml": original_names,
                          "identical": project_names == original_names},
        "checkpoints": {}, "pretrained": {},
    }
    for key, spec in CHECKPOINTS.items():
        p = PROJECT / spec["path"]
        d = describe(p)
        d.update({"path": spec["path"], "sha256_matches_recorded": d["sha256"] == spec["expected_sha256"],
                  "names_match_dataset": d["names"] == original_names, "historical_metrics": spec["historical"],
                  "historical_source": spec["source"]})
        report["checkpoints"][key] = d
    for name, prefix in PRETRAINED.items():
        p = PROJECT / "models/pretrained" / name
        if p.exists():
            h = sha256(p)
            report["pretrained"][name] = {"sha256": h, "size_bytes": p.stat().st_size,
                                          "prefix_matches_recorded": (h.startswith(prefix) if prefix else None)}
    report["active_is"] = next((k for k, s in CHECKPOINTS.items() if s["path"] == report["active_checkpoint_setting"]), "UNKNOWN")

    if run_val:
        from ultralytics import YOLO
        data = PROJECT / "data/generated/dataset_resolved.yaml"
        for key, spec in CHECKPOINTS.items():
            r = YOLO(str(PROJECT / spec["path"])).val(
                data=str(data), imgsz=640, batch=8, conf=0.001, iou=0.7, device="mps", plots=False,
                save_json=False, project=str(out_dir), name=f"val_{key}", exist_ok=False, verbose=False)
            box = r.box
            got = {"precision": round(float(box.mp), 4), "recall": round(float(box.mr), 4),
                   "mAP50": round(float(box.map50), 4), "mAP50-95": round(float(box.map), 4)}
            per_class = {}
            for i, c in enumerate(box.ap_class_index):
                per_class[r.names[int(c)]] = {"P": round(float(box.p[i]), 4), "R": round(float(box.r[i]), 4),
                                              "AP50": round(float(box.ap50[i]), 4), "AP50-95": round(float(box.ap[i]), 4)}
            hist = spec["historical"]
            report["checkpoints"][key]["revalidation"] = {
                "settings": {"split": "val (200 images)", "imgsz": 640, "batch": 8, "conf": 0.001, "nms_iou": 0.7,
                             "device": "mps", "data": "data/generated/dataset_resolved.yaml (symlink mirror)"},
                "metrics": got, "per_class": per_class,
                "max_abs_diff_vs_historical": round(max(abs(got[k] - hist[k]) for k in hist), 4),
                "speed_ms_per_image": {k: round(v, 2) for k, v in r.speed.items()},
            }
    (out_dir / "model_identity.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    for key, d in report["checkpoints"].items():
        print(key, d["path"], d["sha256"][:16], "sha_ok" if d["sha256_matches_recorded"] else "SHA MISMATCH",
              d["architecture_yaml"], "nc", d["nc"], "params", d["parameters"],
              "names_ok" if d["names_match_dataset"] else "NAMES MISMATCH",
              d.get("revalidation", {}).get("metrics"), "maxdiff", d.get("revalidation", {}).get("max_abs_diff_vs_historical"))
    print("active:", report["active_checkpoint_setting"], "=", report["active_is"], "| mapping identical:",
          report["class_mapping"]["identical"], "| pretrained:", {k: v["sha256"][:12] for k, v in report["pretrained"].items()})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]), "--val" in sys.argv)
