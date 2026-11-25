# REPORT-023 — Phase 5: model comparison and error analysis (development data only)

**Written:** 2026-11-23, about 03:00–03:10 IST. **Specification:** §7.

**Status:** **Complete.**
- **Candidate:** `E3_m896`, selected by the pre-registered rule and frozen at 02:47:31 (`qualification/frozen_candidate.json`).
- **Thresholds:** application thresholds unchanged, on the user's instruction of 2026-11-23. The threshold trade-off is documented in §7.
- **Locked test:** not accessed during this phase. The ledger contains only its header.

## 1. Objective and scope

Compare the YOLO26n production baseline, the earlier YOLO26m and all Phase 4 candidates on identical development data. Then analyse errors for the safety-critical classes. All numbers come from dev (200 images, 2,961 objects).

## 2. Comparison conditions

| Condition | Value |
|---|---|
| Data | `splits/dev.txt` (sha256 `eb1854d4…`), the original 200-image val set; unchanged labels |
| Evaluator | Protocol v1 (REPORT-020): `scripts/accuracy/evaluate.py` and `scripts/accuracy/compare_candidates.py` |
| Class mapping | 12 classes, identical for all checkpoints (validated by `src/detection/model_registry.py` and the tests) |
| Thresholds | Detection conf 0.25 and NMS IoU 0.5, from `configs/settings.yaml`. The alert threshold `compliance.violation_confidence` is 0.50 |
| Image size | 640 for every model except E3 (896). **E3 is compared as a whole system** (model plus its own inference size). This is marked wherever it matters |

**Non-controlled comparisons:**
- **YOLO26n and YOLO26m e30_b4:** trained on 800 images, which include today's locked test. Dev also selected their best epochs. They are references only.
- **E1 to E5:** trained on the 640-image training split. E1 is the controlled baseline.

## 3. Overall comparison (dev)

| Model | Size | mAP50 | mAP50-95 | P / R at 0.25 | F1 at 0.25 | FP / image | Mean missing-PPE recall at 0.25 | Person recall at 0.25 | Single-image latency in the evaluator (ms)* |
|---|---|---|---|---|---|---|---|---|---|
| YOLO26n production | 640 | 0.7339 | 0.5227 | 0.884 / 0.745 | 0.809 | 1.45 | 0.530 | 0.902 | 10.6 |
| YOLO26m e30_b4 | 640 | 0.8311 | 0.6195 | 0.885 / 0.828 | 0.856 | 1.60 | 0.655 | 0.956 | 29.9 |
| E1_m640_base | 640 | 0.8228 | 0.6076 | 0.884 / 0.825 | 0.854 | 1.60 | 0.662 | 0.963 | 36.8 |
| **E3_m896** | **896** | **0.8539** | **0.6278** | **0.893 / 0.858** | **0.875** | 1.53 | **0.722** | **0.967** | **51.3** |
| E5_m640_clspw | 640 | 0.8324 | 0.6170 | 0.896 / 0.828 | 0.861 | 1.42 | 0.667 | 0.952 | 29.9 |
| E4_m640_aug | 640 | 0.8321 | 0.6127 | 0.904 / 0.825 | 0.862 | 1.30 | 0.666 | 0.956 | 34.2 |

mAP50 and mAP50-95 are from Ultralytics val (conf 0.001, NMS 0.7). The other columns are at the operating point.

\* **Latency caveat:**
- The evaluator latency is a synchronised wall clock per image on MPS (predict plus copy to NumPy), measured right after each training run.
- Three YOLO26m runs at the same 640 size took 29.9–36.8 ms. That spread shows the noise from thermal and background state.
- Runtime is measured properly in Phase 7 (REPORT-024).
- E3's cost at 896 is about 1.5–1.7× that of the 640 models.

Per-class AP50 for every model is in REPORT-022 §5.2. Files: `error_analysis/comparison_dev_vs_E1/comparison.csv` and `.json`.

## 4. Paired image-level bootstrap (B = 1,000, seed 0, dev)

- **Resampling unit:** the image. Both models in a pair use the same resamples.
- **Measure:** the difference "model minus reference".
- **mAP50 here:** the audit evaluator (NMS 0.5). It is a few points below Ultralytics val, but it is the same for both models in a pair.

### 4.1 Against the controlled baseline E1 (`error_analysis/comparison_dev_vs_E1/`)

| Model minus E1 | mAP50 (audit) | Recall at 0.25 | Mean missing-PPE recall at 0.25 |
|---|---|---|---|
| **E3_m896** | **+0.034 [+0.021, +0.048]** | **+0.033 [+0.021, +0.045]** | **+0.060 [+0.034, +0.091]** |
| E4_m640_aug | +0.010 [−0.002, +0.024] | −0.000 [−0.009, +0.009] | +0.004 [−0.021, +0.030] |
| E5_m640_clspw | +0.009 [−0.002, +0.020] | +0.003 [−0.005, +0.011] | +0.006 [−0.015, +0.025] |
| YOLO26m e30_b4 (800 images) | +0.007 [−0.005, +0.019] | +0.003 [−0.005, +0.010] | −0.007 [−0.031, +0.018] |
| YOLO26n production | −0.077 [−0.095, −0.058] | −0.080 [−0.094, −0.066] | −0.131 [−0.165, −0.099] |

**Reading:**
- **Only E3** improves on E1 with intervals that exclude 0, on all three measures. That meets E3's pre-set success criterion (REPORT-022 §4).
- **E4 and E5:** their differences are within resampling noise. They also come from single-seed runs (REPORT-022 §6).
- **E1 and the earlier e30_b4 model agree within noise.** This supports the reproduction (E1 had 20 % less training data).

### 4.2 Candidate against the production model YOLO26n (`error_analysis/comparison_dev_vs_yolo26n/`; non-controlled)

| Model minus YOLO26n | mAP50 (audit) | Recall at 0.25 | Mean missing-PPE recall at 0.25 |
|---|---|---|---|
| **E3_m896** | **+0.111 [+0.090, +0.131]** | **+0.112 [+0.096, +0.131]** | **+0.191 [+0.156, +0.227]** |
| YOLO26m e30_b4 | +0.084 [+0.065, +0.102] | +0.083 [+0.067, +0.096] | +0.125 [+0.096, +0.156] |

**Caveats:**
- **Training data differs.** YOLO26n trained on 800 images and E3 on 640.
- **Selection.** YOLO26n's best epoch was also selected on dev.
- **Effect on the comparison.** Both points favour YOLO26n, so the comparison is conservative against E3.
- **Not on the locked test.** YOLO26n cannot be evaluated there because it is contaminated (REPORT-020 §7.5). This dev comparison is therefore the only one between the candidate and production.

## 5. Per-class results at the operating point (dev; E1 against E3)

| Class (GT) | E1 P / R | E3 P / R | E3 TP / FP / FN |
|---|---|---|---|
| helmet (294) | 0.921 / 0.867 | 0.939 / 0.895 | 263 / 17 / 31 |
| gloves (381) | 0.901 / 0.840 | 0.896 / 0.858 | 327 / 38 / 54 |
| vest (340) | 0.956 / 0.894 | 0.950 / 0.944 | 321 / 17 / 19 |
| boots (481) | 0.822 / 0.794 | 0.824 / 0.836 | 402 / 86 / 79 |
| goggles (139) | 0.957 / 0.957 | 0.964 / 0.971 | 135 / 5 / 4 |
| Person (481) | 0.949 / 0.963 | 0.963 / 0.967 | 465 / 18 / 16 |
| **no_helmet (179)** | 0.801 / 0.676 | 0.796 / **0.765** | 137 / 35 / 42 |
| **no_goggle (82)** | 0.636 / 0.512 | 0.704 / **0.610** | 50 / 21 / 32 |
| **no_gloves (203)** | 0.851 / 0.704 | 0.885 / **0.719** | 146 / 19 / 57 |
| **no_boots (178)** | 0.802 / 0.730 | 0.817 / **0.775** | 138 / 31 / 40 |
| forklift (73) | 0.813 / 0.836 | 0.833 / 0.822 | 60 / 12 / 13 |
| **no_vest (130)** | 0.899 / 0.685 | 0.932 / **0.739** | 96 / 7 / 34 |
| **All (2,961)** | 0.884 / 0.825 | 0.893 / 0.858 | 2,540 / 306 / 421 |

**Missing-PPE recall is far below the 0.90 target** for every class, even on dev: the best is 0.775 and the worst is no_goggle at 0.610.

## 6. Strata

### 6.1 Image family (filename prefix; REPORT-020)

| Model | `source-*` real scenes (59 images, 1,287 objects): mAP50 / R at 0.25 | `ultralytics-ppe-*` generated close-ups (141 images, 1,674 objects): mAP50 / R at 0.25 |
|---|---|---|
| YOLO26n | 0.455 / 0.547 | 0.877 / 0.897 |
| YOLO26m e30_b4 | 0.628 / 0.694 | 0.906 / 0.931 |
| E1 | 0.591 / 0.683 | 0.904 / 0.934 |
| **E3** | **0.670 / 0.744** | **0.922 / 0.945** |
| E5 | 0.657 / 0.685 | 0.911 / 0.938 |
| E4 | 0.606 / 0.684 | 0.916 / 0.933 |

- **Largest gap:** the real-scene family (crowded sites, distant workers). E3 gains most there: +0.079 mAP50 and +0.061 recall over E1.
- **Main weakness:** real scenes remain the main weakness. On generated close-ups, E3 is already above 0.92 mAP50.

### 6.2 Object size (relative area; recall at 0.25)

| Class | tiny (< 0.1 % of image): GT, YOLO26n / E1 / E3 | small (0.1–1 %) | medium (1–10 %) |
|---|---|---|---|
| All | 801: 0.27 / 0.48 / **0.58** | 1,203: 0.88 / 0.94 / 0.95 | 660: 0.97 / 0.97 / 0.97 |
| no_helmet | 84: 0.30 / 0.45 / **0.64** | 46: 0.78 / 0.78 / 0.80 | 49: 1.00 / 0.96 / 0.94 |
| no_gloves | 88: 0.11 / 0.38 / 0.41 | 112: 0.92 / 0.96 / 0.96 | 3: — |
| no_goggle | 54: 0.06 / 0.39 / **0.48** | 28: 0.39 / 0.75 / 0.86 | — |
| no_boots | 43: 0.09 / 0.23 / **0.37** | 106: 0.87 / 0.91 / 0.92 | 29: 0.83 / 0.83 / 0.83 |
| no_vest | 33: 0.00 / 0.06 / 0.18 | 26: 0.46 / 0.69 / 0.85 | 46: 0.98 / 0.98 / 0.96 |

- **Why area bands:** the short-side bands in `size_strata.csv` are measured at each model's own input size, so the same object falls into different bands at 640 and 896. Relative-area bands do not depend on resolution and are used here.
- **Tiny objects:** E3's gain is concentrated on them. Tiny objects remain the dominant failure: no_gloves stays at 0.41 and no_vest at 0.18.
- Files: `evaluation/dev_*/size_strata.csv`.

## 7. Thresholds (development data; no change made)

**User instruction (2026-11-23):** do not change the existing compliance logic or application thresholds. Thresholds are therefore **unchanged**:
- detection confidence 0.25;
- NMS IoU 0.5;
- alert threshold `violation_confidence` 0.50, together with the other compliance thresholds.

This section documents the trade-off on dev so that a future, separately approved decision can be made on evidence.

### 7.1 Detection threshold sweep for E3 (`error_analysis/comparison_dev_vs_E1/threshold_sweep_dev_E3_m896.csv`)

Precision / recall at each detection confidence. The matching is the same as at the operating point (NMS 0.5, IoU 0.5).

| Class (GT) | 0.15 | 0.20 | **0.25 (current)** | 0.35 | 0.40 | 0.50 | 0.60 |
|---|---|---|---|---|---|---|---|
| All (2,961) | 0.851 / 0.870 | 0.874 / 0.863 | **0.892 / 0.858** | 0.920 / 0.841 | 0.932 / 0.833 | 0.950 / 0.809 | 0.960 / 0.787 |
| no_helmet (179) | 0.737 / 0.782 | 0.757 / 0.765 | **0.796 / 0.765** | 0.865 / 0.749 | 0.903 / 0.726 | 0.947 / 0.693 | 0.959 / 0.648 |
| no_gloves (203) | 0.816 / 0.744 | 0.852 / 0.739 | **0.885 / 0.719** | 0.922 / 0.695 | 0.931 / 0.665 | 0.949 / 0.635 | 0.961 / 0.601 |
| no_goggle (82) | 0.642 / 0.634 | 0.676 / 0.610 | **0.704 / 0.610** | 0.783 / 0.573 | 0.868 / 0.561 | 0.946 / 0.427 | 1.000 / 0.232 |
| no_boots (178) | 0.762 / 0.792 | 0.808 / 0.781 | **0.817 / 0.775** | 0.832 / 0.753 | 0.858 / 0.747 | 0.890 / 0.725 | 0.926 / 0.708 |
| no_vest (130) | 0.914 / 0.739 | 0.932 / 0.739 | **0.932 / 0.739** | 0.968 / 0.708 | 0.979 / 0.700 | 0.978 / 0.677 | 0.977 / 0.646 |
| Person (481) | 0.941 / 0.969 | 0.955 / 0.967 | **0.963 / 0.967** | 0.971 / 0.963 | 0.973 / 0.963 | 0.981 / 0.950 | 0.985 / 0.942 |

**Reading:**
- **Best overall F1** is at conf 0.40 (0.880 against 0.875 at 0.25).
- **Why 0.40 is not adopted:** it would cost 2–5 recall points on every missing-PPE class (for example, no_helmet drops from 0.765 to 0.726). The spec forbids raising headline precision at the expense of safety-critical recall.
- **Lower thresholds (0.15–0.20):** these add at most 2 recall points per class, at a 4–6 point precision cost.
- **Conclusion:** the current detection threshold of 0.25 is a defensible balance on dev. Keeping it is consistent with the user's instruction.

### 7.2 Alert threshold (0.50) against detection threshold (0.25): missed violations against false alarms

**How alerts work:**
- The application draws detections at confidence ≥ 0.25.
- It raises a potential violation only for a `no_*` box at confidence ≥ 0.50, and only after the compliance association with a worker.
- The precision and recall of the missing-PPE detections at the two thresholds are therefore:

| E3, dev | no_helmet | no_gloves | no_goggle | no_boots | no_vest |
|---|---|---|---|---|---|
| Recall at 0.25 (detection) | 0.765 | 0.719 | 0.610 | 0.775 | 0.739 |
| Recall at 0.50 (alert) | 0.693 | 0.636 | 0.427 | 0.725 | 0.677 |
| Precision at 0.25 | 0.796 | 0.885 | 0.704 | 0.817 | 0.932 |
| Precision at 0.50 (alert) | 0.947 | 0.949 | 0.946 | 0.890 | 0.978 |
| YOLO26n recall at 0.50 (current production) | 0.492 | 0.503 | 0.037 | 0.657 | 0.600 |

**Reading:**
- **What 0.50 trades:** the alert threshold buys high alert precision (0.89–0.98) at the cost of missed violations. At 0.50, E3 misses about 31 % of no_helmet boxes and 57 % of no_goggle boxes on dev.
- **Effect of lowering it:** lowering the alert threshold would recover 5–18 recall points per class. It would also lower alert precision by 7–24 points.
- **Per-class thresholds:** these could balance the classes, but the compliance logic does not support them and they would need a separate policy decision.
- **Comparison with production:** at the unchanged 0.50 threshold, E3 raises alert recall over the production YOLO26n on every missing-PPE class. no_goggle goes from 0.037 to 0.427.
- **Recommendation (not implemented):** if the user later wants fewer missed violations, consider class-specific alert thresholds chosen on dev, then re-qualify on new, independent data.

### 7.3 Confidence calibration (`error_analysis/calibration/reliability_dev.json`)

**Method:**
- A prediction counts as correct when it is greedily matched to a same-class ground-truth box at IoU ≥ 0.5.
- The table compares precision per confidence bin with the mean confidence in that bin, for E3's missing-PPE predictions on dev.

| Confidence bin | 0.25–0.35 | 0.35–0.45 | 0.45–0.55 | 0.55–0.65 | 0.65–0.75 | 0.75–0.85 | 0.85–0.95 |
|---|---|---|---|---|---|---|---|
| Predictions | 56 | 61 | 44 | 50 | 61 | 126 | 253 |
| Mean confidence | 0.30 | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 | 0.91 |
| Precision | 0.34 | 0.41 | 0.71 | 0.86 | 0.92 | 0.94 | 0.97 |

- **Expected calibration error:** 0.107 for missing-PPE predictions at confidence ≥ 0.25 (all classes: 0.078; E1: 0.093 and 0.076).
- **Calibration:** scores are roughly calibrated below 0.45 and above 0.85, and **under-confident between 0.45 and 0.75** (precision 0.2 above confidence).
- **Interpretation:** the detector score is **not a calibrated probability**. The application and the reports must call it a detector confidence, not a "probability of violation".

## 8. Error analysis (E3 on dev; spec §7)

**Inputs:**
- Manifest: `error_analysis/E3_m896_dev/error_manifest.csv`. It holds 352 safety-critical-class errors at conf 0.25, with annotation IDs `dev/<stem>#L<line>`.
- Contact sheets: `error_analysis/E3_m896_dev/<class>_FN.jpg` and `<class>_FP.jpg`, up to 12 random cases each, seed 0.
- The same analysis for E1 is in `error_analysis/E1_m640_base_dev/` (411 errors).
- **Dev images only. No locked-test example was used.**

### 8.1 False negatives (missed ground truth)

| Class | E1 FN | **E3 FN** | E3 FN < 8 px (at 640) | Median size | What E3 predicted at the missed box (IoU ≥ 0.3) |
|---|---|---|---|---|---|
| no_helmet | 58 | **42** | 23 | 6.6 px | nothing 20; `helmet` 9; poorly localised no_helmet 8; Person 5 |
| no_gloves | 60 | **57** | 39 | 6.8 px | nothing 45; `gloves` 6; poorly localised 6 |
| no_goggle | 40 | **32** | 10 | 9.1 px | nothing 15; poorly localised 12; no_helmet 3; goggles 2 |
| no_boots | 48 | **40** | 21 | 7.7 px | `boots` 18; nothing 14; poorly localised 8 |
| no_vest | 41 | **34** | 11 | 9.1 px | Person 18 (a no_vest box covers the torso); nothing 8; `vest` 8 |
| Person | 18 | **16** | 6 | 10.8 px | nothing 9; poorly localised 7 |

**Main causes, in order:**
1. **Tiny objects.** About half of the missed missing-PPE boxes are under 8 px on the short side at 640 (gloves and hands in crowded scenes are the extreme case).
2. **Present-versus-missing confusion on feet and torsos:**
   - `boots` predicted where `no_boots` is labelled (18);
   - `vest` where `no_vest` is labelled (8);
   - `helmet` where `no_helmet` is labelled (9).
3. **Localisation.** The prediction exists but at IoU 0.3–0.5.

**Examples:**

| Class | Missed box | Size | Predicted instead |
|---|---|---|---|
| no_helmet | `dev/source-150feca69395fa769adccdc8e157e935#L8` | 5.1 px | nothing |
| no_gloves | `dev/source-223442b1ecf2d156710f2b828bb05db2#L19` | 6.8 px | nothing |
| no_gloves | `dev/source-38d248f0e2100035cc7c30a81392baa8#L21` | 11.0 px | `gloves` 0.40, IoU 0.74 |
| no_goggle | `dev/source-49167518cb619cd5c12a8f33872f9b7e#L26` | 6.8 px | nothing |
| no_boots | `dev/source-3f184ae68fc6f7534cd774fed7b212fb#L19` | 7.0 px | no_boots 0.58 at IoU 0.49 (localisation) |
| no_vest | `dev/source-150feca69395fa769adccdc8e157e935#L10` | 8.3 px | Person 0.88 |

### 8.2 False positives (predictions without a same-class ground truth)

| Class | E1 FP | **E3 FP** | Localisation | Wrong class | Background | Duplicate |
|---|---|---|---|---|---|---|
| no_helmet | 30 | **35** | 21 | 6 | 6 | 2 |
| no_gloves | 25 | **19** | 9 | 2 | 8 | 0 |
| no_goggle | 24 | **21** | 19 | 0 | 2 | 0 |
| no_boots | 32 | **31** | 15 | 13 | 3 | 0 |
| no_vest | 10 | **7** | 2 | 4 | 1 | 0 |
| Person | 25 | **18** | 6 | 2 | 9 | 1 |
| All 12 classes | 320 | **306** | 148 | 77 | 74 | 7 |

**Main causes:**
- **Localisation dominates.** A correct class at IoU < 0.5 usually means a tiny box where a 1–2 px offset fails the IoU test.
- **Wrong class:** mostly `no_boots` against `boots` (13 in one direction, 17 in the other).
- **Background:** few (74 of 306). **Duplicates:** rare (7).
- **Contradictions:** a present-PPE box and a missing-PPE box for the same item. They fell from 24 (E1) to 19 (E3).

**Most frequent class confusions (E3):**

| Predicted | Ground truth | Count |
|---|---|---|
| boots | no_boots | 17 |
| no_boots | boots | 13 |
| vest | no_vest | 12 |
| helmet | no_helmet | 9 |
| gloves | no_gloves | 8 |

### 8.3 Ambiguous ground truth

- **Pending review cases:** the Phase 1 review manifest (`annotation_review/review_manifest.csv`, REPORT-019) has 37 suspect boxes in dev. All 178 cases are still **unreviewed**; no human review is claimed.
- **Overlap with misses:** 12 of E3's 42 + 57 + 32 + 40 + 34 + 16 = 221 false-negative boxes are themselves flagged review cases.
- **Overlap by image:** 151 of the 352 errors lie in images that contain at least one flagged box. These are mostly the crowded `source-*` scenes.
- **Consequence:** part of the measured error may therefore be label noise. Its size is unknown until the review is done.

## 9. Decision

1. **Candidate:** `E3_m896`. It is best on both pre-registered measures, and its improvement over E1 has bootstrap intervals that exclude 0.
2. **Frozen:** checkpoint sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`, at image size 896.
3. **Thresholds:** unchanged (detection 0.25, NMS 0.5, alert 0.50). The trade-off is documented in §7 for a future approved decision.
4. **Locked test:** protocol, references and promotion gates pre-registered before any access (`qualification/PREREGISTRATION-phase5-7.md`).

## 10. Limitations

- **Selection bias:** dev selected every model's best epoch, so dev numbers are optimistic.
- **Single seed:** no model was run with more than one seed (REPORT-022 §6).
- **Family mix:** dev has 59 real-scene images and 141 generated images, so the overall numbers are dominated by easy close-ups.
- **Size bands:** the short-side bands are not comparable across input sizes; area bands are used instead.
- **Contact sheets:** they show random samples, not every case. The manifest lists all cases.
- **Latency:** evaluator latencies are noisy. Phase 7 measures runtime properly.

## 11. Files and commands

**Files:**
- New: `error_analysis/comparison_dev_vs_E1/` (with `threshold_sweep_dev_E3_m896.csv`), `error_analysis/comparison_dev_vs_yolo26n/`, `error_analysis/E3_m896_dev/`, `error_analysis/E1_m640_base_dev/`, `error_analysis/calibration/reliability_dev.json`, `error_analysis/logs/`.
- `scripts/accuracy/compare_candidates.py` gained two features:
  - absolute bootstrap intervals from the same resamples, with no extra random draws, so the paired results above are unchanged;
  - a locked-test guard: `--split test` requires `--locked-test-purpose` and writes to the ledger.

```bash
.venv/bin/python scripts/accuracy/compare_candidates.py --split dev --reference dev_E1_m640_base \
  --runs dev_yolo26n_active_baseline dev_yolo26m_e30_b4_baseline dev_E3_m896 dev_E4_m640_aug dev_E5_m640_clspw \
  --out experiments/accuracy_improvement/error_analysis/comparison_dev_vs_E1 --sweep dev_E3_m896
.venv/bin/python scripts/accuracy/compare_candidates.py --split dev --reference dev_yolo26n_active_baseline \
  --runs dev_E3_m896 dev_yolo26m_e30_b4_baseline --out experiments/accuracy_improvement/error_analysis/comparison_dev_vs_yolo26n
.venv/bin/python scripts/accuracy/error_sheets.py --run dev_E3_m896 --out experiments/accuracy_improvement/error_analysis/E3_m896_dev
.venv/bin/python scripts/accuracy/error_sheets.py --run dev_E1_m640_base --out experiments/accuracy_improvement/error_analysis/E1_m640_base_dev
```

**Tests:** the full suite passed (150 of 150) on 2026-11-23 at 02:55.

## 12. Acceptance (spec §7)

| Criterion | Result |
|---|---|
| Overall and per-class comparison | Pass (§3–§6; REPORT-022 §5.2) |
| Traceable errors | Pass (manifest with annotation IDs; contact sheets; §8) |
| False positives and negatives discussed | Pass (§8) |
| Threshold choice documented | Pass: unchanged by instruction; trade-off on dev in §7 |
| Calibration investigated | Pass (§7.3) |
| No locked-test examples used | Pass (ledger header only) |
| REPORT-023 written | This report |

**Readiness for Phase 6:** ready. The frozen candidate, its configuration and the locked-test protocol are fixed.
