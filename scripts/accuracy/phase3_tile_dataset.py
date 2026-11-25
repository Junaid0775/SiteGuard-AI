"""Phase 3: tile-crop training data derived ONLY from the training split (specification §5.3, matrix item 6).

    .venv/bin/python scripts/accuracy/phase3_tile_dataset.py [--max-short 12] [--grid 2] [--overlap 0.2] [--min-visible 0.5]

Selects training images that contain at least one missing-PPE box whose short side is < --max-short px at the
640 inference scale, cuts each into a grid x grid set of overlapping tiles at NATIVE resolution, and writes the
tiles (JPEG q95) with clipped labels. A box is kept in a tile if >= --min-visible of its area is inside the tile
(clipped to the tile); otherwise it is dropped and counted (it becomes background in that tile). Tiles without any
kept box are not written. Result: experiments/accuracy_improvement/datasets/v2_train_tiles/
  images/train, labels/train  = symlinks to the 640 original training images and labels + the tile files
  images/dev, labels/dev      = symlinks to the dev split (unchanged); dev.yaml (no locked test in this version)
  tiles_manifest.csv          provenance of every tile (source image, window, kept / dropped boxes, label SHA-256)
  sheet_*.jpg                 tiles with labels drawn, for the visual audit
The original dataset is only read. Dev and locked-test images are never used to make tiles.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "experiments" / "accuracy_improvement"
V1 = AI / "datasets" / "v1_original_labels"
V2 = AI / "datasets" / "v2_train_tiles"
NAMES = ["helmet", "gloves", "vest", "boots", "goggles", "Person", "no_helmet", "no_goggle", "no_gloves", "no_boots", "forklift", "no_vest"]
MISSING = {6, 7, 8, 9, 11}


def read_labels(path: Path, w: int, h: int) -> np.ndarray:
    rows = [l.split() for l in path.read_text().splitlines() if l.strip()]
    a = np.array([[float(v) for v in r] for r in rows], dtype=float).reshape(-1, 5)
    out = np.zeros_like(a)
    out[:, 0] = a[:, 0]
    out[:, 1] = (a[:, 1] - a[:, 3] / 2) * w; out[:, 2] = (a[:, 2] - a[:, 4] / 2) * h
    out[:, 3] = (a[:, 1] + a[:, 3] / 2) * w; out[:, 4] = (a[:, 2] + a[:, 4] / 2) * h
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-short", type=float, default=12.0)
    ap.add_argument("--grid", type=int, default=2)
    ap.add_argument("--overlap", type=float, default=0.2)
    ap.add_argument("--min-visible", type=float, default=0.5)
    a = ap.parse_args()
    train = sorted(p for p in (V1 / "images" / "train").iterdir() if p.suffix == ".jpg")
    for kind in ("images", "labels"):
        for s in ("train", "dev"):
            (V2 / kind / s).mkdir(parents=True, exist_ok=True)
    # symlinks: all original training images/labels and the dev split
    for s in ("train", "dev"):
        for p in (V1 / "images" / s).iterdir():
            for kind, src in (("images", p.resolve()), ("labels", (V1 / "labels" / s / f"{p.stem}.txt").resolve())):
                dst = V2 / kind / s / (p.name if kind == "images" else f"{p.stem}.txt")
                if not dst.is_symlink():
                    os.symlink(src, dst)
    rows, stats, sheet_tiles = [], Counter(), []
    for p in train:
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        gt = read_labels(V1 / "labels" / "train" / f"{p.stem}.txt", w, h)
        scale = 640 / max(w, h)
        short640 = np.minimum(gt[:, 3] - gt[:, 1], gt[:, 4] - gt[:, 2]) * scale
        if not any(int(c) in MISSING and s < a.max_short for c, s in zip(gt[:, 0], short640)):
            continue
        stats["source_images"] += 1
        tw, th = int(w / a.grid * (1 + a.overlap)), int(h / a.grid * (1 + a.overlap))
        xs = np.linspace(0, w - tw, a.grid).astype(int); ys = np.linspace(0, h - th, a.grid).astype(int)
        for r, y0 in enumerate(ys):
            for c, x0 in enumerate(xs):
                ix1 = np.clip(gt[:, 1], x0, x0 + tw); iy1 = np.clip(gt[:, 2], y0, y0 + th)
                ix2 = np.clip(gt[:, 3], x0, x0 + tw); iy2 = np.clip(gt[:, 4], y0, y0 + th)
                inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
                area = (gt[:, 3] - gt[:, 1]) * (gt[:, 4] - gt[:, 2])
                vis = inter / np.maximum(area, 1e-9)
                keep = (vis >= a.min_visible) & ((ix2 - ix1) >= 2) & ((iy2 - iy1) >= 2)
                partial = (vis > 0) & ~keep
                if not keep.any():
                    stats["tiles_skipped_empty"] += 1
                    continue
                name = f"{p.stem}__tile_r{r}c{c}"
                tile = img[y0:y0 + th, x0:x0 + tw]
                cv2.imwrite(str(V2 / "images" / "train" / f"{name}.jpg"), tile, [cv2.IMWRITE_JPEG_QUALITY, 95])
                lines = []
                for k in np.where(keep)[0]:
                    bx1, by1, bx2, by2 = ix1[k] - x0, iy1[k] - y0, ix2[k] - x0, iy2[k] - y0
                    lines.append(f"{int(gt[k, 0])} {(bx1 + bx2) / 2 / tw:.6f} {(by1 + by2) / 2 / th:.6f} {(bx2 - bx1) / tw:.6f} {(by2 - by1) / th:.6f}")
                txt = "\n".join(lines) + "\n"
                (V2 / "labels" / "train" / f"{name}.txt").write_text(txt)
                stats["tiles"] += 1
                stats["boxes_kept"] += int(keep.sum())
                stats["boxes_dropped_partial"] += int(partial.sum())
                for k in np.where(partial)[0]:
                    stats[f"dropped_{NAMES[int(gt[k, 0])]}"] += 1
                rows.append({"tile": f"images/train/{name}.jpg", "source_image": f"images/train/{p.name}", "x0": x0, "y0": y0,
                             "w": tw, "h": th, "boxes_kept": int(keep.sum()), "boxes_dropped_partial": int(partial.sum()),
                             "label_sha256": hashlib.sha256(txt.encode()).hexdigest()})
                if len(sheet_tiles) < 32 and stats["tiles"] % 7 == 1:
                    t = tile.copy()
                    for k in np.where(keep)[0]:
                        col = (0, 0, 255) if int(gt[k, 0]) in MISSING else ((60, 200, 60) if int(gt[k, 0]) == 5 else (255, 160, 0))
                        cv2.rectangle(t, (int(ix1[k] - x0), int(iy1[k] - y0)), (int(ix2[k] - x0), int(iy2[k] - y0)), col, 2)
                    sheet_tiles.append(cv2.resize(t, (400, int(400 * th / tw))[::1] if tw >= th else (int(400 * tw / th), 400)))
    with open(V2 / "tiles_manifest.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader(); wr.writerows(rows)
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(NAMES))
    (V2 / "dev.yaml").write_text(f"# v2: training images + training-derived tiles; dev unchanged; NO locked test\npath: {V2}\ntrain: images/train\nval: images/dev\nnames:\n{names}\n")
    for s in range(0, len(sheet_tiles), 16):
        tiles = [cv2.copyMakeBorder(t, 0, 400 - t.shape[0], 0, 400 - t.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in sheet_tiles[s:s + 16]]
        while len(tiles) < 16:
            tiles.append(np.full((400, 400, 3), 255, np.uint8))
        cv2.imwrite(str(V2 / f"sheet_{s // 16 + 1}.jpg"), np.vstack([np.hstack(tiles[r * 4:(r + 1) * 4]) for r in range(4)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    summary = {"settings": vars(a), **stats, "train_images_total": len(train),
               "train_set_size_v2": len(train) + stats["tiles"]}
    (V2 / "build_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
