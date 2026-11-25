# Pre-registration: candidate selection, locked-test protocol and promotion gates (Phases 5–7)

**Written:** 2026-11-23 02:47 IST (first saved 02:47:30; corrected header time only), before any locked-test access. The ledger `qualification/locked_test_access_log.csv` contains only its header (0 accesses).

**Context:**
- On 2026-11-23 at about 02:40 the user chose **Option A**: no further training before the Tuesday deadline.
- Stage 2 (the combined configuration E7 and its seed runs) was cancelled before it started (`training/logs/stage2.log`).
- This file fixes every rule below before the locked test is opened. Nothing in it may be changed after the locked-test results are seen.

## 1. Candidate selection (development data only)

The rule was pre-registered on 2026-11-22 at 19:05 in the docstring of `scripts/accuracy/stage2_combined.py`. That was before any result of E3, E4 or E5 existed.

**Measures, both on dev, protocol v1:**
- **A:** Ultralytics mAP50.
- **B:** the mean of the five missing-PPE recalls at confidence 0.25.

**Eligible models:**
- Eligible: models trained on the 640-image training split (E1, E3, E4, E5).
- Not eligible: the production YOLO26n (`models/trained/best.pt`) and the earlier YOLO26m (`experiments/yolo26m/training/yolo26m_e30_b4`). Both trained on images that are now in the locked test (REPORT-020 §7.5).

**Rule:**
- Select the eligible run that is best on both A and B.
- If no run were best on both, the run best on B (safety-critical recall) would be chosen.

| Run (dev) | A: mAP50 | B: mean missing-PPE recall at 0.25 | Eligible |
|---|---|---|---|
| E1_m640_base | 0.8228 | 0.6615 | yes |
| **E3_m896** | **0.8539** | **0.7216** | yes |
| E4_m640_aug | 0.8321 | 0.6660 | yes |
| E5_m640_clspw | 0.8324 | 0.6673 | yes |
| YOLO26n (production) | 0.7339 | 0.5298 | no (reference only) |
| YOLO26m e30_b4 (earlier) | 0.8311 | 0.6547 | no (reference only) |

**Result:** `E3_m896` is best on both A and B. It is the frozen candidate. No tie-break was needed.

**Dev results are optimistic.** `best.pt` was chosen by the dev fitness during training, so the dev scores carry selection bias.

## 2. Frozen candidate

The frozen candidate, its checkpoint SHA-256 and its configuration are in `qualification/frozen_candidate.json`, written in the same step as this file. The configuration is frozen as follows:

- **Inference size:** 896.
- **Detection confidence:** 0.25 (`inference.confidence_threshold`). **NMS IoU:** 0.5 (`inference.iou_threshold`). Ultralytics predict default head with NMS.
- **Compliance thresholds:** unchanged (`compliance.*` in `configs/settings.yaml`, including the alert threshold `violation_confidence` 0.50).
- **Thresholds in general:** not tuned. The user instructed on 2026-11-23 not to change the application thresholds, and the Phase 5 threshold sweep on dev is descriptive only.

## 3. Locked-test protocol (one qualification session)

1. **Candidate:** `E3_m896` at size 896 is evaluated **once** with `scripts/accuracy/evaluate.py --split test`. The evaluator requires a purpose and the frozen SHA-256.
2. **Reference:** `E1_m640_base` at size 640 is evaluated **once** in the same session.
   - It is the controlled reference: the same recipe and the same 640-image training split, at 640.
   - It serves only to measure the resolution effect on held-out data with a paired image bootstrap.
   - It cannot replace the candidate. Nothing is re-selected on the locked test.
3. **Excluded models:** YOLO26n and YOLO26m e30_b4 are **not** evaluated on the locked test, because they are contaminated. The candidate is compared with YOLO26n on dev only, and that comparison is marked as non-controlled.
4. **Analyses in the same session:** every analysis of the locked-test predictions is part of this one session and is recorded in the ledger. That covers per-class results, the confusion matrix, FP/FN counts, bootstrap confidence intervals, size strata and family strata.
   - Locked-test failure cases are counted and described only.
   - No contact sheets are made from them, and nothing is tuned on them.
5. **No revision after viewing:** no change to the model, thresholds or post-processing after the results are seen. Any later change would turn this set into development data (spec §8).

## 4. Promotion gates (making the candidate the application default)

All gates are measured on the locked test at the application operating point unless stated otherwise. The operating point is confidence 0.25 and NMS IoU 0.5, with greedy same-class matching at IoU ≥ 0.5 (protocol v1). The gates come from spec §0, §8 and §9 and from the 30 fps frame budget in REPORT-016 and REPORT-017.

| Gate | Requirement | Source |
|---|---|---|
| G1 | mAP50 ≥ 0.93 (Ultralytics val, protocol v1) | spec §0 primary target |
| G2 | precision ≥ 0.90 **and** recall ≥ 0.90 at the operating point | spec §0 supporting target |
| G3 | recall ≥ 0.90 for **each** of no_helmet, no_gloves, no_goggle, no_boots, no_vest at the operating point | spec §0 safety-critical target |
| G4 | registry loading validates SHA-256, class mapping and architecture; a missing, corrupt or mismatched checkpoint falls back to YOLO26n; the tests pass | spec §9 |
| G5 | the complete regression suite passes, with no test removed or weakened | spec §9 |
| G6 | real time on the M5 (replay through `LiveFrameProcessor`): inference p95 ≤ 33 ms (30 fps frame budget), 0 stale boxes, 0 processing errors | REPORT-016/017, spec §9 |
| G7 | user data intact: original dataset unchanged; events database and evidence not modified by the programme | spec §0.1 |
| (stretch) | mAP50-95 ≥ 0.80. Reported, not a gate | spec §0 |

**Decision rule:**

- **PROMOTE** only if G1–G7 all pass. The steps are:
  1. Copy the checkpoint to a versioned path with a model card.
  2. Add it to the model registry.
  3. Set it as `model.active`.
  - YOLO26n stays registered as `model.fallback`.
- **NOT PROMOTED** if any of G1–G7 fails:
  - YOLO26n stays the active default and the fallback, and `configs/settings.yaml` is not changed.
  - The candidate is stored as a versioned checkpoint with a model card marked "not promoted". It is not added to the application's model registry.
  - A provisional, non-default registration (spec §9) needs the user's explicit approval.
- **Wording:** no wording may call the candidate production-qualified unless G1–G7 pass. Locked-test numbers are reported as "on this limited, held-out, in-distribution test set (160 images)".
