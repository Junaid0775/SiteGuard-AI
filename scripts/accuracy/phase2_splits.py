"""Phase 2: leakage-resistant grouping and the train / dev / locked-test split (specification §4).

    .venv/bin/python scripts/accuracy/phase2_splits.py analyse
    .venv/bin/python scripts/accuracy/phase2_splits.py build --emb-threshold <T> [--test-images 160] [--seed 0]

analyse
  * image embeddings from the COCO-pretrained YOLO26n backbone (models/pretrained/yolo26n.pt, Ultralytics
    YOLO.embed, imgsz 320); cosine similarity for all 499,500 pairs
  * filename-sequence test: are consecutive 'ultralytics-ppe-nov2026-NNN' images more similar than random pairs?
  * contact sheet of the most similar pairs for a manual check (splits/analysis/top_pairs_*.jpg)
build
  * groups = union-find over: pixel near-duplicates from Phase 1 (dHash <= 5, or background-masked
    correlation >= 0.85) and embedding cosine similarity >= T (T chosen from the manual check)
  * dev = the original 200-image val split (already used repeatedly; development data only)
  * locked test = whole groups drawn ONLY from original-train images that share no group with dev,
    chosen by a seeded random search that keeps every class's instance and image share, both filename
    families and the small-object share of each missing-PPE class close to the target fraction.
    Only label statistics are used; no model output is used.
  * train = the remaining original-train images
  * writes split lists, assignments, statistics, leakage checks and SHA-256 hashes, and builds the derived
    dataset experiments/accuracy_improvement/datasets/v1_original_labels/ (symlinks to the ORIGINAL images
    and labels; nothing is copied or changed) with dev.yaml (training/development) and a separate
    locked_test.yaml that no training command references.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import src.utils.paths  # noqa: E402,F401  (project Ultralytics config dir)

DATASET = ROOT.parent / "construction-ppe"
AUDIT = ROOT / "experiments" / "accuracy_improvement" / "data_audit"
OUT = ROOT / "experiments" / "accuracy_improvement" / "splits"
DSROOT = ROOT / "experiments" / "accuracy_improvement" / "datasets" / "v1_original_labels"
NAMES = {0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles", 5: "Person", 6: "no_helmet", 7: "no_goggle",
         8: "no_gloves", 9: "no_boots", 10: "forklift", 11: "no_vest"}
MISSING = ["no_helmet", "no_goggle", "no_gloves", "no_boots", "no_vest"]
PERIOD = 50


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_images() -> list[dict]:
    return list(csv.DictReader(open(AUDIT / "images.csv", encoding="utf-8")))


def embeddings(images: list[dict]) -> np.ndarray:
    """Raw backbone embeddings of each image resized (stretched) to 320x320, so that letterbox padding of
    different aspect ratios cannot dominate the similarity; returned mean-centred and L2-normalised."""
    path = OUT / "analysis" / "embeddings_yolo26n_coco_320_square_raw.npy"
    if path.exists():
        E = np.load(path)
    else:
        from ultralytics import YOLO
        model = YOLO(str(ROOT / "models" / "pretrained" / "yolo26n.pt"))
        vecs = []
        for r in images:
            img = cv2.imread(str(DATASET / "images" / r["split"] / r["file"]))
            img = cv2.resize(img, (320, 320), interpolation=cv2.INTER_AREA)
            e = model.embed(img, imgsz=320, device="mps", verbose=False)[0]
            vecs.append(e.detach().cpu().numpy().astype(np.float32).ravel())
        E = np.stack(vecs)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, E)
    E = E - E.mean(0, keepdims=True)
    return E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)


def thumb(r: dict, h: int = 200) -> np.ndarray:
    img = cv2.imread(str(DATASET / "images" / r["split"] / r["file"]))
    s = h / img.shape[0]
    t = cv2.resize(img, (int(img.shape[1] * s), h), interpolation=cv2.INTER_AREA)
    return t[:, :300] if t.shape[1] > 300 else cv2.copyMakeBorder(t, 0, 0, 0, 300 - t.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))


def analyse() -> None:
    images = load_images()
    E = embeddings(images)
    S = E @ E.T
    n = len(images)
    iu = np.triu_indices(n, 1)
    sims = S[iu]
    order = np.argsort(-sims)
    pct = {f"p{q}": round(float(np.percentile(sims, q)), 4) for q in (50, 90, 99, 99.9, 99.99)}
    top1 = np.sort(S - np.eye(n) * 2, axis=1)[:, -1]
    # filename-sequence test for the ultralytics-ppe family
    seq = {}
    for i, r in enumerate(images):
        m = re.match(r"ultralytics-ppe-nov2026-(\d+)\.jpg", r["file"])
        if m:
            seq[int(m.group(1))] = i
    nums = sorted(seq)
    rng = np.random.default_rng(0)
    seq_stats = {}
    for d in (1, 2, 5, 10, 50):
        v = [S[seq[a], seq[a + d]] for a in nums if a + d in seq]
        seq_stats[f"delta_{d}"] = {"pairs": len(v), "mean_cos": round(float(np.mean(v)), 4), "p90": round(float(np.percentile(v, 90)), 4)}
    idx = list(seq.values())
    rnd = [S[a, b] for a, b in zip(rng.choice(idx, 5000), rng.choice(idx, 5000)) if a != b]
    seq_stats["random_pairs_same_family"] = {"pairs": len(rnd), "mean_cos": round(float(np.mean(rnd)), 4), "p90": round(float(np.percentile(rnd, 90)), 4)}
    # top pairs, contact sheets of 12 pairs each (rank order)
    (OUT / "analysis").mkdir(parents=True, exist_ok=True)
    rows = []
    for k in order[:60]:
        i, j = int(iu[0][k]), int(iu[1][k])
        rows.append({"rank": len(rows) + 1, "cos": round(float(sims[k]), 4), "image_a": f"{images[i]['split']}/{images[i]['file']}",
                     "image_b": f"{images[j]['split']}/{images[j]['file']}", "family_a": images[i]["family"], "family_b": images[j]["family"]})
    with open(OUT / "analysis" / "top_embedding_pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    by_name = {f"{r['split']}/{r['file']}": r for r in images}
    for s in range(0, 48, 12):
        tiles = []
        for r in rows[s:s + 12]:
            a, b = thumb(by_name[r["image_a"]]), thumb(by_name[r["image_b"]])
            pair = np.hstack([a, np.full((200, 6, 3), 255, np.uint8), b])
            cv2.putText(pair, f"#{r['rank']} cos {r['cos']:.3f}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            tiles.append(cv2.copyMakeBorder(pair, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
        grid = np.vstack([np.hstack(tiles[k:k + 2]) for k in range(0, 12, 2)])
        cv2.imwrite(str(OUT / "analysis" / f"top_pairs_{s // 12 + 1}.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 82])
    res = {"pairs": int(len(sims)), "cos_percentiles": pct,
           "nearest_neighbour_cos": {"median": round(float(np.median(top1)), 4), "p90": round(float(np.percentile(top1, 90)), 4),
                                     "max": round(float(top1.max()), 4)},
           "pairs_above": {str(t): int((sims >= t).sum()) for t in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9)},
           "filename_sequence": seq_stats, "top10": rows[:10]}
    (OUT / "analysis" / "embedding_analysis.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: res[k] for k in ("cos_percentiles", "nearest_neighbour_cos", "pairs_above", "filename_sequence")}, indent=1))


def build(t_emb: float, test_images: int, seed: int) -> None:
    images = load_images()
    key = [f"{r['split']}/{r['file']}" for r in images]
    idx = {k: i for i, k in enumerate(key)}
    n = len(images)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    links = []
    for r in csv.DictReader(open(AUDIT / "similarity_pairs.csv", encoding="utf-8")):
        mc = float(r["background_masked_corr"]) if r["background_masked_corr"] not in ("", "nan") else float("nan")
        if int(r["dhash_hamming"]) <= 5 or (mc == mc and mc >= 0.85):
            links.append((idx[r["image_a"]], idx[r["image_b"]], "pixel near-duplicate"))
    E = embeddings(images)
    S = E @ E.T
    iu = np.triu_indices(n, 1)
    for k in np.where(S[iu] >= t_emb)[0]:
        links.append((int(iu[0][k]), int(iu[1][k]), f"embedding cos >= {t_emb}"))
    # generated-image prompt families: 'ultralytics-ppe-nov2026-NNN' images whose numbers are equal modulo 50
    # share one subject template (Phase 2 analysis: mean centred cosine 0.263 at a number distance of 50 vs
    # 0.061-0.068 at 49/51; visual check of residue 7). All members of a family are linked.
    fam_first = {}
    for i, r in enumerate(images):
        m = re.match(r"ultralytics-ppe-nov2026-(\d+)\.jpg", r["file"])
        if m:
            res = int(m.group(1)) % PERIOD
            if res in fam_first:
                links.append((fam_first[res], i, f"prompt family (number mod {PERIOD} = {res})"))
            else:
                fam_first[res] = i
    for a, b, _ in links:
        parent[find(a)] = find(b)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    gid = {}
    for g, (root, members) in enumerate(sorted(groups.items(), key=lambda kv: min(kv[1]))):
        for m in members:
            gid[m] = f"G{g:04d}"

    # per-image label statistics
    ann = list(csv.DictReader(open(AUDIT / "annotations.csv", encoding="utf-8")))
    inst = np.zeros((n, 12), dtype=np.int32)
    small_missing = np.zeros((n, len(MISSING)), dtype=np.int32)
    for a in ann:
        i = idx[f"{a['split']}/{a['file']}"]
        c = int(a["class_id"])
        inst[i, c] += 1
        if NAMES[c] in MISSING and float(a["min_side_640"]) < 8:
            small_missing[i, MISSING.index(NAMES[c])] += 1
    fam = np.array([1 if r["family"] == "source" else 0 for r in images])
    orig_val = np.array([r["split"] == "val" for r in images])

    member = defaultdict(list)
    for i in range(n):
        member[gid[i]].append(i)
    # A group selected for the locked test moves ALL of its original-train members to test; its original-val
    # members stay in dev. So no group can span train and test. Groups may span dev and test (documented).
    blocked = set()
    candidates = [g for g, ms in member.items() if (~orig_val[ms]).any()]
    train_members = {g: [m for m in member[g] if not orig_val[m]] for g in candidates}
    train_pool = np.array([not v for v in orig_val])
    pool_inst = inst[train_pool].sum(0)
    pool_img = (inst[train_pool] > 0).sum(0)
    pool_small = small_missing[train_pool].sum(0)
    pool_fam = fam[train_pool].sum()
    frac = test_images / int(train_pool.sum())

    def score(sel: list[int]) -> float:
        s_inst = inst[sel].sum(0) / np.maximum(pool_inst, 1)
        s_img = (inst[sel] > 0).sum(0) / np.maximum(pool_img, 1)
        s_small = small_missing[sel].sum(0) / np.maximum(pool_small, 1)
        s_fam = fam[sel].sum() / max(pool_fam, 1)
        dev = np.concatenate([np.abs(s_inst - frac), np.abs(s_img - frac), np.abs(s_small - frac), [abs(s_fam - frac)]])
        return float(dev.max() + dev.mean())

    rng = np.random.default_rng(seed)
    best, best_sel, tried = 9e9, None, 0
    for _ in range(20000):
        order = rng.permutation(len(candidates))
        sel = []
        for o in order:
            ms = train_members[candidates[o]]
            if len(sel) + len(ms) <= test_images:
                sel += ms
            if len(sel) == test_images:
                break
        tried += 1
        if len(sel) != test_images:
            continue
        sc = score(sel)
        if sc < best:
            best, best_sel = sc, sorted(sel)
    test_set = set(best_sel)
    split = {}
    for i in range(n):
        split[i] = "dev" if orig_val[i] else ("test" if i in test_set else "train")

    # ---- outputs
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "split_assignments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "original_split", "new_split", "group_id", "group_size", "family"])
        for i in range(n):
            w.writerow([key[i], images[i]["split"], split[i], gid[i], len(member[gid[i]]), images[i]["family"]])
    with open(OUT / "group_links.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_a", "image_b", "reason", "cosine"])
        for a, b, why in links:
            w.writerow([key[a], key[b], why, round(float(S[a, b]), 4)])
    lists = {}
    for s in ("train", "dev", "test"):
        lst = sorted(f"images/{s}/{images[i]['file']}" for i in range(n) if split[i] == s)
        lists[s] = lst
        (OUT / f"{s}.txt").write_text("\n".join(lst) + "\n")

    def stats(sel):
        sel = list(sel)
        return {"images": len(sel), "source_family_images": int(fam[sel].sum()),
                "instances": {NAMES[c]: int(inst[sel, c].sum()) for c in range(12)},
                "images_with_class": {NAMES[c]: int((inst[sel, c] > 0).sum()) for c in range(12)},
                "missing_ppe_lt8px_at_640": {MISSING[k]: int(small_missing[sel, k].sum()) for k in range(len(MISSING))}}
    st = {s: stats([i for i in range(n) if split[i] == s]) for s in ("train", "dev", "test")}
    share = {NAMES[c]: round(st["test"]["instances"][NAMES[c]] / max(1, st["test"]["instances"][NAMES[c]] + st["train"]["instances"][NAMES[c]]), 3)
             for c in range(12)}

    # ---- leakage checks
    cross = Counter()
    for a, b, why in links:
        if split[a] != split[b]:
            cross[f"{'-'.join(sorted((split[a], split[b])))} ({why.split(' ')[0]})"] += 1
    group_split_violations = sum(1 for g, ms in member.items() if {"train", "test"} <= {split[m] for m in ms})
    groups_dev_and_test = sum(1 for g, ms in member.items() if {"dev", "test"} <= {split[m] for m in ms})
    near = list(csv.DictReader(open(AUDIT / "similarity_pairs.csv", encoding="utf-8")))
    near_cross_test = [r for r in near if {split[idx[r["image_a"]]], split[idx[r["image_b"]]]} == {"train", "test"}
                       and (int(r["dhash_hamming"]) <= 5 or (r["background_masked_corr"] not in ("", "nan") and float(r["background_masked_corr"]) >= 0.85))]
    test_idx = [i for i in range(n) if split[i] == "test"]
    trainlike = [i for i in range(n) if split[i] in ("train", "dev")]
    max_cos_test_to_train = float(S[np.ix_(test_idx, [i for i in range(n) if split[i] == "train"])].max())
    max_cos_test_to_dev = float(S[np.ix_(test_idx, [i for i in range(n) if split[i] == "dev"])].max())
    leak = {"images_in_more_than_one_split": len(set(lists["train"]) & set(lists["test"])) + len(set(lists["dev"]) & set(lists["test"])),
            "groups_spanning_train_and_test": group_split_violations,
            "groups_spanning_dev_and_test (allowed, documented)": groups_dev_and_test,
            "cross_split_links": dict(cross),
            "pixel_near_duplicate_pairs_train_test": len(near_cross_test),
            "max_embedding_cos_test_to_train": round(max_cos_test_to_train, 4),
            "max_embedding_cos_test_to_dev": round(max_cos_test_to_dev, 4),
            "embedding_threshold_used": t_emb,
            "known_residual": "groups that are not in the test keep original-train and original-val members in train and dev "
                              "(train-dev overlap, as in all earlier work); test groups may share members with dev but never with train"}
    hashes = {s: sha256_bytes((OUT / f"{s}.txt").read_bytes()) for s in ("train", "dev", "test")}

    # ---- derived dataset: symlinks only
    for s in ("train", "dev", "test"):
        for kind in ("images", "labels"):
            (DSROOT / kind / s).mkdir(parents=True, exist_ok=True)
        for i in range(n):
            if split[i] != s:
                continue
            r = images[i]
            stem = Path(r["file"]).stem
            for kind, src, name in (("images", DATASET / "images" / r["split"] / r["file"], r["file"]),
                                    ("labels", DATASET / "labels" / r["split"] / f"{stem}.txt", f"{stem}.txt")):
                dst = DSROOT / kind / s / name
                if not dst.is_symlink():
                    os.symlink(src, dst)
    names_yaml = "\n".join(f"  {k}: {v}" for k, v in NAMES.items())
    (DSROOT / "dev.yaml").write_text(
        f"# Training / development configuration (train + dev). The locked test is NOT referenced here.\n"
        f"path: {DSROOT}\ntrain: images/train\nval: images/dev\nnames:\n{names_yaml}\n")
    (DSROOT / "locked_test.yaml").write_text(
        f"# LOCKED TEST - use only for Phase 6 qualification of a frozen candidate (spec §8).\n"
        f"# Every access must be logged in experiments/accuracy_improvement/qualification/locked_test_access_log.csv\n"
        f"path: {DSROOT}\nval: images/test\nnames:\n{names_yaml}\n")
    link_count = sum(1 for p in DSROOT.rglob("*") if p.is_symlink())
    report = {"created": datetime.now().isoformat(timespec="seconds"), "seed": seed, "random_search_iterations": tried,
              "test_images_target": test_images, "target_fraction_of_train_pool": round(frac, 4), "best_score": round(best, 4),
              "groups": {"total": len(member), "multi_image": sum(1 for ms in member.values() if len(ms) > 1),
                         "largest": max(len(ms) for ms in member.values()),
                         "size_histogram": dict(sorted(Counter(len(ms) for ms in member.values()).items())),
                         "candidate_groups_for_test": len(candidates)},
              "links": Counter(why for _, _, why in links), "split_stats": st, "test_share_of_train_pool_instances": share,
              "leakage_checks": leak, "split_list_sha256": hashes, "derived_dataset": str(DSROOT.relative_to(ROOT)),
              "derived_symlinks": link_count}
    (OUT / "split_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: report[k] for k in ("groups", "links", "test_share_of_train_pool_instances", "leakage_checks",
                                             "split_list_sha256", "derived_symlinks", "best_score")}, indent=1, default=str))
    print({s: (st[s]["images"], st[s]["source_family_images"]) for s in st})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["analyse", "build"])
    ap.add_argument("--emb-threshold", type=float, default=None)
    ap.add_argument("--test-images", type=int, default=160)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.mode == "analyse":
        analyse()
    else:
        if a.emb_threshold is None:
            raise SystemExit("--emb-threshold is required (choose it from the analyse contact sheets)")
        build(a.emb_threshold, a.test_images, a.seed)
