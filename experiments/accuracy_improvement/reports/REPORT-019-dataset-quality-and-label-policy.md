# REPORT-019 — Phase 1: Dataset Quality and Annotation Policy

**Programme:** YOLO26m accuracy improvement (specification §3)
**Date:** 2026-11-20, 01:00–01:15 IST
**Evidence:** `experiments/accuracy_improvement/data_audit/`, `experiments/accuracy_improvement/annotation_review/`, `docs/ANNOTATION_POLICY.md`
**Status:** **Complete.** All Phase 1 acceptance criteria pass (§16).
- **Human review is pending:** all 178 review cases are `unreviewed`. The review page is ready; the user's decision is needed only before any corrected dataset version is built.
- No label was corrected. The original dataset is unchanged (verified).

---

## 1. Objective

Spec §3:
- audit the whole dataset (structure, geometry, scale, resolvability, overlaps, duplicates, scene similarity, person-label gaps, co-occurrence, viewpoint and source distribution);
- account for all 162 earlier suspect rows, with the 51 high-priority cases listed individually;
- build a review manifest;
- write an annotation policy.

## 2. Scope

**In scope:** read-only analysis of `../construction-ppe/` (1,000 images, 14,863 boxes), a review artefact, and the policy document.

**Not done in this phase:**
- no label corrections, because none can be justified without human review (§10);
- no derived dataset copy, because there are no corrections. The derived copy for the new splits is built in Phase 2;
- no training.

## 3. Summary of findings

| Area | Finding |
|---|---|
| Structure | **Clean:** 1,000 images, 1,000 label files, **14,863 boxes**, 0 invalid rows, 0 boxes extending beyond the image, 0 empty label files, 0 unreadable images, 0 missing image–label pairs in either direction; all 12 class IDs present |
| Resolution vs objects | Images are large (long side 2,048 px for most). At the 640 inference size, **2,207 boxes (14.8 %) have a short side under 8 px and 315 under 4 px**. Only 36 are under 8 px at native resolution. The missing-PPE classes are the smallest: median short side at 640 is **no_goggle 9.4 px, no_helmet 12.8 px, no_gloves 16.0 px** |
| Two image families | `source-*` (293): all landscape, dense wide scenes (median 23 boxes and 4 persons per image). `ultralytics-ppe-nov2026-*` (707): five exact generator-style sizes, four of which hold exactly 141 images each; close-ups (median 9 boxes, 1 person). **Goggles are almost absent from the `source` family (23 of 751 instances)** |
| Duplicates / leakage | 0 exact duplicates, 0 same-class duplicate boxes (IoU ≥ 0.8). **One scene group of 3 images with a near-identical background crosses train/val** (2 train + 1 val; background-masked correlation 0.97–0.99). No other pair is similar after masking (≤ 0.78) |
| Person-label completeness | Share of Person boxes with **neither** the item nor its missing label: eye region **54.9 %**, gloves 31.4 %, boots 30.9 %, helmet 5.1 %, vest 2.6 % |
| Earlier suspects | **All 148 rule-based rows re-derived and matched one-to-one** to the REPORT-011 list, now with annotation IDs. The 14 visual-review rows are carried over. Total **162 = S001–S162**. 16 new Phase 1 findings = N001–N016 |
| The 51 high-priority cases | Mostly an **association-geometry artefact**, not wrong labels. The missing-PPE box sits on a head, hand or foot that sticks out of a *tight* Person box. With the compliance analyser's own 10 % Person-box margin, **42/51** reach ≥ 60 % containment; with 25 %, **49/51**. The AI pre-assessment (not human review) agrees: 42 look like valid labels on limbs outside tight boxes, 5 are Person-box geometry problems (3 in one image where all Person boxes exclude the heads), 3 are uncertain, 1 is an ambiguous crowd |
| Policy | `docs/ANNOTATION_POLICY.md` written. Only one source rule is known (README); everything else is the project's policy and is labelled as such |

## 4. Environment and hardware state

- Same machine and software as REPORT-018: M5, 16 GB; Python 3.12.16; Ultralytics 8.4.215; torch 2.15.0; OpenCV 5.1.0.
- Battery power (26 %); CPU-only work; no MPS use in this phase.

## 5. Files inspected

- `../construction-ppe/` images and labels (read only): every image decoded and every label line parsed.
- `experiments/dataset_audit/{suspect_annotations.csv, review_findings.csv}` (REPORT-011).
- `data/viewpoint_metadata.csv` (AI-assisted viewpoint labels).
- `scripts/engineering/dataset_audit.py`: its parsing, geometry and suspect rules are reused unchanged, so annotation row numbers and rules are identical.
- `configs/settings.yaml → compliance`: the containment rule and the Person-box margin.

## 6. Files created or modified

| Path | Action | Content |
|---|---|---|
| `scripts/accuracy/phase1_dataset_audit.py` | created | Full audit (§3.1) |
| `scripts/accuracy/phase1_review_manifest.py` | created | Review manifest, thumbnails, contact sheets, local review page |
| `experiments/accuracy_improvement/data_audit/*.csv, audit_summary.json` | created | `images.csv` (1,000), `annotations.csv` (14,863), `class_stats.csv`, `cooccurrence_images.csv`, `person_label_completeness.csv`, `overlap_pairs.csv`, `unlabelled_person_clusters.csv`, `similarity_pairs.csv`, `suspects_rule_based.csv`, `verify_end_of_phase1.json` |
| `experiments/accuracy_improvement/annotation_review/` | created | `review_manifest.csv` (178 rows), `thumbs/` (178 local crops), `sheets/` (17 contact sheets), `review.html`, `ai_preassessment.csv` (72 rows), `high_priority_51_table.md`, `high_priority_51_containment.csv` |
| `docs/ANNOTATION_POLICY.md` | created | Annotation policy v1.0 |
| `docs/IMPLEMENTATION_LOG.md` | one row appended | Log |

**No existing file was modified** apart from the log row. Thumbnails are local derived crops of the CC BY 4.0 dataset; no private camera imagery is involved.

## 7. Commands

```bash
.venv/bin/python scripts/accuracy/phase1_dataset_audit.py          # 23 s, CPU
.venv/bin/python scripts/accuracy/phase1_review_manifest.py        # manifest, thumbnails, sheets, review.html
# AI pre-assessment written to annotation_review/ai_preassessment.csv; manifest rebuilt to merge it
.venv/bin/python scripts/accuracy/integrity_manifest.py verify experiments/accuracy_improvement/manifests/20261120-005540_phase0 \
    --json experiments/accuracy_improvement/data_audit/verify_end_of_phase1.json
.venv/bin/python -m pytest -q                                       # 124 passed
```

## 8. Configurations, definitions and seeds

**Size bands** (normalised box area, as in REPORT-011): tiny < 0.1 %, small 0.1–1 %, medium 1–10 %, large ≥ 10 %.

**Pixel scale at inference:**
- The box is scaled by 640 / (image long side). This is what the model sees at imgsz 640.
- COCO-style bands at that scale: S < 32², M 32²–96², L ≥ 96².

**Resolvability flags** (heuristics, not label judgements): short side < 4 px at 640; < 8 px at 640; < 8 px at native resolution.

**Boundary:** a box edge within 0.2 % of the image border.

**Association:**
- A box belongs to a Person if ≥ 60 % of its area lies inside the Person box. This is the same 0.60 as `compliance.min_containment`.
- Margin variants expand each side of the Person box by 10 % or 25 % of its width and height. The 10 % variant mirrors `compliance.person_box_margin: 0.10`.

**Image similarity** (all 499,500 pairs; for the Phase 2 grouping):
- dHash and pHash (64-bit) Hamming distances;
- whole-image 32×32 grey thumbnail correlation;
- for candidate pairs (dHash ≤ 10, pHash ≤ 10, or correlation ≥ 0.85), a **background-masked** correlation with every labelled box removed. The masked threshold 0.85 is the same as in REPORT-011.

**Annotation ID:** `<split>/<label stem>#L<row>`, where row is the 1-based index among the non-empty label lines (identical to REPORT-011).

**Seeds:** not applicable; the audit is deterministic.

## 9. Data provenance and hashes

- Original dataset hashes are recorded in `experiments/accuracy_improvement/manifests/20261120-005540_phase0/dataset.csv` (2,004 files).
- **Re-verified at the end of Phase 1: 0 changed, 0 missing, 0 new** (`data_audit/verify_end_of_phase1.json`).
- The only protected file that changed is `docs/IMPLEMENTATION_LOG.md` (the appended log row).
- No checkpoint and no user data changed.

## 10. Audit results

### 10.1 Images (`images.csv`, `audit_summary.json → image_dimensions`)

| | All (1,000) | `source-*` (293: 234 train / 59 val) | `ultralytics-ppe-*` (707: 566 train / 141 val) |
|---|---|---|---|
| Width / height (min–median–max) | 1,152–2,048–2,048 / 848–1,360–2,048 | 1,264–2,048–2,048 / 848–1,360–1,536 | 1,152–2,048–2,048 / 1,152–2,048–2,048 |
| Aspect w/h (min–median–max) | 0.562–1.506–1.778 | 1.333–1.506–1.506 | 0.562–1.000–1.778 |
| Orientation | 577 landscape, 282 portrait, 141 square | 293 landscape | 284 landscape, 282 portrait, 141 square |
| Distinct sizes (top) | 9 (2048×1360: 361; four sizes with 141 each) | 5 (2048×1360: 218; 1536×1024: 42; 2048×1536: 26) | 5 (2048×1360: 143; 2048×1152, 1152×2048, 1360×2048, 2048×2048: 141 each) |
| Median boxes / persons per image | 12 / 2 | 23 / 4 | 9 / 1 |
| Median brightness (0–255) | 118.0 | 123.8 | 116.4 |

**What the two families are** is not documented. The README says the dataset "combines human-collected and generated images". The exact, evenly filled generator-style sizes of the `ultralytics-ppe-*` family are *consistent with* generated imagery, but this is **not established** and is not used as a fact anywhere.

### 10.2 Per class (`class_stats.csv`, all splits)

| Class | Instances (train / val) | Images | Tiny / small / medium / large | Median short side at 640 (px) | < 8 px at 640 | < 4 px at 640 | < 8 px native | Touching border | No containing Person | ≥ 2 containing Persons |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| helmet | 1,576 (1,282 / 294) | 759 | 610 / 447 / 518 / 1 | 24.7 | 350 | 50 | 6 | 39 | 33 | 29 |
| gloves | 1,929 (1,548 / 381) | 682 | 450 / 1,266 / 213 / 0 | 25.6 | 173 | 17 | 1 | 14 | 25 | 100 |
| vest | 1,816 (1,476 / 340) | 801 | 361 / 581 / 653 / 221 | 40.2 | 141 | 15 | 3 | 66 | 2 | 28 |
| boots | 2,484 (2,003 / 481) | 731 | 835 / 1,043 / 606 / 0 | 25.6 | 444 | 24 | 4 | 202 | 15 | 50 |
| goggles | 751 (612 / 139) | 539 | 17 / 668 / 66 / 0 | 24.8 | 6 | 0 | 0 | 11 | 0 | 11 |
| Person | 2,443 (1,962 / 481) | 991 | 283 / 662 / 487 / 1,011 | 58.0 | 169 | 18 | 0 | 439 | — | — |
| no_helmet | 813 (634 / 179) | 428 | **431** / 163 / 219 / 0 | **12.8** | **308** | **101** | 14 | 13 | 18 | 26 |
| no_goggle | 347 (265 / 82) | 283 | **238** / 108 / 1 / 0 | **9.4** | 119 | 7 | 1 | 0 | 0 | 16 |
| no_gloves | 1,042 (839 / 203) | 434 | 454 / 534 / 54 / 0 | **16.0** | **288** | 59 | 5 | 3 | 27 | 25 |
| no_boots | 747 (569 / 178) | 315 | 195 / 375 / 177 / 0 | 27.7 | 133 | 18 | 2 | 54 | 4 | 6 |
| forklift | 348 (275 / 73) | 247 | 3 / 34 / 101 / 210 | 242.4 | 0 | 0 | 0 | 196 | — | — |
| no_vest | 567 (437 / 130) | 384 | 161 / 90 / 234 / 82 | 65.3 | 76 | 6 | 0 | 28 | 2 | 31 |
| **Total** | **14,863** | | | | **2,207** | **315** | **36** | **1,065** | | |

**Instances by family:**
- `source`: helmet 860, gloves 533, vest 1,079, boots 1,124, **goggles 23**, Person 1,364, no_helmet 492, no_goggle 95, no_gloves 501, no_boots 238, forklift 131, no_vest 252.
- `ultralytics-ppe`: helmet 716, gloves 1,396, vest 737, boots 1,360, **goggles 728**, Person 1,079, no_helmet 321, no_goggle 252, no_gloves 541, no_boots 509, forklift 217, no_vest 315.

**Interpretation, for Phases 3–4:**
- Missing-PPE objects are mostly *judgeable at native resolution*: only 36 boxes are under 8 px there. But they become *tiny at 640*.
- That is direct evidence for testing higher inference/training resolution and tiling.
- Eye-region classes in real wide scenes are very scarce, so any eye-region metric is dominated by the close-up family.

### 10.3 Per-person label completeness (`person_label_completeness.csv`; 2,443 Person boxes)

| Item | Positive only | Missing only | Both | Neither | Neither share |
|---|---:|---:|---:|---:|---:|
| helmet | 1,511 | 780 | 28 | 124 | 5.1 % |
| vest | 1,803 | 561 | 15 | 64 | 2.6 % |
| gloves | 1,040 | 584 | 51 | 768 | 31.4 % |
| boots | 1,293 | 386 | 9 | 755 | 30.9 % |
| goggles | 742 | 350 | 10 | 1,341 | **54.9 %** |

"Both" for helmet, vest and goggles occurs only where Person boxes overlap: the 60 % rule can capture a neighbour's item. No single-person image carries both labels (the REPORT-011 rule found 0).

"Neither" for hands, feet and eyes is largely legitimate: the region is hidden, too small or turned away. It is consistent with the dataset rule that occlusion is not evidence.

### 10.4 Overlapping boxes (`overlap_pairs.csv`; IoU ≥ 0.5 within an image)

- **0 same-class duplicates (IoU ≥ 0.8). 0 contradictory item / missing-item pairs.**
- Cross-class overlaps are expected geometry: Person–vest 59, Person–no_vest 47, Person–forklift 7, Person–helmet 5, Person–no_helmet 4 — close-ups or head-only people.
- **Unusual overlaps, now review cases N001–N011:**
  - goggles–no_helmet 5, no_goggle–no_helmet 2 (one at **IoU 0.906**: N005);
  - same-class overlaps 0.5–0.8: 3;
  - Person–Person 1.

### 10.5 People possibly missing Person boxes

- 5 clusters of ≥ 2 orphan PPE boxes covering ≥ 2 body regions (N012–N016).
- 1 image with PPE boxes but no Person box at all.
- Earlier visual review: forklift and vehicle drivers are not labelled as Person (S052–S056 include these).

### 10.6 Duplicates and scene similarity (`similarity_pairs.csv`; 13 candidate pairs out of 499,500)

| Group | Images | Evidence | Consequence |
|---|---|---|---|
| Gate scene | `train/source-3978abe9cfed5d8a5faa5a98dfe4b00a.jpg`, `train/source-efc23273c04e007083114c0f217335f0.jpg`, `val/source-9e10b0409f922546c35b276eb5a5756e.jpg` | dHash 3–5; background-masked correlation 0.975–0.992 | **One scene crossing train/val.** These must be grouped in Phase 2 |
| 10 other candidate pairs | — | Masked correlation ≤ 0.78 (or < 50 unmasked pixels) | Not the same scene |

Exact duplicates: 0 (all 1,000 SHA-256 hashes distinct; REPORT-011).

### 10.7 Class co-occurrence (`cooccurrence_images.csv`)

- A full 12×12 image-level matrix is saved.
- Person appears in 991 of 1,000 images, so every class co-occurs mostly with Person.
- Forklift images (247) are mainly warehouse scenes.

### 10.8 Viewpoint and scene distribution — **uncertain metadata**

- `data/viewpoint_metadata.csv` was produced by "manual visual inspection of contact-sheet thumbnails" **by the AI assistant**, not by a human.
- Train: frontal 527, overhead 166, side 84, low angle 10, unclear 13. Val: frontal 112, overhead 53, side 32, low angle 3.
- Image group: close-up 530 / 141; scene 270 / 59.
- **These labels are not used to make claims.** They may only stratify exploratory results, and are marked as AI-assisted.

## 11. Suspect review (`annotation_review/`)

### 11.1 Accounting for the 162 earlier suspects

| Group | IDs | Count | Source |
|---|---|---:|---|
| High: missing-PPE box not contained in any Person box | S001–S051 | **51** | Rule (REPORT-011), re-derived 51/51 |
| High: visual review (missing Person label ×4, unsupported no_goggle ×1) | S052–S056 | 5 | AI visual review (REPORT-011) |
| Medium: extreme aspect ×15, item as large as person ×7, visual ×3 | S057–S081 | 25 | Rule + visual |
| Low: PPE box without person ×75, visual small objects ×6 | S082–S162 | 81 | Rule + visual |
| **Total earlier suspects** | S001–S162 | **162** | All accounted for |
| New Phase 1 findings (overlaps ×11, orphan clusters ×5) | N001–N016 | 16 | Phase 1 |

Each manifest row carries:
- image path, label file, annotation ID, row, class, normalised and pixel coordinates, short side at 640, reason;
- the local thumbnail path;
- **review status `unreviewed`**, empty reviewer and timestamp fields;
- separate AI pre-assessment columns.

### 11.2 How to review (human)

1. Open `experiments/accuracy_improvement/annotation_review/review.html` in a browser. It is a local file and needs no network.
2. For each case you judge, pick a status (`confirmed`, `corrected-in-derived-copy`, `exclude-with-reason`, `uncertain`) and add a note. Page state is kept in the browser.
3. Enter your name and press **Download decisions CSV**.
4. Save the file as `annotation_review/human_review_decisions.csv`.

Only cases with a status other than `unreviewed` are exported. Corrections are then applied in a versioned derived copy, with a change log.

**Minimum useful review:**
- the 51 high-priority cases (S001–S051), especially the 3 `uncertain`, the 5 `person_box_geometry_issue` and the 9 that do not associate even at +10 %;
- N005 (possible label error);
- the policy questions in §13.

### 11.3 The 51 high-priority cases, individually

Containment is the largest share of the box inside any Person box (expanded by 0 %, 10 % or 25 % per side); ≥ 0.60 means it would associate. The AI pre-assessment was made from contact-sheet thumbnails and is **not a human review**.

| Review ID | Annotation ID | Class | Short side at 640 (px) | Containment: none / +10 % / +25 % | AI pre-assessment (not human review) |
|---|---|---|---:|---|---|
| S001 | `train/source-022057494459ca6f76f42787146319ff#L7` | no_helmet | 3.0 | 0.00 / 0.00 / 0.03 | uncertain_needs_full_resolution |
| S002 | `train/source-022057494459ca6f76f42787146319ff#L8` | no_helmet | 3.0 | 0.58 / 0.74 / 0.97 | association_edge_case_label_plausible |
| S003 | `train/source-04c535fcc25148fcc46c3e4d36902d57#L20` | no_gloves | 3.0 | 0.07 / 1.00 / 1.00 | uncertain_needs_full_resolution |
| S004 | `train/source-0f1bcf865e6c2db6ebdc47be3bb206b7#L20` | no_helmet | 6.4 | 0.49 / 0.87 / 1.00 | association_edge_case_label_plausible |
| S005 | `train/source-14bd7cec4f45ba3526e8219b69f10d7a#L12` | no_gloves | 2.5 | 0.45 / 0.86 / 1.00 | association_edge_case_label_plausible |
| S006 | `train/source-14bd7cec4f45ba3526e8219b69f10d7a#L13` | no_boots | 3.0 | 0.56 / 0.95 / 1.00 | association_edge_case_label_plausible |
| S007 | `train/source-170f0215ae2fb7f1bc4b26a6895fd581#L11` | no_gloves | 3.2 | 0.39 / 0.74 / 1.00 | association_edge_case_label_plausible |
| S008 | `train/source-1cf7cb3866d943a954bc8e591591e519#L29` | no_gloves | 3.8 | 0.10 / 0.48 / 1.00 | association_edge_case_label_plausible |
| S009 | `train/source-1cf7cb3866d943a954bc8e591591e519#L30` | no_gloves | 5.1 | 0.45 / 0.73 / 1.00 | association_edge_case_label_plausible |
| S010 | `train/source-1cf7cb3866d943a954bc8e591591e519#L31` | no_gloves | 5.5 | 0.03 / 0.31 / 0.73 | association_edge_case_label_plausible |
| S011 | `train/source-2edf4fdf4d031044f1130ef13ef129cc#L19` | no_helmet | 3.8 | 0.54 / 1.00 / 1.00 | association_edge_case_label_plausible |
| S012 | `train/source-32b77e88696e2ba988310ec62da94f16#L46` | no_helmet | 4.7 | 0.00 / 0.22 / 0.73 | uncertain_needs_full_resolution |
| S013 | `train/source-32b77e88696e2ba988310ec62da94f16#L50` | no_vest | 8.3 | 0.51 / 0.64 / 0.87 | person_box_geometry_issue |
| S014 | `train/source-3fcdab28d51a8a73673fd1bd1bf917c0#L23` | no_gloves | 5.1 | 0.47 / 1.00 / 1.00 | association_edge_case_label_plausible |
| S015 | `train/source-41527d1166c4fb9c683f1a66502cbc3e#L29` | no_gloves | 4.5 | 0.07 / 0.69 / 1.00 | association_edge_case_label_plausible |
| S016 | `train/source-449d7c49b40597a87fd789730bc14f43#L27` | no_gloves | 4.7 | 0.07 / 0.33 / 0.72 | association_edge_case_label_plausible |
| S017 | `train/source-52fd8c6b1a98a15b0556e6f521ab06d7#L10` | no_helmet | 3.2 | 0.38 / 0.66 / 1.00 | person_box_geometry_issue |
| S018 | `train/source-52fd8c6b1a98a15b0556e6f521ab06d7#L11` | no_helmet | 5.1 | 0.37 / 0.66 / 1.00 | person_box_geometry_issue |
| S019 | `train/source-52fd8c6b1a98a15b0556e6f521ab06d7#L12` | no_helmet | 4.5 | 0.49 / 0.79 / 1.00 | person_box_geometry_issue |
| S020 | `train/source-5aef8f03a221e1d0f7dc1df4501dda5e#L23` | no_helmet | 3.8 | 0.47 / 0.87 / 1.00 | association_edge_case_label_plausible |
| S021 | `train/source-62f03e64233ccb5a3966914b379a424c#L19` | no_helmet | 4.2 | 0.45 / 0.87 / 1.00 | association_edge_case_label_plausible |
| S022 | `train/source-697ef7be42e68d78ab9ba0191638f308#L10` | no_gloves | 3.8 | 0.40 / 0.94 / 1.00 | association_edge_case_label_plausible |
| S023 | `train/source-6b6114dea7ecbe5997f1f0393824508b#L18` | no_gloves | 5.8 | 0.36 / 0.80 / 1.00 | association_edge_case_label_plausible |
| S024 | `train/source-74c0b473923339bf2a5d512cfb73b63c#L28` | no_gloves | 8.1 | 0.39 / 0.84 / 1.00 | association_edge_case_label_plausible |
| S025 | `train/source-87a78faabd244b0faf55fd305407adef#L16` | no_gloves | 2.6 | 0.50 / 0.88 / 1.00 | association_edge_case_label_plausible |
| S026 | `train/source-883735c1b03f27b4b0d1b75cf5a5575b#L14` | no_helmet | 5.1 | 0.49 / 0.75 / 0.90 | association_edge_case_label_plausible |
| S027 | `train/source-8d0f06f4f83594e0a66dc5567587f7f6#L9` | no_gloves | 3.8 | 0.37 / 0.68 / 1.00 | association_edge_case_label_plausible |
| S028 | `train/source-8e33b28f753f04e4141c3b4a561d868a#L24` | no_helmet | 3.8 | 0.41 / 0.69 / 1.00 | association_edge_case_label_plausible |
| S029 | `train/source-8e33b28f753f04e4141c3b4a561d868a#L26` | no_helmet | 3.8 | 0.52 / 0.91 / 1.00 | association_edge_case_label_plausible |
| S030 | `train/source-8e33b28f753f04e4141c3b4a561d868a#L27` | no_vest | 6.4 | 0.59 / 0.71 / 0.86 | person_box_geometry_issue |
| S031 | `train/source-903bd92aa69a20ccde63606d9b8e74af#L34` | no_gloves | 4.5 | 0.49 / 1.00 / 1.00 | association_edge_case_label_plausible |
| S032 | `train/source-903bd92aa69a20ccde63606d9b8e74af#L35` | no_gloves | 5.8 | 0.37 / 1.00 / 1.00 | association_edge_case_label_plausible |
| S033 | `train/source-a221c5bce61774564bb52fa445977871#L21` | no_gloves | 5.1 | 0.40 / 0.64 / 1.00 | association_edge_case_label_plausible |
| S034 | `train/source-a36439d05ebf0f383997aed40d295074#L15` | no_helmet | 4.2 | 0.29 / 0.62 / 1.00 | association_edge_case_label_plausible |
| S035 | `train/source-a9654697f4739d0834ce644ae8a0ca79#L31` | no_helmet | 5.1 | 0.59 / 1.00 / 1.00 | association_edge_case_label_plausible |
| S036 | `train/source-b7365710e3f2d090a30fae7678bef407#L35` | no_gloves | 5.1 | 0.54 / 0.96 / 1.00 | association_edge_case_label_plausible |
| S037 | `train/source-c01dfb2dbae89f8e5825648d9da4e842#L11` | no_gloves | 6.4 | 0.57 / 0.85 / 1.00 | association_edge_case_label_plausible |
| S038 | `train/source-c715790ce68e51f46da3fef5c618486a#L7` | no_gloves | 4.7 | 0.54 / 1.00 / 1.00 | association_edge_case_label_plausible |
| S039 | `train/source-eabef86b2cecf0e9ffe06787e0298a38#L29` | no_boots | 5.1 | 0.39 / 0.76 / 0.96 | association_edge_case_label_plausible |
| S040 | `train/source-eabef86b2cecf0e9ffe06787e0298a38#L31` | no_boots | 3.8 | 0.45 / 0.65 / 0.86 | association_edge_case_label_plausible |
| S041 | `train/source-efa761a319a37ba07e58ccd0bc1a4003#L23` | no_helmet | 5.8 | 0.57 / 0.93 / 1.00 | association_edge_case_label_plausible |
| S042 | `train/source-efa761a319a37ba07e58ccd0bc1a4003#L26` | no_gloves | 6.4 | 0.00 / 0.20 / 0.89 | association_edge_case_label_plausible |
| S043 | `val/source-150feca69395fa769adccdc8e157e935#L13` | no_gloves | 7.0 | 0.27 / 0.45 / 0.72 | association_edge_case_label_plausible |
| S044 | `val/source-53cbca61c77e1f22da4e9c5a1e6acdb7#L31` | no_gloves | 5.1 | 0.00 / 0.14 / 0.34 | association_edge_case_label_plausible |
| S045 | `val/source-56088ecf75821c1b93f4015a2bc0a071#L23` | no_gloves | 5.6 | 0.16 / 0.76 / 1.00 | association_edge_case_label_plausible |
| S046 | `val/source-63861e8188160ca09d7e331600db6cad#L9` | no_helmet | 3.8 | 0.42 / 0.81 / 1.00 | association_edge_case_label_plausible |
| S047 | `val/source-aace0a9a1ad6cbfe9e492e99b2eb14e4#L18` | no_helmet | 5.1 | 0.15 / 0.81 / 1.00 | association_edge_case_label_plausible |
| S048 | `val/source-b08681d985288f3ddcc52556c4445bab#L19` | no_boots | 4.2 | 0.36 / 0.63 / 1.00 | association_edge_case_label_plausible |
| S049 | `val/source-c565c40ac5d9c5f2659804a3826ab942#L16` | no_gloves | 5.9 | 0.47 / 0.75 / 1.00 | association_edge_case_label_plausible |
| S050 | `val/source-f90f8c78e44eb2d40158a732d46901c8#L19` | no_gloves | 5.8 | 0.00 / 0.46 / 1.00 | association_edge_case_label_plausible |
| S051 | `val/ultralytics-ppe-nov2026-024#L44` | no_gloves | 5.5 | 0.24 / 0.63 / 1.00 | ambiguous_crowd |

**Summary:**
- **0/51 associate without a margin (by definition), 42/51 with the application's 10 % margin, 49/51 with 25 %.**
- By class: no_gloves 27, no_helmet 18, no_boots 4, no_vest 2.
- Pre-assessment: 42 association edge cases (35 associate at +10 %), 5 Person-box geometry issues, 3 uncertain, 1 ambiguous crowd.

**Conclusion:**
- The "high-priority" flag mainly reveals that **Person boxes in this dataset are drawn tightly**: they often exclude raised arms, reaching hands, heads (systematically in one image) and feet.
- It is **not** evidence that the missing-PPE labels are wrong.
- Consequence for the application: some genuine missing-PPE detections on limbs outside the person box will be *unassigned* (status *uncertain*) unless the margin covers them. This is noted for the user. **No compliance rule is changed** (spec §0.1 rule 10).

### 11.4 New findings (N001–N016), AI pre-assessment

- Plausible valid: 9 (two hands or feet close together; close-up faces where head and eye boxes overlap; occluded workers).
- Uncertain: 3 (N001, N012, N015).
- **Possible label error: 1 (N005: no_helmet and no_goggle boxes almost identical, IoU 0.906).**
- Likely missing Person box: 1 (N014).
- Policy questions: 2 (N013 unworn helmet on the ground; N016 partially visible worker).

## 12. Annotation policy (`docs/ANNOTATION_POLICY.md`)

The policy defines all 12 classes. It gives rules for:
- Person boxes, including limbs;
- partially visible people;
- when a missing-PPE label is justified (visible, resolvable, belongs to a person, no contradicting positive);
- unresolvable eyes, and ordinary eyeglasses vs protective goggles;
- forklift and vehicle operators;
- tiny, occluded or unjudgeable items;
- overlapping workers, unworn items, and uncertain or excluded examples;
- change control in derived copies only.

It states that **the absence of a PPE detection is not proof of a violation**, and that the existing conservative compliance logic is preserved. It names the one rule taken from the source README and states that the rest is project policy, not the creator's intent.

## 13. Ambiguities and decisions needed from the user

These are needed only before a corrected dataset version is built. They do not block Phase 2.

1. **Vehicle operators:** label visible forklift and roller drivers as Person (policy §8.1), or leave the existing labels as they are?
2. **no_goggle on unresolvable eyes:** exclude such labels in a derived training copy, or keep them?
3. **Unworn items** (N013): remove the `helmet` label from unworn helmets in a derived copy, or keep it?
4. **Review of S001–S051** (at least the 17 flagged above) and N005.

## 14. Tests and exact counts

- **Application test suite:** 124 passed, 0 failed, 0 skipped (12.75 s). No application code changed.
- **Audit verification checks:**
  - structural counts equal the dataset README (1,000 images; 14,863 boxes);
  - rule-based suspects re-derived **148/148** matched to REPORT-011 (0 unmatched either way);
  - integrity verify: dataset 0 changed / 0 missing / 0 new.

## 15. Limitations

- **The AI pre-assessment used thumbnails (crops up to 320 px).** It is a triage aid, not a review, and does not change any status.
- **Similarity:** thumbnail-based measures find near-identical scenes but not "same site, different viewpoint" relationships. Phase 2 adds checks on filename sequence and family.
- **Heuristic cut-offs:** the resolvability thresholds (4 / 8 px) and the orphan-cluster rule are heuristics. They flag cases for review; they do not decide labels.
- **Viewpoint metadata** is AI-assisted and unverified.

## 16. Acceptance criteria (spec §3)

| Criterion | Status | Evidence |
|---|---|---|
| All 162 suspects accounted for | **PASS** | S001–S162 in `review_manifest.csv`; 148/148 rule rows reconciled; 14 visual rows carried over |
| 51 high-priority cases individually listed | **PASS** | §11.3 and `high_priority_51_containment.csv` |
| Ambiguities documented | **PASS** | §13; `docs/ANNOTATION_POLICY.md` §§6–9 |
| Original files unchanged | **PASS** | `verify_end_of_phase1.json`: 0 changed / 0 missing / 0 new |
| REPORT-019 written | **PASS** | This file |
| No invented human review | **PASS** | All 178 cases `unreviewed`; AI notes in separate, labelled columns |

## 17. Next-phase readiness

**Ready for Phase 2** (evaluation protocol and leakage-resistant splits). Inputs carried forward:
- the gate-scene group of 3 (must not be split);
- filename families (stratify, and report results per family);
- the class scale statistics;
- the fact that the original val set is development data.

**Outstanding:**
- Human review (§11.2) and the policy decisions (§13): optional for Phase 2, required before any corrected dataset version.
- Mains power before Phase 3–4 training.
