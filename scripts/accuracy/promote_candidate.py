"""Phase 7: store a qualified YOLO26m candidate as a separate, versioned checkpoint with a model card and register it.

    .venv/bin/python scripts/accuracy/promote_candidate.py --run experiments/accuracy_improvement/training/<run> \
        --key yolo26m_candidate_v1 --imgsz <N> --report <REPORT-024 path> [--dev-eval <dir>] [--test-eval <dir>] [--activate]

* copies <run>/weights/best.pt to models/trained/yolo26m_accuracy_candidate/<key>/best.pt (refuses to overwrite)
* writes model_card.json next to it: model name, architecture, training run and arguments, checkpoint SHA-256,
  dataset version and split hashes, class mapping, image size, thresholds, evaluation summaries and report paths
* adds the registry entry to configs/settings.yaml (backup first); with --activate it also sets model.active to the
  new key. The fallback stays 'yolo26n_baseline'. models/trained/best.pt is never touched.
* verifies that the application loads the new entry (hash equal to the card, class mapping, architecture).
* --no-register (candidate that did not pass the promotion gates): stores the checkpoint and its model card only.
  configs/settings.yaml is not touched; the stored copy is validated directly (hash, class mapping, architecture).
  --status records the qualification outcome in the card.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
AI = ROOT / "experiments" / "accuracy_improvement"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--imgsz", type=int, required=True)
    ap.add_argument("--report", action="append", default=[])
    ap.add_argument("--dev-eval", default=None)
    ap.add_argument("--test-eval", default=None)
    ap.add_argument("--description", default="")
    ap.add_argument("--activate", action="store_true")
    ap.add_argument("--no-register", action="store_true", help="store checkpoint + model card only; settings.yaml untouched")
    ap.add_argument("--status", default=None, help="qualification outcome recorded in the model card")
    a = ap.parse_args()
    if a.activate and a.no_register:
        raise SystemExit("--activate and --no-register exclude each other")
    status = a.status or ("promoted: active default" if a.activate else
                          "not promoted: stored only, not registered" if a.no_register else "registered, not active")
    run = ROOT / a.run
    src = run / "weights" / "best.pt"
    dst_dir = ROOT / "models" / "trained" / "yolo26m_accuracy_candidate" / a.key
    dst = dst_dir / "best.pt"
    if dst.exists():
        raise SystemExit(f"{dst} already exists - never overwritten; choose a new --key")
    prod = ROOT / "models" / "trained" / "best.pt"
    prod_sha = sha256(prod)
    dst_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(src, dst)
    sha = sha256(dst)
    assert sha == sha256(src), "copy differs from source"

    import torch
    ck = torch.load(dst, map_location="cpu", weights_only=False)
    m = ck.get("ema") or ck["model"]
    args = yaml.safe_load((run / "args.yaml").read_text()) if (run / "args.yaml").exists() else {}
    settings = yaml.safe_load((ROOT / "configs" / "settings.yaml").read_text())

    def summary(d):
        if not d:
            return None
        p = ROOT / d / "summary.json"
        return {"path": d, **json.loads(p.read_text())} if p.exists() else None

    card = {
        "model_key": a.key, "description": a.description, "status": status,
        "registered_in_settings": not a.no_register, "active_default": a.activate,
        "architecture": Path(str((getattr(m, "yaml", {}) or {}).get("yaml_file", ""))).stem,
        "parameters": int(sum(p.numel() for p in m.parameters())),
        "checkpoint": str(dst.relative_to(ROOT)), "checkpoint_sha256": sha, "checkpoint_bytes": dst.stat().st_size,
        "training_run": str(run.relative_to(ROOT)), "source_checkpoint_sha256": sha256(src),
        "training_arguments": {k: args.get(k) for k in ("model", "data", "epochs", "batch", "imgsz", "seed", "optimizer", "lr0",
                                                       "scale", "hsv_h", "hsv_s", "hsv_v", "cls_pw", "mosaic", "close_mosaic", "patience")},
        "dataset_version": "datasets/v1_original_labels (symlinks to ../construction-ppe, unchanged labels)",
        "split_list_sha256": {s: sha256(AI / "splits" / f"{s}.txt") for s in ("train", "dev", "test")},
        "class_mapping": {int(k): str(v) for k, v in m.names.items()},
        "image_size": a.imgsz,
        "thresholds": {"detection_confidence": settings["inference"]["confidence_threshold"],
                       "nms_iou": settings["inference"]["iou_threshold"],
                       "compliance": settings["compliance"], "note": "compliance and event rules unchanged by this model"},
        "evaluation": {"dev": summary(a.dev_eval), "locked_test": summary(a.test_eval)},
        "reports": a.report,
        "created": datetime.now().isoformat(timespec="seconds"), "ultralytics_version": ck.get("version"),
        "rollback": {"key": "yolo26n_baseline", "weights": "models/trained/best.pt", "sha256": prod_sha},
    }
    (dst_dir / "model_card.json").write_text(json.dumps(card, indent=2, default=str))

    if a.no_register:
        from src.detection.model_registry import load_validated
        _, ident = load_validated(dst, architecture=card["architecture"], expected_sha256=sha)
        assert ident["sha256"] == sha
        assert sha256(prod) == prod_sha, "production checkpoint changed!"
        print(json.dumps({"stored": str(dst.relative_to(ROOT)), "sha256": sha, "registered": False, "activated": False,
                          "status": status, "validated": ident, "yolo26n_unchanged": True}, indent=1))
        return

    cfg = ROOT / "configs" / "settings.yaml"
    backup = AI / "manifests" / f"settings.yaml.before_promote_{a.key}_{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(cfg, backup)
    text = cfg.read_text()
    s = yaml.safe_load(text)
    if a.key in s["model"]["registry"]:
        raise SystemExit(f"registry already has '{a.key}'")
    entry = (f"    {a.key}:\n      weights: {dst.relative_to(ROOT)}\n      architecture: {card['architecture']}\n"
             f"      image_size: {a.imgsz}\n      card: {(dst_dir / 'model_card.json').relative_to(ROOT)}\n"
             f"      description: \"{a.description or 'YOLO26m accuracy-programme candidate'}; sha256 {sha[:8]}...\"\n")
    anchor = "  # Legacy key, used only if no registry is configured."
    assert text.count(anchor) == 1, "settings.yaml layout changed; add the entry by hand"
    text = text.replace(anchor, entry + anchor)
    if a.activate:
        assert text.count("  active: yolo26n_baseline\n") == 1, "unexpected active key in settings.yaml"
        text = text.replace("  active: yolo26n_baseline\n", f"  active: {a.key}\n")
    cfg.write_text(text)

    from src.utils.paths import load_settings
    load_settings.cache_clear()
    from src.detection.detector import PPEDetector
    det = PPEDetector(model_key=a.key).load()
    assert det.status == "active" and det.identity["sha256"] == sha, (det.status, det.load_errors)
    assert sha256(prod) == prod_sha, "production checkpoint changed!"
    print(json.dumps({"stored": str(dst.relative_to(ROOT)), "sha256": sha, "registered": a.key, "activated": a.activate,
                      "settings_backup": str(backup.relative_to(ROOT)), "load_check": det.status,
                      "yolo26n_unchanged": True}, indent=1))


if __name__ == "__main__":
    main()
