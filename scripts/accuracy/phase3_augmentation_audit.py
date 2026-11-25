"""Phase 3 augmentation audit (specification §5.2): what each policy does to the labelled boxes.

    .venv/bin/python scripts/accuracy/phase3_augmentation_audit.py [--samples 300]

For each policy, builds the Ultralytics 8.4 TRAINING dataset (train split of datasets/v1_original_labels, augment=True,
the same code path as model.train) and draws augmented samples with a fixed seed. Records:
  * boxes per sample and per class (survival relative to the un-augmented reference at the same image size)
  * short side of every box in the augmented image (px): share < 4 px, < 8 px, median
  * contact sheets with the labels drawn (visual audit), experiments/accuracy_improvement/augmented_samples/<policy>/
Reference 'ref_<imgsz>' = augment=False (letterbox only). Nothing is trained; the original data is only read.
Note: Ultralytics drops boxes narrower or shorter than 2 px after augmentation (box_candidates, wh_thr=2).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import src.utils.paths  # noqa: E402,F401

AI = ROOT / "experiments" / "accuracy_improvement"
DS = AI / "datasets" / "v1_original_labels"
OUT = AI / "augmented_samples"
NAMES = ["helmet", "gloves", "vest", "boots", "goggles", "Person", "no_helmet", "no_goggle", "no_gloves", "no_boots", "forklift", "no_vest"]
COLOURS = [(0, 200, 255), (255, 160, 0), (0, 255, 0), (160, 80, 0), (255, 0, 255), (60, 200, 60), (0, 0, 255), (128, 0, 255),
           (0, 80, 255), (0, 120, 200), (200, 200, 0), (0, 0, 160)]

POLICIES = {
    # previous runs (Ultralytics defaults, as used for YOLO26n/YOLO26m)
    "P0_default": {"mosaic": 1.0, "scale": 0.5, "translate": 0.1, "fliplr": 0.5, "flipud": 0.0, "hsv_h": 0.015, "hsv_s": 0.7, "hsv_v": 0.4,
                   "degrees": 0.0, "shear": 0.0, "perspective": 0.0, "mixup": 0.0},
    # small-object conservative: no strong down-scaling, otherwise unchanged
    "P1_scale_0.25": {"mosaic": 1.0, "scale": 0.25, "translate": 0.1, "fliplr": 0.5, "flipud": 0.0, "hsv_h": 0.015, "hsv_s": 0.7,
                      "hsv_v": 0.4, "degrees": 0.0, "shear": 0.0, "perspective": 0.0, "mixup": 0.0},
    # P1 with gentler colour changes (moderate brightness / saturation)
    "P2_scale_0.25_colour_mild": {"mosaic": 1.0, "scale": 0.25, "translate": 0.1, "fliplr": 0.5, "flipud": 0.0, "hsv_h": 0.01,
                                  "hsv_s": 0.4, "hsv_v": 0.3, "degrees": 0.0, "shear": 0.0, "perspective": 0.0, "mixup": 0.0},
    # no mosaic (mosaic at 640 halves every source image before placing it)
    "P3_no_mosaic_scale_0.25": {"mosaic": 0.0, "scale": 0.25, "translate": 0.1, "fliplr": 0.5, "flipud": 0.0, "hsv_h": 0.015,
                                "hsv_s": 0.7, "hsv_v": 0.4, "degrees": 0.0, "shear": 0.0, "perspective": 0.0, "mixup": 0.0},
}


def build(imgsz: int, hyp: dict | None):
    from ultralytics.cfg import get_cfg
    from ultralytics.data.build import build_yolo_dataset
    from ultralytics.data.utils import check_det_dataset
    data = check_det_dataset(str(DS / "dev.yaml"))
    cfg = get_cfg(overrides={"imgsz": imgsz, **(hyp or {}), "cache": False, "fraction": 1.0})
    return build_yolo_dataset(cfg, data["train"], batch=8, data=data, mode="train" if hyp is not None else "val", rect=False, stride=32)


def draw(sample: dict) -> np.ndarray:
    img = sample["img"].numpy().transpose(1, 2, 0)[:, :, ::-1].copy()  # CHW RGB -> HWC BGR
    h, w = img.shape[:2]
    for c, b in zip(sample["cls"].numpy().ravel(), sample["bboxes"].numpy()):
        x, y, bw, bh = b
        p1 = (int((x - bw / 2) * w), int((y - bh / 2) * h))
        p2 = (int((x + bw / 2) * w), int((y + bh / 2) * h))
        cv2.rectangle(img, p1, p2, COLOURS[int(c)], 1)
    return img


def audit(name: str, imgsz: int, hyp: dict | None, n: int) -> dict:
    random.seed(0)
    np.random.seed(0)
    import torch
    torch.manual_seed(0)
    ds = build(imgsz, hyp)
    idx = np.random.default_rng(0).choice(len(ds), size=min(n, len(ds)), replace=False)
    per_class, shorts, boxes_per_sample, tiles = Counter(), [], [], []
    for k, i in enumerate(idx):
        s = ds[int(i)]
        h, w = s["img"].shape[1:]
        b = s["bboxes"].numpy()
        cls = s["cls"].numpy().ravel().astype(int)
        boxes_per_sample.append(len(b))
        for c, (x, y, bw, bh) in zip(cls, b):
            per_class[NAMES[c]] += 1
            shorts.append(min(bw * w, bh * h))
        if k < 32:
            t = draw(s)
            tiles.append(cv2.resize(t, (320, 320), interpolation=cv2.INTER_AREA))
    d = OUT / f"{name}_{imgsz}"
    d.mkdir(parents=True, exist_ok=True)
    for sh in range(0, len(tiles), 16):
        grid = np.vstack([np.hstack(tiles[sh + r * 4: sh + r * 4 + 4]) for r in range(4) if len(tiles[sh + r * 4: sh + r * 4 + 4]) == 4])
        cv2.imwrite(str(d / f"sheet_{sh // 16 + 1}.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    shorts = np.array(shorts)
    return {"policy": name, "imgsz": imgsz, "hyp": hyp, "samples": int(len(idx)), "boxes": int(len(shorts)),
            "boxes_per_sample_mean": round(float(np.mean(boxes_per_sample)), 2),
            "short_side_px": {"median": round(float(np.median(shorts)), 1), "lt4_share": round(float((shorts < 4).mean()), 4),
                              "lt8_share": round(float((shorts < 8).mean()), 4), "ge32_share": round(float((shorts >= 32).mean()), 4)},
            "per_class": dict(per_class)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=300)
    a = ap.parse_args()
    results = []
    for imgsz in (640, 1024):
        results.append(audit("ref_no_augmentation", imgsz, None, a.samples))
        for name, hyp in POLICIES.items():
            results.append(audit(name, imgsz, hyp, a.samples))
    # survival relative to the reference at the same size: per-sample box counts are comparable because every
    # sample is one training image (mosaic samples combine parts of 4 images, so their counts are reported, not ratioed)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "augmentation_audit.json").write_text(json.dumps(results, indent=2))
    for r in results:
        print(f"{r['policy']:28s} {r['imgsz']:5d}  boxes/sample {r['boxes_per_sample_mean']:6.2f}  "
              f"short median {r['short_side_px']['median']:6.1f}  <4px {r['short_side_px']['lt4_share']:.3f}  "
              f"<8px {r['short_side_px']['lt8_share']:.3f}  no_helmet {r['per_class'].get('no_helmet', 0)}  "
              f"no_goggle {r['per_class'].get('no_goggle', 0)}  no_gloves {r['per_class'].get('no_gloves', 0)}")


if __name__ == "__main__":
    main()
