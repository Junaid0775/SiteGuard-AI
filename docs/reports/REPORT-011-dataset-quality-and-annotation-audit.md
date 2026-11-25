# REPORT-011 — Dataset Quality and Annotation Audit

**Date:** 2026-11-19 (21:10–21:17 IST, from file timestamps) **Spec:** §6 (Phase 4) **Workspace:** `experiments/dataset_audit/`
**Status:** Complete. The original dataset was **read only**: 2,004 hashes are unchanged and no file was added (verified after the audit). Nothing was corrected automatically.

---

## 1. Executive summary

| Aspect | Finding |
|---|---|
| **Structural validity** | Clean. 800/800 train and 200/200 val image–label pairs, 14,863 annotations; 0 invalid rows, out-of-range coordinates, zero-size boxes, empty label files, unreadable images or duplicate filenames. All 12 class IDs present. |
| **Class imbalance** | Strong. no_goggle 2.33 % and forklift 2.34 % of annotations against boots 16.7 % and Person 16.4 %. |
| **Scale imbalance (more important)** | The missing-PPE classes are **much smaller** than their positive counterparts. Median normalised area: no_helmet 0.00068 vs helmet 0.00273. no_goggle is 99.7 % small (< 1 % of the image) and 68.6 % tiny (< 0.1 %). no_gloves is 94.8 % small. |
| **Duplicates / leakage** | 0 exact duplicates. 1 perceptual near-duplicate pair, which crosses train/val. Visual review shows the **same gate-camera background with a different worker**. A background-only analysis (labelled boxes masked) finds that **1 of 200 val images (0.5 %)** shares a near-identical background with train (r = 0.991). No other val image exceeds r = 0.81. There is **no material leakage**, so no stop condition is triggered. The original split is preserved. |
| **Visual annotation quality (sample)** | 29 images reviewed, selected systematically (§9). 15 clean. Issues: vehicle operators (forklift drivers) not labelled as Person while a road-roller driver was; missing-PPE boxes on partially visible people without a Person box; no_goggle on distant workers whose eyes are not resolvable; boot-vs-shoe ambiguity; eyeglasses vs goggles (REPORT-010). |
| **Rule-based suspects** | 148 rows: 51 high (missing-PPE box not inside any Person box), 22 medium, 75 low. Plus 14 visual-review rows. Total **162**, all `unreviewed` or `needs human confirmation`. |
| **Viewpoint metadata** | 639 frontal, 116 side, 219 overhead, 13 low-angle, 13 unclear. **AI-assisted thumbnail labels, not human-verified.** |

## 2. Objective

Spec §6: inventory and structural validation; class distribution; box scale; duplicates and leakage; visual annotation review; suspect list; viewpoint metadata. All without modifying the original dataset.

## 3. Initial project state

- The original dataset is at `/Users/junaidahmad/Desktop/471 Project/construction-ppe/`, with the hash baseline from REPORT-010.
- Prior validation (REPORT-003) established structural correctness only.
- The README states that the set mixes human-collected and generated images.

## 4. Technical investigation

### 4.1 Inventory and image dimensions (`inventory.json`, `image_dimensions.csv`)

| Item | Value |
|---|---|
| Train images / labels | 800 / 800; images without label 0; labels without image 0 |
| Val images / labels | 200 / 200; 0 / 0 |
| Annotations | 14,863. Invalid rows 0 (5 fields, class 0–11, coordinates in [0, 1], w/h > 0) |
| Empty label files / unreadable images / unsupported extensions | 0 / 0 / 0 |
| Duplicate filenames across splits | 0 |
| Width min / median / mean / max | 1152 / 2048 / 1798.6 / 2048 px |
| Height min / median / mean / max | 848 / 1360 / 1609.8 / 2048 px |
| Aspect w/h min / median / mean / max | 0.5625 / 1.506 / 1.20 / 1.778 |
| Orientation | 577 landscape, 282 portrait, 141 square |
| Most common sizes | 2048×1360 (361), then exactly **141** each of 2048×1152, 1360×2048, 1152×2048 and 2048×2048; 1536×1024 (42) |

The identical counts of 141 per size suggest a standardised generated subset. That is consistent with the README and with the `ultralytics-ppe-nov2026-*` file family.

### 4.2 Class distribution (`class_distribution.csv`, `charts/class_distribution.png`)

| Class | Train | Val | Share % | Train imgs | Val imgs | Median area (norm.) | Median area (px) | Small % (tiny %) | Medium % | Large % |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| helmet | 1282 | 294 | 10.60 | 613 | 146 | 0.00273 | 6,972 | 67.1 (38.7) | 32.9 | 0.1 |
| gloves | 1548 | 381 | 12.98 | 546 | 136 | 0.00394 | 10,501 | 89.0 (23.3) | 11.0 | 0.0 |
| vest | 1476 | 340 | 12.22 | 644 | 157 | 0.00831 | 21,360 | 51.9 (19.9) | 36.0 | 12.2 |
| boots | 2003 | 481 | 16.71 | 576 | 155 | 0.00413 | 11,141 | 75.6 (33.6) | 24.4 | 0.0 |
| goggles | 612 | 139 | 5.05 | 437 | 102 | 0.00434 | 12,234 | 91.2 (2.3) | 8.8 | 0.0 |
| Person | 1962 | 481 | 16.44 | 791 | 200 | 0.02877 | 71,541 | 38.7 (11.6) | 19.9 | 41.4 |
| no_helmet | 634 | 179 | 5.47 | 337 | 91 | **0.00068** | 1,585 | 73.1 (**53.0**) | 26.9 | 0.0 |
| no_goggle | 265 | 82 | 2.33 | 227 | 56 | **0.00069** | 1,938 | **99.7** (**68.6**) | 0.3 | 0.0 |
| no_gloves | 839 | 203 | 7.01 | 340 | 94 | 0.00145 | 3,887 | 94.8 (43.6) | 5.2 | 0.0 |
| no_boots | 569 | 178 | 5.03 | 244 | 71 | 0.00480 | 12,458 | 76.3 (26.1) | 23.7 | 0.0 |
| forklift | 275 | 73 | 2.34 | 201 | 46 | 0.32866 | 899,387 | 10.6 (0.9) | 29.0 | 60.3 |
| no_vest | 437 | 130 | 3.81 | 300 | 84 | 0.02499 | 67,340 | 44.3 (28.4) | 41.3 | 14.5 |

The train/val ratio per class is about 80/20 for every class (split consistency is good).

### 4.3 Bounding-box scale (`box_scale_by_class.csv`, `boxes.csv`, `charts/box_size_categories.png`)

**Thresholds (project audit categories, not universal standards):**
- small: normalised area < 0.01 (the box covers less than 1 % of the image; for a 2048×1360 image that is under about 27,900 px², e.g. 167×167 px);
- medium: 0.01–0.10;
- large: ≥ 0.10;
- tiny (< 0.001, under about 2,800 px², e.g. 53×53 px) is reported as a sub-count of small.

The thresholds were chosen to separate distant objects in wide scenes from close-up PPE.

**Observations:**
- Gloves, goggles and boots are almost entirely small.
- no_helmet and no_goggle are dominated by *tiny* boxes (53 % and 68.6 %), i.e. distant workers in wide scenes. Positive helmets are larger (tiny 38.7 %).
- So the missing-PPE classes are not only rarer; they are also disproportionately *small*.
- This links directly to REPORT-010: recall below 1 % area drops to 0.47 (no_helmet), 0.20 (no_vest) and 0.17 (no_goggle).

### 4.4 Duplicates and leakage

- **Exact:** SHA-256 over all 1,000 images found 0 duplicate groups (`duplicates_exact.csv`, empty).
- **Perceptual** (`near_duplicates.csv`). Method: 64-bit dHash (9×8 gradient) and a 64-bit DCT hash (32×32 → 8×8 low-frequency block, threshold = block median). Candidates have dHash ≤ 10 or DCT-hash ≤ 10. A pair is "near-duplicate" if dHash ≤ 5 and DCT-hash ≤ 8. Result: 13 candidate pairs, 1 near-duplicate.
- **Visual review of all 13 pairs** (`review_sheets/near_duplicate_pairs.jpg`):
  - #0 (train `source-efc23273…` / val `source-9e10b040…`) and #2 (train `source-3978abe9…` / val `source-9e10b040…`): **same gate-camera background, different worker**.
  - #1 (train/train): same scene and person with and without a vest, i.e. generated variants of one base scene.
  - #3–#12: different images with similar simple layouts (false alarms).
- **Background-only leakage check** (`background_leakage.json`, `review_sheets/background_leakage_pairs.jpg`):
  - Method: 64×64 grayscale, every labelled box masked, Pearson correlation over pixels that are background in both images (≥ 40 % shared). Best train match per val image.
  - Result: **1 val image ≥ 0.85** (r = 0.991, the gate scene above). The next best are r = 0.808, 0.807 and 0.802, all visually different scenes with similar sky/ground structure.
  - A first attempt with masked perceptual hashes was rejected. Images whose boxes cover most of the frame hash as near-uniform grey, which gave false "identical" pairs. That method is documented in the same JSON history.
- **Conclusion:** no exact or material train/val leakage. One val image (0.5 %) shares its background, not its subject, with train. The original split is kept, and no corrected split is proposed.

### 4.5 Visual annotation review

Selection is in `review_selection.csv`, findings in `review_findings.csv`, sheets in `review_sheets/annotation_review_0…4.jpg`.

- **Selection (systematic, seed 0):**
  - one random val image per class (12);
  - rare classes from train: no_goggle ×2, forklift ×1, no_vest ×1;
  - the 2 images with the most small boxes; the 2 with the largest PPE boxes;
  - the 2 with the most persons (crowding / occlusion proxy);
  - overhead ×2 and side ×1 (AI-assisted labels);
  - the 2 darkest images (mean grayscale);
  - 4 random rule-flagged high-priority suspects.
- After de-duplication, **29 images** were reviewed. That is 2.9 % of images; it is **not** a full verification. The reviewer was the AI assistant, using GT boxes drawn with class codes at 640 px per image.

**Findings:**

| Finding type | Images | Examples |
|---|---:|---|
| ok (labels consistent with the visual evidence) | 15 | Close-ups with helmet/vest/gloves/boots; no_boots on sneakers; no_vest on dark shirts |
| small_objects (labels plausible but unverifiable at ~10 px) | 6 | Atrium with ~40 tiny workers; factory hall; weir wall |
| missing_person_label | 4 | Forklift drivers not labelled Person (2 images); partially visible workers at the frame edge or back of a crowd with no_helmet boxes but no Person box |
| unsupported_label | 1 | no_goggle on a distant overhead worker whose eyes are not resolvable |
| policy_inconsistency | 1 | Night street: road-roller driver labelled (no_helmet) while forklift drivers elsewhere are not |
| ambiguous_label | 1 | no_boots on brown leather footwear resembling work boots |
| rule_flag_confirmed | 1 | Missing-PPE box (hands/arms) extends beyond its worker's Person box |

Also from REPORT-010 §10.4 (24 no_goggle crops): ordinary eyeglasses labelled no_goggle, and one box on a face turned away. 53.6 % of val persons have no eye-region label at all.

### 4.6 Suspect annotation list (`suspect_annotations.csv`; spec §6.6 columns)

| Issue type (rule-based) | Rows | Priority | Rule |
|---|---:|---|---|
| missing_ppe_without_person | 51 | high | A `no_*` box with < 60 % of its area inside any Person box. Either the Person label is missing or the association is impossible. |
| ppe_without_person | 75 | low | A PPE box not inside any Person box. Could be an unworn item or an unlabelled person. |
| extreme_aspect | 15 | medium | Helmet/goggles/gloves/boots (incl. no_*) with w/h > 4 or < 0.2 |
| item_as_large_as_person | 7 | medium | Item box ≥ 90 % of its Person box area |
| duplicate_box / contradictory_pair / item_and_missing_item_on_same_person | 0 / 0 / 0 | — | Same-class IoU ≥ 0.8; opposite classes IoU ≥ 0.5 (helmet/vest/goggles); a single person carrying both an item and its missing class |
| visual_review:* | 14 | high/medium/low | §4.5 |

All rows are `reviewer_status = unreviewed` or `visually reviewed (AI assistant) - needs human confirmation`. **No label was changed.**

### 4.7 Viewpoint metadata (`viewpoint_summary.json`)

- Source: `data/viewpoint_metadata.csv`, labelling method "manual visual inspection of contact-sheet thumbnails" **by an AI assistant**. These are **not independently human-verified** ground truth.
- Overall: frontal 639, side 116, overhead 219, low_angle 13, unclear 13.
- Train: frontal 527, side 84, overhead 166, low_angle 10, unclear 13. Val: frontal 112, side 32, overhead 53, low_angle 3.
- Confound (REPORT-007): frontal and side images are mostly close-ups; overhead images are mostly wide scenes.
- **Reliability:** borderline elevated-vs-frontal and three-quarter-vs-side cases are subjective. A human spot-check is recommended before any viewpoint claim. The labels were not changed.

## 5. Files inspected

All files under `construction-ppe/` (read-only), `data/viewpoint_metadata.csv`, and REPORT-003, REPORT-007 and REPORT-010.

## 6. Files modified / created

**No existing file was modified.** Created:
- `scripts/engineering/dataset_audit.py` (copy in `experiments/dataset_audit/scripts/`);
- in `experiments/dataset_audit/`:
  - `inventory.json`, `image_dimensions.csv`, `boxes.csv`, `class_distribution.csv`, `box_scale_by_class.csv`;
  - `duplicates_exact.csv`, `near_duplicates.csv`, `background_leakage.json`, `background_similar_pairs.csv`;
  - `suspect_annotations.csv`, `review_selection.csv`, `review_findings.csv`, `viewpoint_summary.json`, `audit_summary.json`;
  - `dataset_hash_manifest.csv`, `audit_stdout.log`, `charts/*.png`, `review_sheets/*.jpg`.

## 7. Engineering decisions and alternatives

| Decision | Alternative | Reason |
|---|---|---|
| dHash + DCT hash with a visual check of every candidate | A CNN-embedding similarity | Documented and dependency-free. All 13 candidates were checked by eye. |
| A background-only correlation for scene-level leakage | Whole-image hashes only | Whole-image hashes miss the same background with a different worker (the generated-variant pattern). The masked-hash variant was tried and rejected (degenerates on images whose boxes fill most of the frame). |
| Keep the original split | A corrected split | Leakage is limited to 1 val image (0.5 %) and is background-only. Changing the split would break comparability with every prior result. |
| Suspect list only, no corrections | Auto-fixing labels | Spec §6.6. The label policy (e.g. vehicle operators, eyeglasses) needs a human decision. |

## 8. Actual implementation details

`dataset_audit.py` reads the images (OpenCV decode) and labels, computes every statistic, hashes and rule flags, and writes CSV/JSON/PNG under `experiments/dataset_audit/`. The background-leakage, pair-sheet and review-sheet steps ran as recorded inline steps, with outputs saved in the same folder. Review sheets draw GT boxes with class codes (H, noH, V, noV, G, noG, B, noB, Gg, noGg, P, F).

## 9. Testing methodology

- The structural checks cross-check REPORT-003 and the Phase 0 hash manifest (identical counts).
- Perceptual candidates were all verified visually.
- The visual review is a stratified sample with a fixed seed, and its selection reasons are recorded.
- The dataset hashes were verified after the audit (§10).

## 10. Actual measured results

See §4 for all values. After the audit, `hash_manifest.py verify dataset_manifest.csv` gave changed = 0, missing = 0, and there were no new files.

## 11. Before/after comparison

Not applicable: no change was made. This is a baseline audit.

## 12. Limitations and uncertainty

- The visual review covers 29 images (2.9 %), done by an AI assistant at 640 px. Tiny objects cannot be verified at that resolution.
- The perceptual and background methods can miss near-duplicates with large viewpoint changes.
- Occlusion is not annotated.
- The viewpoint labels are AI-assisted.
- The rule thresholds (60 % containment, aspect limits) are heuristics; flagged rows are candidates, not confirmed errors.

## 13. Known unresolved issues

1. **Labelling-policy decisions needed (human):**
   - Are vehicle operators Person?
   - Do eyeglasses count as goggles?
   - Should no_goggle be labelled when the eyes are not resolvable?
2. 51 high-priority missing-PPE boxes without a Person box need human review.
3. Scale imbalance of the missing-PPE classes. This is a dataset property; addressing it (more close-range negatives, tiling or higher imgsz) is future work.

## 14. Exact reproduction

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
.venv/bin/python scripts/engineering/dataset_audit.py
.venv/bin/python scripts/engineering/hash_manifest.py verify experiments/engineering_phase/baseline/dataset_manifest.csv
```

The background-leakage and review-sheet steps are reproduced by the code recorded in `experiments/engineering_phase/EXECUTION_LOG.md` (Phase 4).

## 15. Conclusion

- The dataset is structurally sound, and there is no material train/val leakage. No stop condition is triggered, and YOLO26m training may proceed on the original split.
- The main quality risks are:
  1. the small scale of the missing-PPE classes;
  2. labelling-policy inconsistencies (vehicle operators, eyeglasses vs goggles, unresolvable eyes);
  3. missing Person boxes for partially visible people.

  These affect model recall and the compliance association. They need human review.

## 16. Recommended next step

Phase 5: YOLO26m readiness and smoke tests (REPORT-013). The audit does not block training. A human pass over the 51 high-priority suspects and the three policy questions is recommended before any corrected dataset version is created (that would be a separate, traceable experiment).
