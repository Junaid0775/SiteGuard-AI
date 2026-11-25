# REPORT-020 — Phase 2: Evaluation Protocol and Leakage-Resistant Splits

**Programme:** YOLO26m accuracy improvement (specification §4)
**Date:** 2026-11-20, 01:10–01:20 IST
**Evidence:**
- `experiments/accuracy_improvement/splits/` (lists, assignments, links, report, analysis);
- `experiments/accuracy_improvement/datasets/v1_original_labels/`;
- `experiments/accuracy_improvement/evaluation/dev_*_baseline/`;
- `scripts/accuracy/{phase2_splits.py, evaluate.py}`.

**Status:** **Complete.** All Phase 2 acceptance criteria pass (§13). The locked test has been accessed **0 times** (`qualification/locked_test_access_log.csv` contains only its header).

---

## 1. Objective

Spec §4:
- decide whether the 800 original training images can provide a defensible train / development / locked-test split;
- group related images so that they cannot cross splits;
- save split manifests and hashes;
- fix the evaluation protocol: metrics, definitions, settings, matching, uncertainty;
- make the locked test unusable for training or tuning.

## 2. Scope and decisions in brief

| Question | Decision | Reason |
|---|---|---|
| Is the original 200-image val set a clean test? | **No.** It is **development data** ("dev") | It selected the best epoch of both existing models and served every earlier comparison and analysis (REPORT-009 to 017) |
| Can the 800 training images give a locked test? | **Yes: 160 images (20 %)**, made of whole groups | Enough instances for every class (46–440 per class, §5), while 640 images remain for training |
| Alternatives | Grouped 5-fold cross-validation: rejected as the primary method. About 5 × 95 min of training per configuration on this Mac, and it still needs an untouched final test. A smaller test: rejected, because the rare classes would have too few instances | — |
| What can be claimed from the locked test | "X on this limited, held-out, in-distribution test set (160 images)". **Not** real-world or deployment accuracy | The dataset README itself recommends "independent deployment imagery for final evaluation" |
| Existing checkpoints on the locked test | **Never evaluated there.** YOLO26n and YOLO26m were trained on all 800 original training images, including the 160 now in the locked test | Only models trained on the new 640-image training split are eligible for qualification |

## 3. Grouping evidence

Related images must stay together. Three kinds of relationship were tested.

### 3.1 Pixel near-duplicates (from Phase 1)

- Rule: dHash ≤ 5, or background-masked correlation ≥ 0.85.
- Result: one group of 3, the "gate camera" scene: `source-3978…`, `source-efc2…` (train) and `source-9e10…` (val).

### 3.2 Scene and template similarity (image embeddings)

**Method:**
- Global features from the COCO-pretrained YOLO26n backbone (`models/pretrained/yolo26n.pt`, Ultralytics `embed`).
- Each image is resized to a 320×320 square first, so the letterbox padding of different aspect ratios cannot dominate. A first, padded attempt was discarded for exactly that reason: median pair cosine 0.90.
- Vectors are mean-centred, then compared by cosine similarity over all 499,500 pairs.
- After centring: median pair cosine −0.006, 99.9th percentile 0.897, nearest-neighbour median 0.836.

**Threshold choice (manual check of the 36 most similar pairs; `splits/analysis/top_pairs_{1,2,3}.jpg`):**

| Cosine | What the pairs show |
|---|---|
| 0.957–0.990 | The same gate camera with different workers (4 pairs), the same fisheye packing floor (0.973), and a repeated warehouse layout with forklifts and pallets |
| 0.947–0.956 | Mostly that same warehouse layout; two different scenes |
| 0.943–0.947 | Mostly different scenes with a similar composition |

- **Threshold: 0.95.** It gives 19 links and 4 multi-image groups: the warehouse-layout group of 12, the gate group of 3, and two pairs.
- Lowering it to 0.94 or 0.93 would chain unrelated scenes (largest group 15, then 23).

### 3.3 Generated-image prompt families (filename sequence)

**Finding:**
- Images named `ultralytics-ppe-nov2026-NNN` cycle through five fixed sizes with period 5.
- **Numbers that are equal modulo 50 share one subject template.** Mean centred cosine is 0.263 at a number distance of 50, against 0.061 at 49 and 0.068 at 51 (random same-family pairs: 0.068).
- Visual check of residue 7 (`analysis/residue7_mod50.jpg`): the same two-worker template (red and blue helmets, navy coveralls) on different backgrounds.

**Rule:** all images with the same number mod 50 form one group, giving 50 families of 14–15 images.

**The original Ultralytics split already respects these families:**
- 39 families are entirely in train, 10 entirely in val, and **only 1 is mixed** (family 5: 14 train, 1 val).
- So the original val set mostly contains *unseen* families.

### 3.4 Resulting groups

- 328 groups: 274 single images, 50 prompt families (43 of 14 and 7 of 15 images), and the groups of 12, 3, 2 and 2.

## 4. Split construction (`phase2_splits.py build --emb-threshold 0.95 --test-images 160 --seed 0`)

- **dev** = the original 200 val images, unchanged.
- **locked test** = 160 images chosen as **whole groups**:
  - A group chosen for the test moves all its original-train members to test; its original-val members stay in dev.
  - A seeded random search (20,000 group orders, seed 0) picked the order whose test set best matches the target fraction (0.20 of the training pool) for every class's instance count, every class's image count, the source-family image count, and the number of missing-PPE boxes under 8 px at 640.
  - Score = maximum + mean absolute deviation, best 0.047.
  - **Only label statistics were used, never model outputs.**
- **train** = the remaining 640 original-train images.

**Derived dataset** `experiments/accuracy_improvement/datasets/v1_original_labels/`:
- 2,000 symlinks to the **original** images and labels. Nothing is copied or changed.
- `dev.yaml` (train + dev) is the only YAML that training may use.
- `locked_test.yaml` is separate and is not referenced by any training command.
- Ultralytics writes its label caches into this derived folder, never into the original dataset.

**Path mapping:** `datasets/` is an addition to the spec §11 layout. It holds derived dataset versions; the original stays at `../construction-ppe/`.

## 5. Split statistics (`splits/split_report.json`)

| | train | dev | **locked test** |
|---|---:|---:|---:|
| Images | 640 | 200 | **160** |
| `source-*` (real-scene family) / generated family | 187 / 453 | 59 / 141 | **47 / 113** |
| Prompt families (generated) | 32 whole + 14 of family 5 | 10 whole + 1 of family 5 | **8 whole** (families 6, 9, 16, 18, 31, 33, 42, 43) |
| Boxes | 9,422 | 2,961 | **2,480** |

| Class | train | dev | test | Test share of the 800-image pool | Images with class (train / dev / test) |
|---|---:|---:|---:|---:|---|
| helmet | 1,026 | 294 | 256 | 0.200 | 494 / 146 / 119 |
| gloves | 1,222 | 381 | 326 | 0.211 | 435 / 136 / 111 |
| vest | 1,173 | 340 | 303 | 0.205 | 513 / 157 / 131 |
| boots | 1,563 | 481 | 440 | 0.220 | 449 / 155 / 127 |
| goggles | 476 | 139 | 136 | 0.222 | 345 / 102 / 92 |
| Person | 1,561 | 481 | 401 | 0.204 | 632 / 200 / 159 |
| no_helmet | 492 | 179 | 142 | 0.224 | 267 / 91 / 70 |
| no_goggle | 219 | 82 | **46** | 0.174 | 187 / 56 / 40 |
| no_gloves | 656 | 203 | 183 | 0.218 | 273 / 94 / 67 |
| no_boots | 461 | 178 | 108 | 0.190 | 201 / 71 / 43 |
| forklift | 229 | 73 | **46** | 0.167 | 164 / 46 / 37 |
| no_vest | 344 | 130 | 93 | 0.213 | 242 / 84 / 58 |

Missing-PPE boxes with a short side under 8 px at 640 (train / dev / test):
- no_helmet 194 / 57 / 57;
- no_gloves 181 / 52 / 55;
- no_goggle 77 / 20 / 22;
- no_boots 84 / 31 / 18;
- no_vest 51 / 12 / 13.

**Statistical caution:**
- no_goggle (46) and forklift (46) have few test instances.
- Per-class locked-test results will carry wide confidence intervals and are reported with them.

## 6. Leakage checks (`split_report.json → leakage_checks`)

| Check | Result |
|---|---|
| Images in more than one split | **0** |
| Groups spanning train and test | **0** |
| Pixel near-duplicate pairs between train and test | **0** |
| Highest embedding cosine, test to train | **0.945**, below the 0.95 grouping threshold |
| Groups spanning dev and test | **1**: the gate scene (2 test, 1 dev). Allowed and documented. Dev never trains a model; at most it informs choices on a scene that also appears in two test images |
| Highest embedding cosine, test to dev | 0.981 (that gate scene) |
| Residual, not detectable | Same-site photos taken from very different viewpoints, and prompt-like relationships inside the `source-*` family, whose names are hashes with no sequence. The embedding check bounds visual similarity; it cannot prove independence |
| Known historical overlap | Train–dev: the warehouse-layout group (6 train / 6 dev) and prompt family 5 (14 / 1). This existed in all earlier work and does not touch the locked test |

**Hashes:**

| File | SHA-256 |
|---|---|
| `splits/train.txt` | `6d9138035fd2665e768e0b4beed7d01e72999771c9e6cee1591085bde649f70f` |
| `splits/dev.txt` | `eb1854d404cfe55a27398655b2dde8e3655dfe3321f5d059f808c43b6b024ae9` |
| `splits/test.txt` | `cbc2ef25b8e25f26f1b57f0c14c5ecfa8d43e81e9328371742d21f783aeef5c2` |
| `datasets/v1_original_labels/dev.yaml` / `locked_test.yaml` | `954b928ed085516d…` / `163374a94413e0a9…` (prefixes) |

## 7. Locked-test controls

1. **Training:** training YAMLs reference only `images/train` and `images/dev`. A run is rejected if its `args.yaml` mentions `images/test`; this check is part of the Phase 4 runner.
2. **Threshold and checkpoint selection:** only on dev, or on train-internal folds.
3. **Access:**
   - `scripts/accuracy/evaluate.py --split test` refuses to run without `--locked-test-purpose` and a `--frozen-sha256` equal to the weights' hash.
   - Every access is appended to `qualification/locked_test_access_log.csv`. Currently **0 accesses**.
4. **No revision after viewing** (spec §8). If a model is changed after its locked-test result is seen, this test set becomes development data and is reported as such.
5. **Contaminated checkpoints:** `models/trained/best.pt` (YOLO26n) and `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt` must not be evaluated on the locked test. They trained on those images.

## 8. Evaluation protocol v1 (`scripts/accuracy/evaluate.py`)

### 8.1 Metrics and definitions

| Metric | Definition |
|---|---|
| **Precision, Recall (Ultralytics)** | Mean over classes, each at the confidence that maximises that class's F1. Not values at the app threshold. Reported for comparability with REPORT-010 to 018 |
| **mAP50** | Mean over the 12 classes of AP at IoU 0.50. AP is the area under the interpolated precision–recall curve (Ultralytics `ap_per_class`, 101-point). **This is the metric of the primary ≥ 0.93 target** |
| **mAP50-95** | The same, averaged over IoU 0.50, 0.55 … 0.95 (stretch target ≥ 0.80) |
| **Per-class AP50 / AP50-95** | Per class, from the same computation |
| **Operating-point precision, recall, F1** | At the application threshold. Predictions ≥ conf are matched greedily in descending confidence to unmatched ground truth of the **same class** with IoU ≥ 0.50. TP = matched prediction; FP = unmatched prediction; FN = unmatched ground truth. **These are the metrics of the supporting (P, R ≥ 0.90) and safety (missing-PPE recall ≥ 0.90) targets** |
| **FP types** | For each FP: *duplicate* (same class, overlaps an already-matched GT), *wrong_class* (IoU ≥ 0.5 with a GT of another class), *localization* (same class, 0.1 ≤ IoU < 0.5), *background* (nothing nearby) |
| **Contradiction pairs** | Item and missing-item predictions for the same region (for example helmet and no_helmet) overlapping with IoU ≥ 0.5 |
| **Confusion matrix** | (a) Ultralytics, computed at conf 0.001, so background counts are inflated; (b) at the operating point, with class-agnostic greedy matching at IoU 0.5 plus a background row and column |
| **Size strata** | Recall at the operating point per class, by ground-truth short side **at the inference size** (< 8, 8–16, 16–32, ≥ 32 px) and by area band |
| **Family strata** | All operating-point and AP results separately for `source-*` and generated images. Filename family is reliable metadata; viewpoint is **not** (AI-assisted), so it is not used for claims |
| **Latency, memory** | Synchronised wall clock of `predict` plus the copy to numpy on full-resolution dataset images (MPS); MPS driver memory. **Analysed FPS** is measured through the application pipeline in Phase 7 |

The word "accuracy" is never used for any of these.

### 8.2 Fixed settings

| Setting | Value |
|---|---|
| Matching IoU | 0.50 (mAP50 and operating point); 0.50:0.95 (mAP50-95) |
| Confidence for AP | 0.001 |
| Operating confidence | 0.25 (current app setting) until Phase 5 chooses one **on dev**. The chosen value is then frozen for Phase 6 |
| NMS IoU | 0.7 for Ultralytics val; 0.5 for operating-point predictions (app setting); class-aware |
| Image size | The evaluated model's own training and deployment size (640 unless an experiment changes it). Comparisons across sizes are labelled as such |
| Evaluator | Ultralytics 8.4.215 `val` + `scripts/accuracy/evaluate.py` v1 (SHA-256 prefix `a9dd2e87ba0f8c58`) |
| Dataset manifest | Split-list SHA-256 (§6) and the original-file manifest from Phase 0 |

### 8.3 Uncertainty

- **Paired, image-level bootstrap** for model comparisons: resample whole images, never boxes. B = 1,000, seed 0, 95 % percentile intervals.
- Per-class intervals are reported for the safety-critical classes.
- Seed-to-seed variation is reported separately (Phase 4).

## 9. Baselines under protocol v1 (dev, 200 images, 2,961 boxes)

The new evaluator, run through the derived dataset, **reproduces every historical value exactly**: all Ultralytics metrics; the app-threshold TP/FP/FN; the missing-PPE recalls of REPORT-015 (corrected). This validates both the derived dataset and the evaluator.

| | YOLO26n (active, `890dc61f…`) | YOLO26m (previous, `399c4e5b…`) |
|---|---|---|
| Ultralytics P / R / mAP50 / mAP50-95 | 0.8322 / 0.6809 / 0.7339 / 0.5227 | 0.8909 / 0.7773 / **0.8311** / 0.6195 |
| Audit evaluator mAP50 / mAP50-95 (NMS 0.5) | 0.7296 / 0.5142 | 0.8150 / 0.6073 |
| Operating point P / R / F1 (conf 0.25) | 0.884 / 0.745 / 0.809 | 0.885 / 0.828 / 0.856 |
| TP / FP / FN; background FP | 2206 / 289 / 755; 53 | 2452 / 319 / 509; 89 |
| Missing-PPE recall (helmet / gloves / goggle / boots / vest) | 0.615 / 0.567 / 0.171 / 0.674 / 0.623 | 0.715 / 0.700 / 0.476 / 0.691 / 0.692 |
| Person recall | 0.902 | 0.956 |
| Latency per full-resolution image (mean) | 10.6 ms | 29.9 ms (battery) |

**Family strata on dev (YOLO26m; `family_strata.json`):**

| Family | Images / boxes | mAP50 (audit) | P / R at conf 0.25 | Missing-PPE recall (helmet / gloves / goggle / boots / vest) |
|---|---|---:|---|---|
| Generated close-ups (`ultralytics-ppe-*`) | 141 / 1,674 | **0.906** | 0.934 / **0.931** | **0.928 / 0.926** / 0.422 / **0.891 / 0.916** |
| Real-scene family (`source-*`) | 59 / 1,287 | **0.628** | 0.811 / **0.694** | 0.531 / 0.442 / 0.667 (n = 6) / **0.180** / 0.424 |

YOLO26n on the same strata: generated 0.877 mAP50, R 0.897; source 0.455 mAP50, R 0.547.

**Where the gap is:**
- On generated close-ups, YOLO26m is already near the supporting and safety targets, except no_goggle.
- **The deficit is concentrated in the dense real-scene images,** whose missing-PPE objects are tiny at 640 (REPORT-019 §10.2).
- That gives Phases 3–4 a precise target: small-object performance on `source-*` scenes. Overall dev metrics are a mix of the two families, so family strata are always reported.

## 10. Files, commands and tests

**Created:**
- `scripts/accuracy/phase2_splits.py`, `scripts/accuracy/evaluate.py`;
- `experiments/accuracy_improvement/splits/`:
  - `{train,dev,test}.txt`, `split_assignments.csv`, `group_links.csv`, `split_report.json`;
  - `analysis/`: embeddings (raw, 1,000 × 256), `embedding_analysis.json`, `top_embedding_pairs.csv`, contact sheets.
- `experiments/accuracy_improvement/datasets/v1_original_labels/` (symlinks and two YAMLs);
- `experiments/accuracy_improvement/evaluation/dev_yolo26n_active_baseline/`, `dev_yolo26m_e30_b4_baseline/`;
- `experiments/accuracy_improvement/qualification/locked_test_access_log.csv` (header only).

**Modified:** `docs/IMPLEMENTATION_LOG.md` (one row).

```bash
.venv/bin/python scripts/accuracy/phase2_splits.py analyse
.venv/bin/python scripts/accuracy/phase2_splits.py build --emb-threshold 0.95 --test-images 160 --seed 0
.venv/bin/python scripts/accuracy/evaluate.py --weights experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt \
    --split dev --out experiments/accuracy_improvement/evaluation/dev_yolo26m_e30_b4_baseline
.venv/bin/python scripts/accuracy/evaluate.py --weights models/trained/best.pt \
    --split dev --out experiments/accuracy_improvement/evaluation/dev_yolo26n_active_baseline
```

**Environment:** M5, battery 24 % and discharging, MPS. Same software as REPORT-018.

**Seeds:** split search seed 0.

**Tests:**
- Application suite unchanged at 124 (no application code touched). The test-split guard was exercised by design: the evaluator exits without `--frozen-sha256`.
- Protocol validation: exact reproduction of the historical dev metrics (§9).

## 11. Limitations

- The locked test is **in-distribution**: same dataset, same generator and photographers. It is not independent deployment imagery and cannot certify real-site performance.
- 160 images, with 46 instances for no_goggle and forklift. Small per-class samples.
- 47 of 160 test images are real-scene images. Results on that family will be uncertain.
- Removing 160 images reduces training data by 20 % compared with earlier runs. New models are compared with each other on the new split, and with the earlier checkpoints only on dev, where the training sets differ (labelled as non-controlled).
- Grouping cannot detect every relationship (§6).

## 12. Decisions

1. dev = original val; locked test = 160 grouped images from the original train set; train = 640.
2. Protocol v1 as in §8; the operating threshold is chosen on dev in Phase 5.
3. Family strata are always reported; viewpoint strata are not used for claims.
4. Existing checkpoints are never evaluated on the locked test.

## 13. Acceptance criteria (spec §4)

| Criterion | Status | Evidence |
|---|---|---|
| Split manifests and hashes saved | **PASS** | `splits/*.txt`, `split_assignments.csv`, SHA-256 in §6 |
| Leakage checks documented | **PASS** | §3, §6 |
| Locked test excluded from training and threshold tuning | **PASS** | Separate YAML; evaluator guard; ledger with 0 accesses; rules in §7 |
| Metric definitions explicit | **PASS** | §8 |
| REPORT-020 written | **PASS** | This file |

## 14. Next-phase readiness

**Ready for Phase 3** (data expansion, augmentation, small-object strategy). Its analytical parts can run on battery:
- external-dataset assessment;
- augmentation visualisation;
- tiling and resolution at inference with existing checkpoints on dev.

**Training ablations need mains power** (battery at 24 %).
