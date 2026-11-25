"""Dataset quality and annotation audit (spec §6). READ-ONLY on the original dataset.

    .venv/bin/python scripts/engineering/dataset_audit.py

Outputs (experiments/dataset_audit/):
  inventory.json                    structural validation + image dimension statistics
  image_dimensions.csv              per image: split, width, height, aspect, bytes
  class_distribution.csv            per class: train/val instances, share, images containing class, box-area stats
  box_scale_by_class.csv            per class x size category (normalised area thresholds below) x split
  boxes.csv                         every annotation with normalised and pixel geometry
  duplicates_exact.csv              identical SHA-256 groups
  near_duplicates.csv               perceptual-hash pairs (dHash + pHash, 64-bit) with Hamming distances
  suspect_annotations.csv           rule-based review list (spec §6.6 columns); never auto-corrected
  viewpoint_summary.json            counts from data/viewpoint_metadata.csv (AI-assisted labels)
  charts/*.png                      class distribution, size categories, image sizes
  review_sheets/*.jpg               GT boxes drawn on systematically sampled images
Size categories (project audit thresholds, not universal standards):
  small  : normalised box area <  0.01  (box covers < 1 % of the image)
  medium : 0.01 <= area < 0.10
  large  : area >= 0.10
  ('tiny' < 0.001 is reported as a sub-count of small)
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.paths import VIEWPOINT_CSV, class_names, source_dataset_dir  # noqa: E402

OUT = ROOT / "experiments" / "dataset_audit"
NAMES = class_names()
ID = {v: k for k, v in NAMES.items()}
PAIRS = {"helmet": "no_helmet", "vest": "no_vest", "gloves": "no_gloves", "boots": "no_boots", "goggles": "no_goggle"}
NEG = {v: k for k, v in PAIRS.items()}


def size_cat(area: float) -> str:
    return "small" if area < 0.01 else ("medium" if area < 0.10 else "large")


def dhash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def phash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(small)[:8, :8]
    bits = (d > np.median(d[1:, 1:] if False else d)).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming_matrix(hashes: list[int]) -> np.ndarray:
    a = np.array(hashes, dtype=np.uint64)
    x = a[:, None] ^ a[None, :]
    # popcount for uint64
    x = x - ((x >> np.uint64(1)) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> np.uint64(2)) & np.uint64(0x3333333333333333))
    x = (x + (x >> np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return ((x * np.uint64(0x0101010101010101)) >> np.uint64(56)).astype(np.int32)


def ioa(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))
    return ix / area


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix
    return ix / u if u > 0 else 0.0


def main() -> None:
    root = source_dataset_dir()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "charts").mkdir(exist_ok=True)
    (OUT / "review_sheets").mkdir(exist_ok=True)
    inv = Counter()
    images, boxes, dims = [], [], []
    invalid_rows, unreadable, empty_labels = [], [], []
    names_seen = Counter()
    for split in ("train", "val"):
        img_dir, lbl_dir = root / "images" / split, root / "labels" / split
        imgs = sorted(p for p in img_dir.iterdir() if not p.name.startswith("."))
        lbls = sorted(p for p in lbl_dir.iterdir() if p.suffix == ".txt")
        inv[f"{split}_images"], inv[f"{split}_labels"] = len(imgs), len(lbls)
        inv[f"{split}_images_without_label"] = len({p.stem for p in imgs} - {p.stem for p in lbls})
        inv[f"{split}_labels_without_image"] = len({p.stem for p in lbls} - {p.stem for p in imgs})
        for p in imgs:
            names_seen[p.name] += 1
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                inv["unsupported_extension"] += 1
            data = p.read_bytes()
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                unreadable.append(f"{split}/{p.name}")
                continue
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rec = {"split": split, "file": p.name, "path": f"images/{split}/{p.name}", "w": w, "h": h, "bytes": len(data),
                   "sha256": hashlib.sha256(data).hexdigest(), "dhash": dhash(gray), "phash": phash(gray),
                   "brightness": float(gray.mean())}
            images.append(rec)
            dims.append(rec)
            lbl = lbl_dir / f"{p.stem}.txt"
            lines = [l for l in lbl.read_text().splitlines() if l.strip()] if lbl.exists() else []
            if lbl.exists() and not lines:
                empty_labels.append(f"{split}/{lbl.name}")
            for i, line in enumerate(lines, 1):
                parts = line.split()
                ok = len(parts) == 5
                try:
                    c = int(parts[0]); xc, yc, bw, bh = map(float, parts[1:])
                except (ValueError, IndexError):
                    ok = False
                if not ok or not (0 <= c < 12) or not all(0 <= v <= 1 for v in (xc, yc, bw, bh)) or bw <= 0 or bh <= 0:
                    invalid_rows.append(f"{split}/{lbl.name}:{i}: {line}")
                    continue
                boxes.append({"split": split, "file": p.name, "row": i, "class_id": c, "class_name": NAMES[c],
                              "xc": xc, "yc": yc, "w_norm": bw, "h_norm": bh, "area_norm": bw * bh,
                              "w_px": bw * w, "h_px": bh * h, "area_px": bw * w * bh * h,
                              "aspect_w_over_h": (bw * w) / (bh * h), "size_cat": size_cat(bw * bh),
                              "x1": (xc - bw / 2) * w, "y1": (yc - bh / 2) * h, "x2": (xc + bw / 2) * w, "y2": (yc + bh / 2) * h})
    inv["total_annotations"] = len(boxes)
    inv["invalid_rows"] = len(invalid_rows)
    inv["unreadable_images"] = len(unreadable)
    inv["empty_label_files"] = len(empty_labels)
    inv["duplicate_filenames_across_splits"] = sum(1 for v in names_seen.values() if v > 1)
    inv["class_ids_present"] = sorted({b["class_id"] for b in boxes})
    W = np.array([d["w"] for d in dims]); H = np.array([d["h"] for d in dims]); A = W / H
    dim_stats = {k: {"min": float(v.min()), "max": float(v.max()), "mean": round(float(v.mean()), 1), "median": float(np.median(v))}
                 for k, v in (("width", W), ("height", H), ("aspect_w_over_h", A))}
    orient = Counter("landscape" if a > 1.05 else ("portrait" if a < 0.95 else "square") for a in A)
    size_combos = Counter(f"{d['w']}x{d['h']}" for d in dims)
    inventory = {"counts": dict(inv), "image_dimensions": dim_stats, "orientation": dict(orient),
                 "most_common_sizes": size_combos.most_common(10), "invalid_row_examples": invalid_rows[:20],
                 "unreadable": unreadable, "empty_labels": empty_labels[:20]}
    (OUT / "inventory.json").write_text(json.dumps(inventory, indent=2))
    with open(OUT / "image_dimensions.csv", "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["split", "file", "width", "height", "aspect_w_over_h", "bytes", "mean_brightness"])
        for d in dims:
            wr.writerow([d["split"], d["file"], d["w"], d["h"], round(d["w"] / d["h"], 4), d["bytes"], round(d["brightness"], 1)])
    with open(OUT / "boxes.csv", "w", newline="") as f:
        keys = ["split", "file", "row", "class_id", "class_name", "xc", "yc", "w_norm", "h_norm", "area_norm", "w_px", "h_px",
                "area_px", "aspect_w_over_h", "size_cat"]
        wr = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); wr.writeheader()
        for b in boxes:
            wr.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in b.items()})

    # ---------------- class distribution and scale
    rows = []
    for c, n in NAMES.items():
        cb = [b for b in boxes if b["class_id"] == c]
        areas = np.array([b["area_norm"] for b in cb]); px = np.array([b["area_px"] for b in cb])
        rows.append({"class_id": c, "class_name": n,
                     "train_instances": sum(b["split"] == "train" for b in cb), "val_instances": sum(b["split"] == "val" for b in cb),
                     "share_of_annotations_pct": round(100 * len(cb) / len(boxes), 2),
                     "train_images_with_class": len({b["file"] for b in cb if b["split"] == "train"}),
                     "val_images_with_class": len({b["file"] for b in cb if b["split"] == "val"}),
                     "area_norm_mean": round(float(areas.mean()), 5), "area_norm_median": round(float(np.median(areas)), 5),
                     "area_norm_min": round(float(areas.min()), 6), "area_norm_max": round(float(areas.max()), 4),
                     "area_px_median": round(float(np.median(px)), 1),
                     "small_pct": round(100 * float((areas < 0.01).mean()), 1), "tiny_lt_0.001_pct": round(100 * float((areas < 0.001).mean()), 1),
                     "medium_pct": round(100 * float(((areas >= 0.01) & (areas < 0.1)).mean()), 1), "large_pct": round(100 * float((areas >= 0.1).mean()), 1)})
    with open(OUT / "class_distribution.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    with open(OUT / "box_scale_by_class.csv", "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["class_name", "split", "small", "tiny_lt_0.001", "medium", "large", "total"])
        for c, n in NAMES.items():
            for split in ("train", "val"):
                cb = [b for b in boxes if b["class_id"] == c and b["split"] == split]
                cnt = Counter(b["size_cat"] for b in cb)
                wr.writerow([n, split, cnt["small"], sum(b["area_norm"] < 0.001 for b in cb), cnt["medium"], cnt["large"], len(cb)])

    # ---------------- duplicates and leakage
    by_sha = defaultdict(list)
    for d in images:
        by_sha[d["sha256"]].append(d)
    exact = [g for g in by_sha.values() if len(g) > 1]
    with open(OUT / "duplicates_exact.csv", "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["group", "path", "split", "sha256", "review_status"])
        for gi, g in enumerate(exact):
            for d in g:
                wr.writerow([gi, d["path"], d["split"], d["sha256"], "not reviewed"])
    dm = hamming_matrix([d["dhash"] for d in images]); pm = hamming_matrix([d["phash"] for d in images])
    pairs = []
    n = len(images)
    iu = np.triu_indices(n, 1)
    sel = (dm[iu] <= 10) | (pm[iu] <= 10)
    for i, j in zip(iu[0][sel], iu[1][sel]):
        a, b = images[i], images[j]
        pairs.append({"path_a": a["path"], "split_a": a["split"], "path_b": b["path"], "split_b": b["split"],
                      "dhash_distance": int(dm[i, j]), "phash_distance": int(pm[i, j]),
                      "cross_split": a["split"] != b["split"],
                      "category": "near-duplicate" if (dm[i, j] <= 5 and pm[i, j] <= 8) else "similar"})
    pairs.sort(key=lambda r: (r["dhash_distance"] + r["phash_distance"]))
    with open(OUT / "near_duplicates.csv", "w", newline="") as f:
        keys = ["path_a", "split_a", "path_b", "split_b", "dhash_distance", "phash_distance", "cross_split", "category", "review_status"]
        wr = csv.DictWriter(f, fieldnames=keys); wr.writeheader()
        for r in pairs:
            wr.writerow({**r, "review_status": "pending visual review"})
    dist_hist = {"dhash_min_nonself": int(np.sort(dm + np.eye(n, dtype=np.int32) * 999, axis=1)[:, 0].min()),
                 "pairs_dhash_le5": int((dm[iu] <= 5).sum()), "pairs_dhash_le10": int((dm[iu] <= 10).sum()),
                 "pairs_phash_le8": int((pm[iu] <= 8).sum()), "pairs_phash_le10": int((pm[iu] <= 10).sum())}

    # ---------------- rule-based suspect annotations (review list, never auto-corrected)
    suspects = []
    by_img = defaultdict(list)
    for b in boxes:
        by_img[(b["split"], b["file"])].append(b)
    img_dim = {(d["split"], d["file"]): (d["w"], d["h"]) for d in images}

    def add(b, issue, reason, prio):
        suspects.append({"image_path": f"images/{b['split']}/{b['file']}", "split": b["split"], "class_id": b["class_id"],
                         "class_name": b["class_name"], "bbox_x": round(b["xc"], 6), "bbox_y": round(b["yc"], 6),
                         "bbox_width": round(b["w_norm"], 6), "bbox_height": round(b["h_norm"], 6), "issue_type": issue,
                         "reason": reason, "review_priority": prio, "reviewer_status": "unreviewed", "notes": ""})

    for key, bl in by_img.items():
        persons = [b for b in bl if b["class_name"] == "Person"]
        pb = [(b["x1"], b["y1"], b["x2"], b["y2"]) for b in persons]
        for b in bl:
            bx = (b["x1"], b["y1"], b["x2"], b["y2"])
            name = b["class_name"]
            if name in PAIRS or name in NEG:
                inside = [k for k, p in enumerate(pb) if ioa(bx, p) >= 0.6]
                if not inside and name in NEG:
                    add(b, "missing_ppe_without_person", "missing-PPE box not inside any Person box (>=60% overlap)", "high")
                elif not inside:
                    add(b, "ppe_without_person", "PPE box not inside any Person box; may be an unworn item or an unlabelled person", "low")
            for o in bl:
                if o is b or o["row"] < b["row"]:
                    continue
                ob = (o["x1"], o["y1"], o["x2"], o["y2"])
                if o["class_id"] == b["class_id"] and iou(bx, ob) >= 0.8:
                    add(b, "duplicate_box", f"same class box row {o['row']} overlaps IoU {iou(bx, ob):.2f}", "high")
                pair = PAIRS.get(b["class_name"]) == o["class_name"] or PAIRS.get(o["class_name"]) == b["class_name"]
                if pair and iou(bx, ob) >= 0.5 and b["class_name"] not in ("gloves", "no_gloves", "boots", "no_boots"):
                    add(b, "contradictory_pair", f"overlaps its opposite class '{o['class_name']}' (row {o['row']}, IoU {iou(bx, ob):.2f})", "high")
            if name in ("helmet", "no_helmet", "goggles", "no_goggle", "gloves", "no_gloves", "boots", "no_boots"):
                if b["aspect_w_over_h"] > 4 or b["aspect_w_over_h"] < 0.2:
                    add(b, "extreme_aspect", f"aspect w/h {b['aspect_w_over_h']:.2f} unusual for {name}", "medium")
            if name != "Person" and name != "forklift":
                inside = [p for p in pb if ioa(bx, p) >= 0.6]
                if inside and all((b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) > 0.9 * (p[2] - p[0]) * (p[3] - p[1]) for p in inside):
                    add(b, "item_as_large_as_person", "item box is >= 90% of the area of its person box", "medium")
        # same person carries both helmet and no_helmet (or vest/no_vest, goggles/no_goggle)
        for p in persons:
            pbx = (p["x1"], p["y1"], p["x2"], p["y2"])
            for item in ("helmet", "vest", "goggles"):
                has_pos = [b for b in bl if b["class_name"] == item and ioa((b["x1"], b["y1"], b["x2"], b["y2"]), pbx) >= 0.6]
                has_neg = [b for b in bl if b["class_name"] == PAIRS[item] and ioa((b["x1"], b["y1"], b["x2"], b["y2"]), pbx) >= 0.6]
                if has_pos and has_neg and len(persons) == 1:
                    add(has_neg[0], "item_and_missing_item_on_same_person",
                        f"single person carries both '{item}' and '{PAIRS[item]}'", "high")
    # de-duplicate identical suspect rows
    seen, uniq = set(), []
    for s_ in suspects:
        k = (s_["image_path"], s_["class_id"], s_["bbox_x"], s_["bbox_y"], s_["issue_type"])
        if k not in seen:
            seen.add(k); uniq.append(s_)
    with open(OUT / "suspect_annotations.csv", "w", newline="") as f:
        keys = ["image_path", "split", "class_id", "class_name", "bbox_x", "bbox_y", "bbox_width", "bbox_height", "issue_type",
                "reason", "review_priority", "reviewer_status", "notes"]
        wr = csv.DictWriter(f, fieldnames=keys); wr.writeheader(); wr.writerows(uniq)

    # ---------------- viewpoint metadata
    vp = {}
    if VIEWPOINT_CSV.exists():
        vrows = list(csv.DictReader(open(VIEWPOINT_CSV)))
        vp = {"source": str(VIEWPOINT_CSV.relative_to(ROOT)), "images": len(vrows),
              "labelling_method": sorted({r["labelling_method"] for r in vrows}),
              "reliability": "AI-assisted thumbnail judgements (REPORT-003); NOT independently human-verified",
              "by_viewpoint": dict(Counter(r["viewpoint"] for r in vrows)),
              "by_viewpoint_and_split": {f"{v}|{s}": c for (v, s), c in Counter((r["viewpoint"], r["source_split"]) for r in vrows).items()},
              "by_viewpoint_and_group": {f"{v}|{g}": c for (v, g), c in Counter((r["viewpoint"], r["image_group"]) for r in vrows).items()}}
    (OUT / "viewpoint_summary.json").write_text(json.dumps(vp, indent=2))

    # ---------------- charts
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r["class_name"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = np.arange(len(names))
    ax.bar(x - 0.2, [r["train_instances"] for r in rows], 0.4, label="train", color="#5B6573")
    ax.bar(x + 0.2, [r["val_instances"] for r in rows], 0.4, label="val", color="#D9622B")
    ax.set_xticks(x, names, rotation=35, ha="right"); ax.set_ylabel("instances"); ax.set_title("Instances per class"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "charts/class_distribution.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sm = np.array([r["small_pct"] for r in rows]); md = np.array([r["medium_pct"] for r in rows]); lg = np.array([r["large_pct"] for r in rows])
    ax.bar(names, sm, label="small (<0.01)", color="#D9622B"); ax.bar(names, md, bottom=sm, label="medium", color="#9AA3AE")
    ax.bar(names, lg, bottom=sm + md, label="large (>=0.10)", color="#5B6573")
    ax.set_ylabel("% of boxes"); ax.set_title("Box size category per class (normalised area)"); ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right"); fig.tight_layout(); fig.savefig(OUT / "charts/box_size_categories.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(W, H, s=8, alpha=0.5, color="#5B6573"); ax.set_xlabel("width px"); ax.set_ylabel("height px"); ax.set_title("Image sizes")
    fig.tight_layout(); fig.savefig(OUT / "charts/image_sizes.png", dpi=120); plt.close(fig)

    summary = {"inventory": inventory["counts"], "dimension_stats": dim_stats, "orientation": dict(orient),
               "exact_duplicate_groups": len(exact), "perceptual_hash_pairs": dist_hist,
               "near_duplicate_pairs": sum(p["category"] == "near-duplicate" for p in pairs),
               "near_duplicate_cross_split": sum(p["category"] == "near-duplicate" and p["cross_split"] for p in pairs),
               "similar_pairs": sum(p["category"] == "similar" for p in pairs),
               "suspects": dict(Counter(s_["issue_type"] for s_ in uniq)),
               "suspects_by_priority": dict(Counter(s_["review_priority"] for s_ in uniq))}
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
