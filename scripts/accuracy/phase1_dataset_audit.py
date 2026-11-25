"""Phase 1 full dataset audit (accuracy-improvement specification §3.1). READ-ONLY on the original dataset.

    .venv/bin/python scripts/accuracy/phase1_dataset_audit.py

Re-uses the parsing and geometry helpers of scripts/engineering/dataset_audit.py (REPORT-011), so annotation
row numbers and suspect rules are identical, and adds: annotation IDs, filename families, image-boundary
boxes, pixel-scale resolvability at the 640 inference size, overlap analysis, class co-occurrence,
per-person label completeness, likely-unlabelled-person clusters, all-pairs image similarity (for the
Phase 2 grouping) and a reconciliation of the 148 rule-based suspects with the earlier list.

Annotation ID format: '<split>/<label stem>#L<row>', where row is the 1-based index among the non-empty
lines of the label file (identical to REPORT-011).

Outputs: experiments/accuracy_improvement/data_audit/
  images.csv, annotations.csv, class_stats.csv, cooccurrence_images.csv, person_label_completeness.csv,
  overlap_pairs.csv, unlabelled_person_clusters.csv, similarity_pairs.csv, suspects_rule_based.csv,
  audit_summary.json
Heuristic flags (unresolvable, unlabelled person, similarity) are review aids, not label corrections.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "engineering"))
import dataset_audit as da  # noqa: E402  (REPORT-011 helpers: dhash, phash, hamming_matrix, ioa, iou, PAIRS, NEG)

DATASET = ROOT.parent / "construction-ppe"
OUT = ROOT / "experiments" / "accuracy_improvement" / "data_audit"
NAMES = da.NAMES
PAIRS, NEG = da.PAIRS, da.NEG
INFER = 640
EDGE = 0.002          # a box edge within 0.2 % of the image border counts as touching the boundary
THUMB = 32            # thumbnail side for whole-image similarity


def family(name: str) -> str:
    return "source" if name.startswith("source-") else ("ultralytics-ppe" if name.startswith("ultralytics-ppe-") else "other")


def norm_band(a: float) -> str:
    return "tiny(<0.1%)" if a < 0.001 else "small(0.1-1%)" if a < 0.01 else "medium(1-10%)" if a < 0.10 else "large(>=10%)"


def coco_band(area_px: float) -> str:
    return "S(<32^2)" if area_px < 32 ** 2 else "M(32^2-96^2)" if area_px < 96 ** 2 else "L(>=96^2)"


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0].keys()) if rows else [])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    viewpoint = {}
    vp_csv = ROOT / "data" / "viewpoint_metadata.csv"
    if vp_csv.exists():
        for r in csv.DictReader(open(vp_csv, encoding="utf-8")):
            viewpoint[r["filename"]] = r

    images, boxes, invalid, beyond, empty, unreadable = [], [], [], [], [], []
    thumbs, masks_src = [], []
    pairs_missing = {}
    for split in ("train", "val"):
        img_dir, lbl_dir = DATASET / "images" / split, DATASET / "labels" / split
        imgs = sorted(p for p in img_dir.iterdir() if not p.name.startswith("."))
        lbls = sorted(p for p in lbl_dir.iterdir() if p.suffix == ".txt")
        pairs_missing[f"{split}_images_without_label"] = sorted({p.stem for p in imgs} - {p.stem for p in lbls})
        pairs_missing[f"{split}_labels_without_image"] = sorted({p.stem for p in lbls} - {p.stem for p in imgs})
        for p in imgs:
            img = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if img is None:
                unreadable.append(f"{split}/{p.name}")
                continue
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lbl = lbl_dir / f"{p.stem}.txt"
            lines = [l for l in lbl.read_text().splitlines() if l.strip()] if lbl.exists() else []
            if lbl.exists() and not lines:
                empty.append(f"{split}/{lbl.name}")
            idx = len(images)
            vp = viewpoint.get(p.name, {})
            rec = {"img_idx": idx, "split": split, "file": p.name, "family": family(p.name), "width": w, "height": h,
                   "aspect_w_over_h": round(w / h, 4), "orientation": "landscape" if w / h > 1.05 else "portrait" if w / h < 0.95 else "square",
                   "brightness": round(float(gray.mean()), 1), "viewpoint_ai": vp.get("viewpoint", ""),
                   "image_group_ai": vp.get("image_group", ""), "dhash": da.dhash(gray), "phash": da.phash(gray)}
            img_boxes = []
            for i, line in enumerate(lines, 1):
                parts = line.split()
                try:
                    c = int(parts[0]); xc, yc, bw, bh = map(float, parts[1:])
                    ok = len(parts) == 5 and 0 <= c < 12 and all(0 <= v <= 1 for v in (xc, yc, bw, bh)) and bw > 0 and bh > 0
                except (ValueError, IndexError):
                    ok = False
                if not ok:
                    invalid.append(f"{split}/{lbl.name}:{i}: {line}")
                    continue
                if xc - bw / 2 < -0.001 or xc + bw / 2 > 1.001 or yc - bh / 2 < -0.001 or yc + bh / 2 > 1.001:
                    beyond.append(f"{split}/{p.stem}#L{i}")
                s = INFER / max(w, h)
                b = {"annotation_id": f"{split}/{p.stem}#L{i}", "img_idx": idx, "split": split, "file": p.name,
                     "family": rec["family"], "row": i, "class_id": c, "class_name": NAMES[c],
                     "xc": xc, "yc": yc, "w_norm": bw, "h_norm": bh, "area_norm": bw * bh,
                     "x1": (xc - bw / 2) * w, "y1": (yc - bh / 2) * h, "x2": (xc + bw / 2) * w, "y2": (yc + bh / 2) * h,
                     "w_px": bw * w, "h_px": bh * h, "min_side_px": min(bw * w, bh * h),
                     "w_640": bw * w * s, "h_640": bh * h * s, "min_side_640": min(bw * w, bh * h) * s,
                     "area_640": bw * w * bh * h * s * s}
                b["band_norm"] = norm_band(b["area_norm"])
                b["band_coco_640"] = coco_band(b["area_640"])
                b["touches_boundary"] = int(xc - bw / 2 <= EDGE or yc - bh / 2 <= EDGE or xc + bw / 2 >= 1 - EDGE or yc + bh / 2 >= 1 - EDGE)
                b["lt4px_at_640"] = int(b["min_side_640"] < 4)
                b["lt8px_at_640"] = int(b["min_side_640"] < 8)
                b["lt8px_native"] = int(b["min_side_px"] < 8)
                img_boxes.append(b)
            # person association (same rule as REPORT-011 and the compliance analyser: >= 60 % of the box inside)
            persons = [b for b in img_boxes if b["class_name"] == "Person"]
            for b in img_boxes:
                if b["class_name"] in ("Person", "forklift"):
                    b["persons_containing"] = ""
                    continue
                bx = (b["x1"], b["y1"], b["x2"], b["y2"])
                b["persons_containing"] = sum(1 for pp in persons if da.ioa(bx, (pp["x1"], pp["y1"], pp["x2"], pp["y2"])) >= 0.6)
            rec["n_boxes"] = len(img_boxes)
            rec["n_person"] = len(persons)
            rec["classes"] = " ".join(sorted({b["class_name"] for b in img_boxes}))
            images.append(rec)
            boxes += img_boxes
            # thumbnail for similarity: whole image and a version with labelled boxes masked out
            t = cv2.resize(gray, (THUMB, THUMB), interpolation=cv2.INTER_AREA).astype(np.float32)
            m = np.ones((THUMB, THUMB), dtype=bool)
            for b in img_boxes:
                x1, y1 = int(b["x1"] / w * THUMB), int(b["y1"] / h * THUMB)
                x2, y2 = int(np.ceil(b["x2"] / w * THUMB)), int(np.ceil(b["y2"] / h * THUMB))
                m[max(0, y1):min(THUMB, y2), max(0, x1):min(THUMB, x2)] = False
            thumbs.append(t)
            masks_src.append(m)

    n_img = len(images)
    summary: dict = {"counts": {
        "images": n_img, "annotations": len(boxes), "invalid_rows": len(invalid), "boxes_extending_beyond_image": len(beyond),
        "empty_label_files": len(empty), "unreadable_images": len(unreadable),
        **{k: len(v) for k, v in pairs_missing.items()}}, "invalid_examples": invalid[:10], "beyond_examples": beyond[:10]}

    # ---- image dimensions, orientation, families
    by_split_fam = Counter((r["split"], r["family"]) for r in images)
    summary["families"] = {f"{s}/{f}": n for (s, f), n in sorted(by_split_fam.items())}
    dims = {}
    for key in ("all", "source", "ultralytics-ppe"):
        sel = [r for r in images if key == "all" or r["family"] == key]
        W = np.array([r["width"] for r in sel]); H = np.array([r["height"] for r in sel]); A = W / H
        dims[key] = {"images": len(sel), "width_min_med_max": [int(W.min()), int(np.median(W)), int(W.max())],
                     "height_min_med_max": [int(H.min()), int(np.median(H)), int(H.max())],
                     "aspect_min_med_max": [round(float(A.min()), 3), round(float(np.median(A)), 3), round(float(A.max()), 3)],
                     "orientation": dict(Counter(r["orientation"] for r in sel)),
                     "distinct_sizes": len({(r["width"], r["height"]) for r in sel}),
                     "top_sizes": Counter(f"{r['width']}x{r['height']}" for r in sel).most_common(5),
                     "brightness_median": round(float(np.median([r["brightness"] for r in sel])), 1),
                     "boxes_per_image_median": float(np.median([r["n_boxes"] for r in sel])),
                     "persons_per_image_median": float(np.median([r["n_person"] for r in sel]))}
    summary["image_dimensions"] = dims

    # ---- per-class statistics
    class_rows = []
    for cid, name in NAMES.items():
        for split in ("train", "val", "all"):
            sel = [b for b in boxes if b["class_id"] == cid and (split == "all" or b["split"] == split)]
            imgs_with = len({b["img_idx"] for b in sel})
            if not sel:
                continue
            row = {"class_id": cid, "class_name": name, "split": split, "instances": len(sel), "images_with_class": imgs_with,
                   "median_w_px": round(float(np.median([b["w_px"] for b in sel])), 1),
                   "median_h_px": round(float(np.median([b["h_px"] for b in sel])), 1),
                   "median_min_side_640": round(float(np.median([b["min_side_640"] for b in sel])), 1),
                   "median_area_norm": round(float(np.median([b["area_norm"] for b in sel])), 5),
                   "touches_boundary": sum(b["touches_boundary"] for b in sel),
                   "lt4px_at_640": sum(b["lt4px_at_640"] for b in sel), "lt8px_at_640": sum(b["lt8px_at_640"] for b in sel),
                   "lt8px_native": sum(b["lt8px_native"] for b in sel)}
            for band in ("tiny(<0.1%)", "small(0.1-1%)", "medium(1-10%)", "large(>=10%)"):
                row[band] = sum(1 for b in sel if b["band_norm"] == band)
            for band in ("S(<32^2)", "M(32^2-96^2)", "L(>=96^2)"):
                row["coco640_" + band] = sum(1 for b in sel if b["band_coco_640"] == band)
            if name not in ("Person", "forklift"):
                row["no_person_containing"] = sum(1 for b in sel if b["persons_containing"] == 0)
                row["multiple_persons_containing"] = sum(1 for b in sel if b["persons_containing"] >= 2)
            class_rows.append(row)
    write_csv(OUT / "class_stats.csv", class_rows, list(dict.fromkeys(k for r in class_rows for k in r)))

    # ---- class co-occurrence (image level)
    pres = np.zeros((n_img, 12), dtype=np.int32)
    for b in boxes:
        pres[b["img_idx"], b["class_id"]] = 1
    co = pres.T @ pres
    write_csv(OUT / "cooccurrence_images.csv",
              [{"class": NAMES[i], **{NAMES[j]: int(co[i, j]) for j in range(12)}} for i in range(12)])

    # ---- per-person label completeness (items with >= 60 % of their area inside the Person box)
    by_img = defaultdict(list)
    for b in boxes:
        by_img[b["img_idx"]].append(b)
    comp = {item: Counter() for item in PAIRS}
    for idx, bl in by_img.items():
        for p in (b for b in bl if b["class_name"] == "Person"):
            pb = (p["x1"], p["y1"], p["x2"], p["y2"])
            for item, neg in PAIRS.items():
                pos_in = any(da.ioa((b["x1"], b["y1"], b["x2"], b["y2"]), pb) >= 0.6 for b in bl if b["class_name"] == item)
                neg_in = any(da.ioa((b["x1"], b["y1"], b["x2"], b["y2"]), pb) >= 0.6 for b in bl if b["class_name"] == neg)
                comp[item]["both" if pos_in and neg_in else "positive_only" if pos_in else "missing_only" if neg_in else "neither"] += 1
    n_person = sum(1 for b in boxes if b["class_name"] == "Person")
    comp_rows = [{"item": item, "persons": n_person, **{k: comp[item][k] for k in ("positive_only", "missing_only", "both", "neither")},
                  "neither_share": round(comp[item]["neither"] / n_person, 3)} for item in PAIRS]
    write_csv(OUT / "person_label_completeness.csv", comp_rows)

    # ---- overlaps
    overlap_rows, overlap_counts = [], Counter()
    for idx, bl in by_img.items():
        for i, a in enumerate(bl):
            ab = (a["x1"], a["y1"], a["x2"], a["y2"])
            for b in bl[i + 1:]:
                v = da.iou(ab, (b["x1"], b["y1"], b["x2"], b["y2"]))
                if v < 0.5:
                    continue
                if a["class_id"] == b["class_id"]:
                    kind = "same_class_duplicate" if v >= 0.8 else ("person_person_overlap" if a["class_name"] == "Person" else "same_class_overlap")
                elif PAIRS.get(a["class_name"]) == b["class_name"] or PAIRS.get(b["class_name"]) == a["class_name"]:
                    kind = "item_vs_missing_item"
                else:
                    kind = "cross_class:" + "|".join(sorted((a["class_name"], b["class_name"])))
                overlap_counts[kind] += 1
                overlap_rows.append({"kind": kind, "iou": round(v, 3), "annotation_a": a["annotation_id"], "class_a": a["class_name"],
                                     "annotation_b": b["annotation_id"], "class_b": b["class_name"]})
    write_csv(OUT / "overlap_pairs.csv", overlap_rows, ["kind", "iou", "annotation_a", "class_a", "annotation_b", "class_b"])
    summary["overlaps_iou_ge_0.5"] = dict(overlap_counts.most_common())

    # ---- likely unlabelled persons: clusters of >= 2 orphan PPE / missing-PPE boxes covering >= 2 body regions
    region = {"helmet": "head", "no_helmet": "head", "goggles": "eyes", "no_goggle": "eyes", "vest": "torso", "no_vest": "torso",
              "gloves": "hands", "no_gloves": "hands", "boots": "feet", "no_boots": "feet"}
    cluster_rows = []
    for idx, bl in by_img.items():
        orphans = [b for b in bl if b["class_name"] in region and b["persons_containing"] == 0]
        parent = list(range(len(orphans)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i, a in enumerate(orphans):
            for j in range(i + 1, len(orphans)):
                b = orphans[j]
                # expand each box by 1.5x its larger side; join when expanded boxes intersect
                ea = max(a["w_px"], a["h_px"]) * 1.5
                eb = max(b["w_px"], b["h_px"]) * 1.5
                if (a["x1"] - ea < b["x2"] + eb and b["x1"] - eb < a["x2"] + ea and a["y1"] - ea < b["y2"] + eb and b["y1"] - eb < a["y2"] + ea):
                    parent[find(i)] = find(j)
        groups = defaultdict(list)
        for i, o in enumerate(orphans):
            groups[find(i)].append(o)
        for g in groups.values():
            regions = {region[o["class_name"]] for o in g}
            if len(g) >= 2 and len(regions) >= 2:
                cluster_rows.append({"image": f"{g[0]['split']}/{g[0]['file']}", "boxes": len(g), "regions": " ".join(sorted(regions)),
                                     "annotation_ids": " ".join(o["annotation_id"] for o in g),
                                     "classes": " ".join(o["class_name"] for o in g)})
    write_csv(OUT / "unlabelled_person_clusters.csv", cluster_rows, ["image", "boxes", "regions", "annotation_ids", "classes"])
    items_no_person_imgs = sum(1 for idx, bl in by_img.items() if not any(b["class_name"] == "Person" for b in bl)
                               and any(b["class_name"] in region for b in bl))
    summary["person_annotation_gaps"] = {"likely_unlabelled_person_clusters": len(cluster_rows),
                                         "images_with_such_clusters": len({r["image"] for r in cluster_rows}),
                                         "images_with_ppe_items_but_no_person_box": items_no_person_imgs}

    # ---- all-pairs image similarity (for Phase 2 grouping)
    ham_d = da.hamming_matrix([r["dhash"] for r in images])
    ham_p = da.hamming_matrix([r["phash"] for r in images])
    T = np.stack([t.flatten() for t in thumbs])
    Tn = (T - T.mean(1, keepdims=True)) / (T.std(1, keepdims=True) + 1e-6)
    corr = (Tn @ Tn.T) / Tn.shape[1]
    sim_rows = []
    iu = np.triu_indices(n_img, 1)
    cand = np.where((ham_d[iu] <= 10) | (ham_p[iu] <= 10) | (corr[iu] >= 0.85))[0]
    for k in cand:
        i, j = int(iu[0][k]), int(iu[1][k])
        m = masks_src[i] & masks_src[j]
        if m.sum() >= 50:
            a, b = thumbs[i][m], thumbs[j][m]
            mc = float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-3 and b.std() > 1e-3 else 0.0
        else:
            mc = float("nan")
        sim_rows.append({"image_a": f"{images[i]['split']}/{images[i]['file']}", "image_b": f"{images[j]['split']}/{images[j]['file']}",
                         "split_pair": "-".join(sorted((images[i]["split"], images[j]["split"]))),
                         "family_pair": "-".join(sorted((images[i]["family"], images[j]["family"]))),
                         "dhash_hamming": int(ham_d[i, j]), "phash_hamming": int(ham_p[i, j]),
                         "thumb_corr": round(float(corr[i, j]), 4), "background_masked_corr": round(mc, 4),
                         "masked_pixels": int(m.sum()),
                         "same_size": int(images[i]["width"] == images[j]["width"] and images[i]["height"] == images[j]["height"])})
    write_csv(OUT / "similarity_pairs.csv", sim_rows)
    sim_summary = Counter()
    for r in sim_rows:
        sp = r["split_pair"]
        if r["dhash_hamming"] <= 5:
            sim_summary[f"{sp}: dhash<=5"] += 1
        if r["phash_hamming"] <= 8:
            sim_summary[f"{sp}: phash<=8"] += 1
        if r["thumb_corr"] >= 0.95:
            sim_summary[f"{sp}: thumb_corr>=0.95"] += 1
        if r["background_masked_corr"] == r["background_masked_corr"] and r["background_masked_corr"] >= 0.85:
            sim_summary[f"{sp}: background_masked_corr>=0.85"] += 1
    summary["similarity"] = {"candidate_pairs": len(sim_rows), "counts": dict(sorted(sim_summary.items()))}

    # ---- rule-based suspects: same rules as REPORT-011, now with annotation IDs; reconcile with the earlier list
    suspects = []
    for idx, bl in by_img.items():
        persons = [b for b in bl if b["class_name"] == "Person"]
        pbs = [(p["x1"], p["y1"], p["x2"], p["y2"]) for p in persons]
        for b in bl:
            bx = (b["x1"], b["y1"], b["x2"], b["y2"])
            name = b["class_name"]
            if name in PAIRS or name in NEG:
                inside = [k for k, p in enumerate(pbs) if da.ioa(bx, p) >= 0.6]
                if not inside and name in NEG:
                    suspects.append((b, "missing_ppe_without_person", "high"))
                elif not inside:
                    suspects.append((b, "ppe_without_person", "low"))
            if name in ("helmet", "no_helmet", "goggles", "no_goggle", "gloves", "no_gloves", "boots", "no_boots"):
                asp = b["w_px"] / b["h_px"]
                if asp > 4 or asp < 0.2:
                    suspects.append((b, "extreme_aspect", "medium"))
            if name not in ("Person", "forklift"):
                inside = [p for p in pbs if da.ioa(bx, p) >= 0.6]
                if inside and all((b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) > 0.9 * (p[2] - p[0]) * (p[3] - p[1]) for p in inside):
                    suspects.append((b, "item_as_large_as_person", "medium"))
    old = list(csv.DictReader(open(ROOT / "experiments/dataset_audit/suspect_annotations.csv", encoding="utf-8")))
    old_rule = [r for r in old if not r["issue_type"].startswith("visual_review")]
    old_keys = Counter((r["image_path"], int(r["class_id"]), round(float(r["bbox_x"]), 4), round(float(r["bbox_y"]), 4), r["issue_type"]) for r in old_rule)
    rows, matched = [], 0
    for b, issue, prio in suspects:
        key = (f"images/{b['split']}/{b['file']}", b["class_id"], round(b["xc"], 4), round(b["yc"], 4), issue)
        hit = old_keys[key] > 0
        if hit:
            old_keys[key] -= 1
            matched += 1
        rows.append({"annotation_id": b["annotation_id"], "image_path": f"images/{b['split']}/{b['file']}",
                     "label_file": f"labels/{b['split']}/{Path(b['file']).stem}.txt", "row": b["row"], "split": b["split"],
                     "class_id": b["class_id"], "class_name": b["class_name"], "xc": b["xc"], "yc": b["yc"], "w": b["w_norm"],
                     "h": b["h_norm"], "x1_px": round(b["x1"], 1), "y1_px": round(b["y1"], 1), "x2_px": round(b["x2"], 1),
                     "y2_px": round(b["y2"], 1), "min_side_640": round(b["min_side_640"], 1), "issue_type": issue,
                     "priority": prio, "in_earlier_list": int(hit)})
    write_csv(OUT / "suspects_rule_based.csv", rows)
    summary["suspect_reconciliation"] = {"rule_based_rederived": len(rows), "earlier_rule_based_rows": len(old_rule),
                                         "matched_to_earlier": matched, "earlier_unmatched": sum(old_keys.values()),
                                         "by_issue": dict(Counter(f"{r['issue_type']}/{r['priority']}" for r in rows))}

    # ---- totals for resolvability and boundaries
    summary["resolvability"] = {"boxes_min_side_lt4px_at_640": sum(b["lt4px_at_640"] for b in boxes),
                                "boxes_min_side_lt8px_at_640": sum(b["lt8px_at_640"] for b in boxes),
                                "boxes_min_side_lt8px_native": sum(b["lt8px_native"] for b in boxes),
                                "boxes_touching_boundary": sum(b["touches_boundary"] for b in boxes)}
    vp_counts = Counter((r["split"], r["viewpoint_ai"] or "unlabelled") for r in images)
    grp_counts = Counter((r["split"], r["image_group_ai"] or "unlabelled") for r in images)
    summary["viewpoint_ai_assisted"] = {"method": sorted({v.get("labelling_method", "") for v in viewpoint.values()}),
                                        "viewpoint": {f"{s}/{v}": n for (s, v), n in sorted(vp_counts.items())},
                                        "image_group": {f"{s}/{v}": n for (s, v), n in sorted(grp_counts.items())}}
    fam_class = Counter((b["family"], b["class_name"]) for b in boxes)
    summary["instances_by_family"] = {f: {NAMES[c]: fam_class[(f, NAMES[c])] for c in range(12)} for f in ("source", "ultralytics-ppe")}

    write_csv(OUT / "images.csv", [{k: v for k, v in r.items() if k not in ("dhash", "phash")} for r in images])
    write_csv(OUT / "annotations.csv", [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in b.items()} for b in boxes])
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("counts", "families", "overlaps_iou_ge_0.5", "person_annotation_gaps",
                                              "similarity", "suspect_reconciliation", "resolvability")}, indent=1, default=str))


if __name__ == "__main__":
    main()
