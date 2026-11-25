"""Fine-tune a pretrained Ultralytics YOLO model on the construction-PPE dataset.

Typical use (from the SiteGuard-AI folder):

    .venv/bin/python -m src.training.train                 # full run with configs/settings.yaml
    .venv/bin/python -m src.training.train --epochs 1      # quick smoke test
    .venv/bin/python -m src.training.train --resume experiments/<run>/weights/last.pt

Transfer learning: the network starts from COCO-pretrained YOLO weights
(models/pretrained/yolo26n.pt). Ultralytics replaces the 80-class detection head
with a 12-class head that matches configs/dataset.yaml, then fine-tunes all layers.

After training, the best validation checkpoint is copied to models/trained/best.pt
(an existing best.pt is backed up first, never silently overwritten).
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from src.utils.paths import (  # noqa: I001  (paths must be imported before ultralytics)
    EXPERIMENTS_DIR,
    TRAINED_DIR,
    configure_ultralytics,
    load_settings,
    project_path,
)
from src.utils.dataset_tools import prepare_default_dataset, validate_dataset
from src.utils.logging_config import setup_logging


def pick_device(requested: str = "auto") -> str:
    """Return 'mps' on Apple Silicon when available, otherwise 'cpu' (or the requested device)."""
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def backup_if_exists(path: Path) -> Path | None:
    """Rename an existing file to <name>.<timestamp>.bak so it is never lost."""
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.{stamp}.bak{path.suffix}")
    shutil.move(str(path), backup)
    return backup


def promote_checkpoints(run_dir: Path, log) -> dict:
    """Copy best.pt / last.pt from a run folder into models/trained/."""
    TRAINED_DIR.mkdir(parents=True, exist_ok=True)
    result = {}
    for name in ("best.pt", "last.pt"):
        src = run_dir / "weights" / name
        if not src.exists():
            log.warning("Checkpoint %s not found in %s", name, run_dir)
            continue
        dst = TRAINED_DIR / name
        backup = backup_if_exists(dst)
        if backup:
            log.info("Existing %s backed up to %s", name, backup.name)
        shutil.copy2(src, dst)
        result[name] = {"from": str(src), "to": str(dst), "backup": str(backup) if backup else None}
    return result


def library_versions() -> dict:
    import torch
    import ultralytics

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "mps_available": bool(torch.backends.mps.is_available()),
    }


def write_metadata(model, run_dir: Path, duration: float, extra: dict) -> None:
    """Save a JSON summary of the run (parameters, versions, duration, final metrics)."""
    trainer = model.trainer
    metadata = {
        "created": datetime.now().isoformat(timespec="seconds"),
        **extra,
        "duration_seconds": round(duration, 1),
        "epochs_completed": int(trainer.epoch) + 1,
        "best_fitness": float(trainer.best_fitness) if trainer.best_fitness is not None else None,
        "final_val_metrics": {k: float(v) for k, v in (trainer.metrics or {}).items()},
        "versions": library_versions(),
        "class_names": trainer.data["names"],
    }
    name = "training_metadata_resumed.json" if "resumed_from" in extra else "training_metadata.json"
    (run_dir / name).write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    cfg = load_settings()["training"]
    p = argparse.ArgumentParser(description="Fine-tune YOLO on construction PPE.")
    p.add_argument("--data", type=str, default=None, help="dataset YAML (default: generated full dataset)")
    p.add_argument("--weights", type=str, default=None, help="pretrained weights (default from settings)")
    p.add_argument("--epochs", type=int, default=cfg["epochs"])
    p.add_argument("--imgsz", type=int, default=cfg["image_size"])
    p.add_argument("--batch", type=int, default=cfg["batch"])
    p.add_argument("--workers", type=int, default=cfg["workers"])
    p.add_argument("--patience", type=int, default=cfg["patience"])
    p.add_argument("--device", type=str, default=cfg["device"])
    p.add_argument("--name", type=str, default=cfg["run_name"], help="run folder name under --project")
    p.add_argument("--project", type=str, default=None, help="parent folder for the run (default: experiments/)")
    p.add_argument("--resume", type=str, default=None, help="path to last.pt of an interrupted run")
    p.add_argument("--no-promote", action="store_true", help="do not copy best.pt into models/trained/")
    p.add_argument("--fraction", type=float, default=1.0, help="fraction of training images (smoke tests)")
    p.add_argument("--seed", type=int, default=cfg["seed"], help="random seed (default from settings)")
    p.add_argument("--hyp", type=str, default=None,
                   help="YAML/JSON file of extra Ultralytics train arguments for a documented experiment "
                        "(for example scale, mosaic, cls_pw, multi_scale, cos_lr). Unused = unchanged behaviour")
    return p.parse_args()


# Keys an experiment file may never override: they control where data comes from and where results go.
PROTECTED_TRAIN_KEYS = frozenset({"data", "project", "name", "exist_ok", "resume", "model", "pretrained"})


def load_hyp_overrides(path: Path | None) -> dict:
    """Read extra training arguments for an experiment. Raises SystemExit for protected or unknown keys."""
    if path is None:
        return {}
    import yaml

    if not path.exists():
        raise SystemExit(f"Experiment hyperparameter file not found: {path}")
    extra = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(extra, dict):
        raise SystemExit(f"{path} must contain a mapping of argument names to values")
    bad = sorted(PROTECTED_TRAIN_KEYS & set(extra))
    if bad:
        raise SystemExit(f"{path} may not override protected training arguments: {bad}")
    from ultralytics.cfg import DEFAULT_CFG_DICT

    unknown = sorted(set(extra) - set(DEFAULT_CFG_DICT))
    if unknown:
        raise SystemExit(f"{path} contains unknown Ultralytics arguments: {unknown}")
    return extra


def main() -> None:
    args = parse_args()
    settings = load_settings()
    cfg = settings["training"]
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    log = setup_logging(log_file=EXPERIMENTS_DIR / "training.log")
    configure_ultralytics()
    from ultralytics import YOLO

    device = pick_device(args.device)
    log.info("Training device: %s", device)

    if args.resume:
        # Continue an interrupted run with exactly its original settings (stored inside last.pt).
        resume_path = project_path(args.resume)
        if not resume_path.exists():
            raise SystemExit(f"Checkpoint to resume not found: {resume_path}")
        log.info("Resuming from %s", resume_path)
        model = YOLO(str(resume_path))
        start = time.time()
        model.train(resume=True)
        run_dir = Path(model.trainer.save_dir)
        write_metadata(model, run_dir, time.time() - start, {"resumed_from": str(resume_path), "train_params": vars(model.trainer.args)})
        log.info("Resumed training finished. Run folder: %s", run_dir)
    else:
        if args.data:
            data_yaml = project_path(args.data)
        else:
            report = validate_dataset(check_images=False)
            if not report.ok:
                raise SystemExit(f"Dataset validation failed: {report.to_dict()}")
            data_yaml = prepare_default_dataset()
        weights = project_path(args.weights) if args.weights else project_path(settings["model"]["pretrained_dir"]) / settings["model"]["pretrained_name"]
        if not weights.exists():
            raise SystemExit(f"Pretrained weights not found: {weights}")

        train_params = dict(
            data=str(data_yaml),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            workers=args.workers,
            patience=args.patience,
            device=device,
            seed=args.seed,
            deterministic=True,
            cache=cfg["cache"],
            optimizer=cfg["optimizer"],
            amp=cfg["amp"],
            project=str(project_path(args.project)) if args.project else str(EXPERIMENTS_DIR),
            name=args.name,
            exist_ok=False,  # a new run never overwrites an old run folder (Ultralytics adds a suffix)
            pretrained=True,
            plots=True,
            val=True,
            fraction=args.fraction,
        )
        overrides = load_hyp_overrides(project_path(args.hyp) if args.hyp else None)
        if overrides:
            log.info("Experiment overrides from %s: %s", args.hyp, json.dumps(overrides))
            train_params.update(overrides)
        log.info("Pretrained weights: %s", weights)
        log.info("Training parameters: %s", json.dumps(train_params, indent=2))

        model = YOLO(str(weights))
        start = time.time()
        try:
            model.train(**train_params)
        except KeyboardInterrupt:
            log.warning("Training interrupted. Resume with: --resume <run>/weights/last.pt")
            raise
        duration = time.time() - start
        run_dir = Path(model.trainer.save_dir)

        write_metadata(model, run_dir, duration, {"pretrained_weights": str(weights), "train_params": train_params})
        log.info("Training finished in %.1f min. Run folder: %s", duration / 60, run_dir)

    if not args.no_promote:
        promoted = promote_checkpoints(run_dir, log)
        (TRAINED_DIR / "MODEL_SOURCE.json").write_text(
            json.dumps({"run_dir": str(run_dir), "promoted": promoted, "at": datetime.now().isoformat(timespec="seconds")}, indent=2),
            encoding="utf-8",
        )
        log.info("Checkpoints promoted to %s", TRAINED_DIR)


if __name__ == "__main__":
    main()
