# REPORT-022 — Phase 4: YOLO26m training experiment matrix

**Written:** 2026-11-23, about 02:50–03:10 IST. **Specification:** `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` §6.

**Status:** **Complete, with documented reductions.**
- Four controlled runs were trained and evaluated on dev: E1 baseline, E3 resolution 896, E4 conservative augmentation and E5 class weighting.
- Three planned items were **not run** because of the user's Tuesday deadline (§7):
  - E2, longer training;
  - E6, tiling;
  - E7, the combined configuration with 3 seeds.
- On 2026-11-23 at about 02:40 the user chose to stop training and use E3 as the candidate ("Option A").
- Every run uses a single seed (42). Seed-to-seed variation was **not measured**; the uncertainty is stated in §6.

## 1. Objective and scope

**Objective:** find which hardware-feasible change to the earlier YOLO26m recipe improves detection of missing PPE, measured on dev only. Each change is a controlled ablation against a reproduced baseline (spec §6.1–6.2).

**In scope:**
- training on the 640-image training split defined in REPORT-020;
- dev evaluation with protocol v1;
- hardware safeguards (spec §6.3).

**Out of scope:**
- the locked test (Phase 6);
- threshold changes (the user instructed on 2026-11-23 not to change application thresholds);
- architecture or dependency changes.

## 2. Environment and hardware state

| Item | Value (from run logs and `training_metadata.json`) |
|---|---|
| Machine | MacBook Air, Apple M5, 16 GB unified memory, fanless; macOS 27.0.1 (arm64) |
| Software | Python 3.12.16, torch 2.15.0, Ultralytics 8.4.215 (uv virtual environment `.venv`) |
| Acceleration | MPS. Confirmed in every training log (`Ultralytics 8.4.215 … torch-2.15.0 MPS (Apple M5)`) |
| Mixed precision | **Off in practice.** `amp=True` is in the arguments, but Ultralytics' `check_amp` returns False on `mps` ("AMP only used on accelerator devices", `ultralytics/utils/checks.py`), so training ran in FP32 |
| Guards (`scripts/accuracy/run_matrix.py`) | One job at a time. Every 30 s it samples memory pressure, swap, power source, battery and macOS thermal state. Rules: SIGSTOP at thermal state "serious", SIGCONT at "nominal"; stop at "critical"; pause on battery; stop if free memory < 6 % for 3 consecutive samples; `caffeinate -s` |
| Thermal state during all runs | Only "nominal" (0) and "fair" (1) were recorded. "Serious" never occurred |

## 3. Fixed configuration (all runs)

- **Architecture and weights:** YOLO26m, pretrained weights `models/pretrained/yolo26m.pt`, sha256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7`.
- **Data:** `experiments/accuracy_improvement/datasets/v1_original_labels/dev.yaml` (sha256 prefix `954b928ed085516d`). It trains on `images/train` (640 images) and validates on `images/dev` (200 images, the original val set). Labels are unchanged (symlinks to `../construction-ppe/`).
- **Split lists (sha256):**
  - `splits/train.txt` `6d9138035fd2665e768e0b4beed7d01e72999771c9e6cee1591085bde649f70f`
  - `splits/dev.txt` `eb1854d404cfe55a27398655b2dde8e3655dfe3321f5d059f808c43b6b024ae9`
  - `splits/test.txt` `cbc2ef25b8e25f26f1b57f0c14c5ecfa8d43e81e9328371742d21f783aeef5c2`
- **Training settings:**
  - 30 epochs, patience 15, batch 4, seed 42, `deterministic=True`, 4 workers, no cache;
  - optimizer `auto`, which resolves to AdamW lr 0.000625 for this nominal batch;
  - lrf 0.01, momentum 0.937, weight decay 0.0005, 3 warm-up epochs;
  - mosaic 1.0 with `close_mosaic` 10, fliplr 0.5, translate 0.1;
  - Ultralytics 8.4.215 defaults otherwise.
- **Locked test:** every run's `args.yaml` was checked by the runner for any reference to `images/test`. None was found, and the ledger still has 0 accesses at the end of Phase 4.
- **Checkpoints:** every run used `--no-promote` and its own folder. No checkpoint was overwritten.

## 4. Experiments (hypotheses were written before training; see `training/matrix_phase4.yaml`)

| Run | Changed variable | Hypothesis (short) | Pre-set success criterion |
|---|---|---|---|
| **E1_m640_base** | Training data 800 → 640 images (locked test removed); otherwise the earlier recipe | Reproduces the earlier dev mAP50 of 0.831, minus the effect of 20 % less data | Dev mAP50 within about 0.03 of 0.831; becomes the controlled baseline |
| **E3_m896** | imgsz 640 → 896 (training and evaluation) | Makes tiny missing-PPE boxes resolvable (13.7 % of training boxes are < 8 px at 640) | Dev mAP50 and missing-PPE recall above E1, with a paired-bootstrap CI that excludes 0; latency measured |
| **E5_m640_clspw** | `cls_pw` 0.0 → 0.5 (square-root inverse-frequency class weights) | Raises the learning signal for rare classes (no_goggle 219, no_vest 344 training instances) | Missing-PPE recall above E1 without a larger precision loss |
| **E4_m640_aug** | scale 0.5 → 0.25; hsv_h 0.015 → 0.01, hsv_s 0.7 → 0.4, hsv_v 0.4 → 0.3 | Stops augmentation from shrinking tiny objects below resolvability; keeps PPE colours realistic | Dev missing-PPE recall and mAP50 at least equal to E1 |

### 4.1 Run records

| Run | Wall time | Active GPU time | Epochs / best epoch | Peak GPU memory (Ultralytics) | Lowest free system memory / max swap | Interruptions |
|---|---|---|---|---|---|---|
| E1 | 3 sessions: 26 min (2026-11-20), 13 min + 57 min (2026-11-22) | about 1.6 h | 30 / 30 | 6.72 GB | 14 % / 6.5 GB | Stopped after epoch 7 (overheating concern, rc −15; CONTINUATION-001 §7). Resumed at epoch 8, stopped for the deadline re-plan, resumed at epoch 12 |
| E3 | 3 h 22 m 38 s | about 2 h 33 m | 30 / 29 | 10.8 GB | 3 % (1 of 305 samples < 6 %) / 6.6 GB | User pauses (SIGSTOP) 20:16–20:56 and 20:56–21:06 (49 min) |
| E5 | 1 h 20 m 25 s | about 1 h 15 m | 30 / 30 | 6.83 GB | 20 % / 6.4 GB | Battery guard: suspended 23:59:10–00:04:34 (charger disconnected) |
| E4 | 1 h 17 m 03 s | about 1 h 17 m | 30 / 24 | 6.83 GB | 18 % / 3.8 GB | None |

- **Times:** wall times are from `training/logs/runner_phase4.log` and include the dev evaluation.
- **E1 resumes:** E1 was resumed from `weights/last.pt` twice. Ultralytics restores weights, optimizer, EMA and epoch, but not the data-loader random state, so E1 is reproducible in configuration but not bit-for-bit.
- **Logs and curves kept:** per-epoch curves are in `training/<run>/results.csv` and `results.png`. Monitor samples are in `training/logs/<run>_monitor.csv`.

### 4.2 Checkpoints (sha256 of `weights/best.pt`)

| Run | best.pt | last.pt | args.yaml |
|---|---|---|---|
| E1_m640_base | `13c71d3024306cf889033762dea6aaa9352be9abaa4aa6a6a83bad5d275c815e` | `19bdebc3…1b723a08` | `6117ecbfb785251f…` |
| **E3_m896** | **`590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`** | `a4e66c02…8c002a1ef` | `05e614daa4728ee8…` |
| E4_m640_aug | `973f04c98c71d59fe3da6bce05e028ba892f5197c12c9d985eb45d775f239267` | `93db3861…358e27953` | `0970be6ddfbf88ef…` |
| E5_m640_clspw | `b1c162ce69e9875f86195a532e0a881e7643930d1a6c6bfd5c009bebd5463f7b` | `2e938d26…94b237d0` | `b1be258b7e89b265…` |

## 5. Results on dev (protocol v1, REPORT-020)

**Denominators:** dev = 200 images and 2,961 ground-truth objects. Per-class instance counts are in §5.2.

**Metric definitions:**
- **Ultralytics P / R / mAP:** Ultralytics val at conf 0.001 and NMS IoU 0.7. P and R are taken at the confidence of maximum F1.
- **Operating point:** the application settings, conf 0.25 and NMS IoU 0.5, with greedy same-class matching at IoU ≥ 0.5.
- **Missing-PPE recall:** recall at the operating point for each of no_helmet, no_gloves, no_goggle, no_boots and no_vest.

**Caveats:**
- **Selection bias:** `best.pt` of every run was chosen by dev fitness, so dev results are optimistic.
- **Contaminated references:** YOLO26n and the earlier YOLO26m e30 trained on 800 images, which include today's locked test. They are shown as references only, and their training data is not the same as E1–E5 (a non-controlled comparison).

### 5.1 Headline

| Model | Image size | P | R | mAP50 | mAP50-95 | P / R at 0.25 | F1 at 0.25 | FP / image at 0.25 | Mean missing-PPE recall |
|---|---|---|---|---|---|---|---|---|---|
| YOLO26n production (reference) | 640 | 0.832 | 0.681 | 0.7339 | 0.5227 | 0.884 / 0.745 | 0.809 | 1.45 | 0.530 |
| YOLO26m e30_b4 earlier (reference) | 640 | 0.891 | 0.777 | 0.8311 | 0.6195 | 0.885 / 0.828 | 0.856 | 1.60 | 0.655 |
| E1_m640_base | 640 | 0.885 | 0.766 | 0.8228 | 0.6076 | 0.884 / 0.825 | 0.854 | 1.60 | 0.662 |
| **E3_m896** | **896** | **0.922** | **0.796** | **0.8539** | **0.6278** | 0.893 / **0.858** | **0.875** | 1.53 | **0.722** |
| E5_m640_clspw | 640 | 0.891 | 0.781 | 0.8324 | 0.6170 | 0.896 / 0.828 | 0.861 | 1.42 | 0.667 |
| E4_m640_aug | 640 | 0.892 | 0.774 | 0.8321 | 0.6127 | 0.904 / 0.825 | 0.862 | 1.30 | 0.666 |

**Missing-PPE recall at the operating point:**

| Model | no_helmet (179) | no_gloves (203) | no_goggle (82) | no_boots (178) | no_vest (130) |
|---|---|---|---|---|---|
| YOLO26n | 0.615 | 0.567 | 0.171 | 0.674 | 0.623 |
| YOLO26m e30_b4 | 0.715 | 0.700 | 0.476 | 0.691 | 0.692 |
| E1 | 0.676 | 0.704 | 0.512 | 0.730 | 0.685 |
| **E3** | **0.765** | **0.719** | **0.610** | **0.775** | **0.739** |
| E5 | 0.721 | 0.680 | 0.524 | 0.719 | 0.692 |
| E4 | 0.704 | 0.680 | 0.512 | 0.742 | 0.692 |

### 5.2 Per-class AP50 (Ultralytics val)

| Class (dev instances) | YOLO26n | m e30 | E1 | **E3** | E5 | E4 |
|---|---|---|---|---|---|---|
| helmet (294) | 0.825 | 0.915 | 0.900 | **0.924** | 0.912 | 0.906 |
| gloves (381) | 0.793 | 0.889 | 0.875 | 0.888 | 0.881 | 0.880 |
| vest (340) | 0.887 | 0.920 | 0.916 | **0.955** | 0.936 | 0.906 |
| boots (481) | 0.771 | 0.849 | 0.842 | **0.869** | 0.846 | 0.849 |
| goggles (139) | 0.924 | 0.967 | 0.977 | 0.971 | 0.984 | 0.967 |
| Person (481) | 0.940 | 0.975 | 0.979 | 0.982 | 0.978 | 0.982 |
| no_helmet (179) | 0.652 | 0.756 | 0.720 | **0.792** | 0.758 | 0.763 |
| no_goggle (82) | 0.148 | 0.530 | 0.567 | **0.667** | 0.545 | 0.598 |
| no_gloves (203) | 0.620 | 0.765 | 0.748 | **0.773** | 0.754 | 0.736 |
| no_boots (178) | 0.748 | 0.805 | 0.802 | **0.819** | 0.797 | 0.806 |
| forklift (73) | 0.807 | 0.848 | 0.822 | 0.835 | 0.846 | 0.859 |
| no_vest (130) | 0.692 | 0.753 | 0.727 | **0.771** | 0.751 | 0.733 |

### 5.3 Paired image-level bootstrap on dev

- **Method:** B = 1,000 resamples of the 200 dev images, seed 0, the same resample for both models (`scripts/accuracy/compare_candidates.py`).
- **Measure:** the difference "run minus reference". mAP50 here is the audit-evaluator mAP50 at NMS 0.5, so it differs slightly from Ultralytics val.
- **Output:** `error_analysis/comparison_dev_vs_E1/bootstrap_vs_reference.json`.

| Run minus E1 | mAP50 (audit) [95 % CI] | Recall at 0.25 | Mean missing-PPE recall at 0.25 |
|---|---|---|---|
| **E3_m896** | **+0.034 [+0.021, +0.048]** | **+0.033 [+0.021, +0.045]** | **+0.060 [+0.034, +0.091]** |
| E5_m640_clspw | +0.009 [−0.002, +0.020] | +0.003 [−0.005, +0.011] | +0.006 [−0.015, +0.025] |
| E4_m640_aug | +0.010 [−0.002, +0.024] | −0.000 [−0.009, +0.009] | +0.004 [−0.021, +0.030] |
| YOLO26m e30_b4 (reference, 800 images) | +0.007 [−0.005, +0.019] | +0.003 [−0.005, +0.010] | −0.007 [−0.031, +0.018] |
| YOLO26n production (reference) | −0.077 [−0.095, −0.058] | −0.080 [−0.094, −0.066] | −0.131 [−0.165, −0.099] |

### 5.4 Assessment against the pre-set success criteria

| Run | Criterion | Outcome |
|---|---|---|
| E1 | Dev mAP50 within about 0.03 of 0.831 | **Met:** 0.8228 (−0.008). The bootstrap difference against the earlier e30_b4 run includes 0 |
| E3 | Dev mAP50 and missing-PPE recall above E1, with a paired-bootstrap CI that excludes 0; latency measured | **Met** on all three measures. Latency is about 1.5–1.7× E1 in the evaluator and is measured properly in Phase 7 |
| E5 | Missing-PPE recall above E1 without a larger precision loss | **Not established.** The mean is +0.006 but the CI includes 0. Per class: no_helmet +0.045, no_gloves −0.024, no_boots −0.011. Precision is not lower |
| E4 | Dev missing-PPE recall and mAP50 at least equal to E1 | **Met as point estimates** (mAP50 +0.009, mean missing-PPE recall +0.005), but within noise. Precision at the operating point rose (0.904 against 0.884; FP 260 against 320) |

The pre-registered stage-2 rule compares point estimates. Under it, both E4 and E5 would have been added to E7 (§7).

## 6. Seeds and uncertainty

- **One seed per configuration.** Every run used seed 42. The spec asks for at least 3 seeds for the leading candidate "if practical". Three E7 seeds at 896 px (about 2.5 h each) were scheduled, then cancelled for the deadline (§7).
- **Seed variance not estimated.** The paired bootstrap above captures only test-image sampling. It does not capture training randomness. Differences of about 0.01 mAP50 between single-seed runs (E4 and E5 against E1) must be treated as **unresolved**.
- **Size of the E3 gain:** E3's improvement over E1 is about 3× larger than the E4 and E5 differences and is consistent across 10 of 12 classes (§5.2). It is the only effect this report treats as established on dev. Even so, it is a single-seed result.
- **Reproducibility evidence:** E1 (640 images) reached 0.8228 against 0.8311 for the earlier e30_b4 run (800 images, same recipe). This matches the E1 hypothesis (within 0.03) and is the only reproducibility evidence available.

## 7. Planned experiments not run (deadline)

| Item | Plan | Status | Reason and consequence |
|---|---|---|---|
| E2 longer training | 60 epochs, patience 15 (about 2.7 h) | **Not run** | Deferred at the 2026-11-22 19:00 re-plan (`training/matrix_phase4_deferred.yaml`). Whether training beyond 30 epochs helps remains unknown. E3's best epoch was 29 of 30, so a longer schedule may still help at 896 |
| E6 small-object tiling | 962 training tiles (`datasets/v2_train_tiles`, REPORT-021) (about 3.3 h) | **Not run** | Deferred at the same re-plan. Inference-time tiling had already been ruled out for live use (144 ms per frame, precision −0.07; REPORT-021) |
| E7 combined configuration | 896 + E4 augmentation + `cls_pw` 0.5. Both E4 and E5 met the pre-registered stage-2 rule (gain ≥ 0.005 on mAP50 with no loss on mean missing-PPE recall); seeds 42, 0 and 1 (about 7.7 h) | **Cancelled before start** | User decision, 2026-11-23 about 02:40 (Option A, Tuesday deadline). `stage2_combined.py` was terminated at 02:43:27 while still waiting; no `stage2_decision.json` exists. Whether the augmentation and class weighting add to the resolution gain is untested |
| Seeds for the candidate | 3 seeds | **1 seed** | As above. Uncertainty stated in §6 |

**Operational note:**
- Stage 2 would not have started on its own at 01:57. Its check `pgrep -f run_matrix.py` also matched the command line of an unrelated monitoring shell, which contained that text.
- This had no effect on the results, because the user cancelled stage 2 before any E7 run was due.
- The same pattern caused the failed first pause attempt on 2026-11-22 (CONTINUATION-001). Exact PIDs are used for process control.

## 8. Hardware safeguard outcomes

- **Thermal:** state 0–1 only. No SIGSTOP from the thermal guard.
- **Battery:** the battery guard suspended E5 once for 5 min 24 s and resumed it on mains power, as designed.
- **Memory:**
  - E3 at 896 / batch 4 is the heaviest configuration: 10.8 GB reported GPU memory, and free system memory fell to 3 % in one sample (the guard needs 3 consecutive samples below 6 %).
  - Resolutions above 896 at batch 4 are not feasible on this Mac (smoke test at 1024: 12.7 GB, REPORT-021).
- **Overheating concern (2026-11-20):** E1 was stopped by hand. No thermal event was logged, and the guards above were added afterwards (CONTINUATION-001 §7).

## 9. Files

**Created in Phase 4:**
- run folders `training/E1_m640_base`, `E3_m896`, `E4_m640_aug`, `E5_m640_clspw`, each with weights, `args.yaml`, `results.csv` and plots;
- `training/configs/*.plan.json` and `*.hyp.yaml`;
- `training/logs/*` (training logs, monitor CSVs, `runner_phase4.log`, `stage2.log`);
- `training/matrix_status.json`;
- dev evaluations `evaluation/dev_E*`.

**Scripts:**
- `scripts/accuracy/run_matrix.py`;
- `scripts/accuracy/stage2_combined.py` (stage 2 cancelled; kept for the record).

**Modified earlier, unchanged in Phase 4:**
- `src/training/train.py` (`--seed`, `--hyp`; pre-change copy in `manifests/train.py.before_phase3`);
- `tests/test_training_overrides.py`.

**Not modified:** the original dataset, `models/trained/best.pt`, the earlier YOLO26m checkpoint, compliance rules, thresholds, the events database and evidence.

## 10. Commands

```bash
# queue (E1 -> E3 -> E5 -> E4), guarded, sequential, resumable
nohup caffeinate -s .venv/bin/python scripts/accuracy/run_matrix.py experiments/accuracy_improvement/training/matrix_phase4.yaml \
  >> experiments/accuracy_improvement/training/logs/runner_phase4.log 2>&1 &
# equivalent single run (example: E3)
.venv/bin/python -m src.training.train --weights models/pretrained/yolo26m.pt \
  --data experiments/accuracy_improvement/datasets/v1_original_labels/dev.yaml --epochs 30 --batch 4 --imgsz 896 --seed 42 \
  --no-promote --project experiments/accuracy_improvement/training --name E3_m896
# dev evaluation (run automatically by the runner)
.venv/bin/python scripts/accuracy/evaluate.py --weights experiments/accuracy_improvement/training/E3_m896/weights/best.pt \
  --split dev --imgsz 896 --out experiments/accuracy_improvement/evaluation/dev_E3_m896
```

## 11. Tests

- Training-override tests: `tests/test_training_overrides.py`, 12 tests, part of the full suite.
- Full suite on 2026-11-23 at 02:55: **150 passed, 0 failed** in 16.1 s (`qualification/tests/pytest_full_20261123-0255.log`).

## 12. Decisions

1. **Candidate: `E3_m896`** (896 px). It is best on both pre-registered selection measures (dev mAP50 and mean missing-PPE recall); see `qualification/PREREGISTRATION-phase5-7.md` §1.
2. **Frozen:** 2026-11-23 02:47:31 (`qualification/frozen_candidate.json`, sha256 `590d7d6e…6b60e6`).
3. **Stage 2 (E7 and its seeds), E2 and E6:** not run (§7).
4. **Thresholds:** unchanged.

## 13. Acceptance (spec §6)

| Criterion | Result |
|---|---|
| Every run reproducible | **Partly.** Configurations, seeds, data and split hashes, and pretrained hash are saved. E1 was resumed twice (not bit-reproducible) |
| Configurations and hashes saved | Pass (§3, §4.2) |
| No overwrite | Pass (versioned run folders, `--no-promote`) |
| Curves retained | Pass (`results.csv`, `results.png` per run) |
| ≥ 3 seeds for the leading candidate if practical | **Not met:** 1 seed. Documented as a deadline limitation (§6, §7) |
| REPORT-022 written | This report |

**Readiness for Phase 5:** ready. The candidate is selected and frozen; dev comparison and error analysis follow in REPORT-023.
