# REPORT-021 — Phase 3: Data Expansion, Augmentation and Small-Object Strategy

**Programme:** YOLO26m accuracy improvement (specification §5)
**Date:** 2026-11-20, 01:20–01:35 IST
**Evidence:**
- `experiments/accuracy_improvement/data_audit/{data_source_register.md, resolvability/}`;
- `augmented_samples/`;
- `evaluation/phase3_inference_scale_yolo26m_e30/`;
- `datasets/v2_train_tiles/`;
- `training/{smoke_m_*, logs/, matrix_smoke.yaml, matrix_phase4.yaml}`.

**Status: complete for the parts this phase can decide.**
- No external dataset qualifies, so none was imported.
- Augmentation policies are defined and visually audited.
- Small-object strategies were compared **at inference time** with the existing checkpoint, and their training-time versions are prepared.
- The **training ablations** (higher training resolution, tiles, augmentation, class weighting) form the Phase 4 matrix. Each is a multi-hour MPS run that needs mains power (§11).

---

## 1. Objective and scope

Spec §5:
- assess additional datasets (licence, provenance, class semantics, label quality);
- define conservative augmentation and verify it visually and statistically;
- investigate small-object strategies: resolution, multi-scale, tiling, class-aware weighting, training-derived crops, resolvability of tiny labels.

Dev split only; **the locked test was not used** (access log still empty).

## 2. Additional datasets (`data_audit/data_source_register.md`)

| Candidate | Licence (as published) | Class coverage | Decision |
|---|---|---|---|
| Ultralytics Construction-PPE, earlier documented version (1,416 images, 11 classes) | AGPL-3.0 in the docs; conflicts with the current CC BY 4.0 | No `no_vest`, no `forklift` | Not imported: unlabelled classes would become background; likely image overlap with the current release (locked-test leakage risk); licence conflict |
| SH17 (8,099 images, 17 classes; Ahmad & Rahimi 2024) | CC BY-NC-SA 4.0; Zenodo record restricted; Pexels terms apply | No missing-PPE classes ("hands", "head", "glasses" and "shoes" do not mean no_gloves, no_helmet, no_goggle or no_boots) | Not imported: needs re-labelling; non-commercial share-alike licence |
| Roboflow Universe sets (for example "Worker-Safety") | Varies or not shown | At most 5 of 12 classes | Not imported: partial labels; unclear licence and provenance |

**Key reason, common to all three:** Ultralytics detection training has no per-image "unlabelled class" mask. Any image missing one of our 12 classes teaches the model that class is background. That would directly harm the missing-PPE classes.

**Decision:** proceed with the verified data (spec §5.1). This is recorded as a limitation. Collecting **independent deployment imagery**, labelled to `docs/ANNOTATION_POLICY.md`, is the recommended route.

## 3. Augmentation (`scripts/accuracy/phase3_augmentation_audit.py`, `augmented_samples/`)

### 3.1 Capabilities checked in Ultralytics 8.4.215 (`cfg/default.yaml`, `data/augment.py`)

- **Supported and relevant:** mosaic, scale (a float range or an explicit `(min, max)`), translate, fliplr / flipud, HSV, `multi_scale` (fraction of imgsz), `cls_pw` (class-weight power for imbalance).
- **Built-in blur:** applied only through Albumentations (Blur / MedianBlur / ToGray / CLAHE, each p = 0.01). **Albumentations is not installed** (REPORT-018), so none of the earlier runs used it.
- **`copy_paste`:** works only for segmentation, OBB or semantic labels, **not detection boxes**. Not applicable.
- **Box filter:** Ultralytics drops any augmented box narrower or shorter than 2 px (`box_candidates`, `wh_thr = 2`).

**Semantic validity:**
- Horizontal flip is valid: PPE is left/right symmetric. It is on (0.5), as before.
- Vertical flip and large rotations would create impossible scenes and stay off (flipud 0, degrees 0, shear 0, perspective 0).
- Mixup is not used: it overlays two scenes and is not physically plausible.

### 3.2 Policies and their measured effect on boxes

The training-split dataset was built with the **same code path as `model.train`**; 300 augmented samples per policy, seed 0.

| Policy | imgsz | Boxes per sample | Median short side | Boxes < 4 px | Boxes < 8 px |
|---|---:|---:|---:|---:|---:|
| Reference (letterbox only) | 640 | 14.8 | 28.6 px | 1.8 % | 13.7 % |
| **P0 default** (earlier runs: mosaic 1, scale 0.5, translate 0.1, HSV 0.015 / 0.7 / 0.4) | 640 | 25.5 | 24.2 px | **4.4 %** | **16.1 %** |
| **P1** scale 0.25 (gain 0.75–1.25) | 640 | 22.8 | 28.2 px | 2.5 % | 13.0 % |
| **P2** = P1 + mild colour (HSV 0.01 / 0.4 / 0.3) | 640 | 22.8 | 28.2 px | 2.5 % | 13.0 % |
| P3 = P1 without mosaic | 640 | 14.6 | 27.3 px | 2.4 % | 14.6 % |
| Reference | 1024 | 14.8 | 45.7 px | 0.1 % | 3.5 % |
| P0 default | 1024 | 25.7 | 38.5 px | 1.1 % | 7.6 % |
| P1 / P2 | 1024 | 22.8 | 45.1 px | 0.6 % | 5.0 % |

**Findings:**
- The default policy's random down-scaling (gain down to 0.5) inside mosaic **pushes 2.4× more boxes below 4 px** than the un-augmented images.
- A conservative scale range removes most of that loss.
- Training resolution is the larger lever: < 8 px falls from 13.7 % at 640 to 3.5 % at 1024.
- Colour policy does not change geometry, as expected.

### 3.3 Visual audit

Sheets inspected: `P1_scale_0.25_640/sheet_1.jpg`, `P2_scale_0.25_colour_mild_1024/sheet_2.jpg`; 32 tiles each, available per policy.
- Boxes follow their objects after mosaic, scale, translate and flip: helmets on heads, eye boxes on eyes, Person boxes around people, forklift boxes on vehicles.
- No impossible scene is produced, apart from the usual mosaic composition.
- **Observed artefact, specific to the audit:** at the start of sampling, the mosaic buffer holds few images, so some tiles repeat one image. This does not occur with a full training buffer.

### 3.4 Blur and noise

- No blur or noise policy is introduced. It would need either an isolated new dependency (Albumentations) or custom code.
- The development and test images are sharp, so a gain there is not expected.
- Robustness to motion blur and compression is measured separately as **synthetic robustness tests**, labelled as such (as in REPORT-016). They are not used as a replacement for real test data.

## 4. Are the tiny annotations resolvable?

- Phase 1: of 14,863 boxes, **2,207 have a short side < 8 px at 640 inference, but only 36 do at native resolution**.
- Visual check: 24 random training boxes of no_helmet / no_goggle / no_gloves that are < 8 px at 640 (9–25 px natively), shown at native resolution ×3 (`data_audit/resolvability/tiny_missing_ppe_native_x3.jpg`). AI-assisted judgement, not human review:
  - **about 20 of 24 are judgeable at native resolution** (bare head, bare hand or uncovered eyes clearly visible);
  - about 4 are marginal (hand hidden by a bag; head covering unclear; profile view of the eyes).
- **Conclusion:** the information exists in the native images and is lost when the image is shrunk to 640. That is exactly what resolution and tiling strategies address.

## 5. Small-object strategies at inference time (existing YOLO26m, trained at 640; dev)

`scripts/accuracy/phase3_inference_scale.py`. The audit evaluator gives mAP at conf 0.001 / NMS 0.5; P and R are at conf 0.25.

| Configuration | mAP50 | mAP50-95 | P | R | Recall, GT < 8 px (640 scale) | R real-scene family | R generated family | Duplicate pairs (op) | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Whole image at 640 (current) | 0.8150 | 0.6073 | 0.885 | 0.828 | 0.388 | 0.694 | 0.931 | 42 | 31.8 ms |
| Whole image at 768 | 0.8318 | **0.6117** | 0.888 | 0.845 | 0.440 | 0.726 | 0.936 | 33 | 40.8 ms |
| **Whole image at 896** | **0.8379** | 0.6031 | 0.874 | 0.855 | 0.480 | 0.744 | **0.940** | 39 | 52.9 ms |
| Whole image at 1024 | 0.8340 | 0.5856 | 0.870 | 0.855 | 0.492 | 0.752 | 0.934 | 27 | 66.5 ms |
| Whole image at 1280 | 0.8097 | 0.5432 | 0.844 | 0.841 | 0.489 | 0.753 | 0.909 | 27 | 100.3 ms |
| 640 whole + 2×2 tiles (20 % overlap), merged | 0.8248 | 0.6088 | **0.814** | **0.863** | **0.534** | **0.770** | 0.934 | 0 | 143.8 ms |

Latency is synchronised wall clock per full-resolution dataset image, on battery. Paced, mains-power latency differs (REPORT-016 §10.7).

**Interpretation:**
1. **Higher inference resolution helps small objects** (recall on boxes < 8 px: 0.39 → 0.48 at 896). But a model *trained at 640* loses localisation quality above about 896 (mAP50-95 falls from 0.61 to 0.54 at 1280): a train/test scale mismatch. Hence the training-resolution ablation **E3 (896)** in Phase 4, rather than only changing the inference size.
2. **Tiling** gives the highest small-object and real-scene recall, but costs 4.5× the latency and **7 points of precision** (more false positives from partial objects and background in tiles).
   - Image-level duplicates after merging (edge-touching tile boxes dropped, NMS 0.5, same-class suppression at intersection-over-smaller 0.8): **0 duplicate pairs**.
   - Caveat: the duplicate criterion (same class, IoU ≥ 0.5 or IoS ≥ 0.8) also counts legitimately nested same-class boxes. The 42 pairs at 640 are therefore an upper bound, and the merge removes such pairs by construction.
   - **A frame-level duplicate-event test is still required before tiling could be integrated** (spec §5.3). At about 144 ms per frame (≈ 7 fps), tiling is not a live-video candidate. It remains an option for still-image inspection; that decision belongs to Phase 5.
3. **Real-time budget:** only 640 fits 30 fps (33 ms) on this M5 on battery; 768 is borderline. A higher-resolution model therefore implies a lower analysed frame rate in live mode. This trade-off is measured, not assumed, in Phase 7.

## 6. Training at larger image sizes: memory (smoke tests)

1 epoch on 10 % of the training split (64 images), batch 4, validation on dev. Battery power; durations include validation.

| Run | Ultralytics GPU_mem max | System free memory (min) | Swap before → after | Duration | Feasible for a multi-hour run? |
|---|---:|---:|---|---:|---|
| `smoke_m_768_b4` | 7.66 GB | 38 % | 4.6 GB, no growth during the run | 51.6 s | Yes |
| `smoke_m_896_b4` | 9.67 GB | 32 % | 5.8 GB, no growth during the run | 62.2 s | **Yes, with the runner's memory guard.** Chosen for E3 (same batch as E1, so the BatchNorm statistics are comparable) |
| `smoke_m_1024_b4` | **12.7 GB** (= MPS recommended maximum working set, 12.71 GB) | **13 %** | **8.0 GB** (+2.2 GB) | 83.6 s | **No.** Batch 2 would fit, but would change the BatchNorm statistics: a confounded ablation. Not run |

**Comparison:** the earlier full 640 / batch 4 run kept ≥ 18 % free over 95 min (REPORT-014). Long runs use more memory than 1-epoch smokes, so 896 needs the runner's guard. The guard stops training gracefully when free memory stays below 6 % for 3 samples; `last.pt` is kept for resuming.

## 7. Other small-object options

| Option | Status |
|---|---|
| **Multi-scale training** | Supported (`multi_scale`, fraction of imgsz). It enlarges the largest batches, so on this memory budget it competes with a higher base resolution. Kept as a candidate for the combined run (E7), not a separate ablation |
| **Class-aware weighting** | Supported (`cls_pw`; 0.5 = square-root inverse frequency). Justified by imbalance: training instances no_goggle 219, no_vest 344 vs boots 1,563. **Phase 4 E5** |
| **Training-derived crops (tiles)** | Built: `datasets/v2_train_tiles/` (§8). **Phase 4 E6** |
| **Class-aware sampling (repeating images)** | Not used. The Ultralytics label cache is keyed by file path, so a repeated list entry is not a reliable oversampling mechanism. Tiles and `cls_pw` cover the same need |

## 8. Training-derived tile dataset (`scripts/accuracy/phase3_tile_dataset.py`)

**Source:** **only training-split images** (no dev or locked-test image) with at least one missing-PPE box whose short side is < 12 px at 640. That is **251 of the 640 training images**.

**Construction:**
- Each source image gives a 2×2 grid of native-resolution tiles with 20 % overlap. That is 962 tiles; 42 tiles without any kept box were not written.
- **Labels:** a box is kept, clipped to the tile, when ≥ 30 % of it is inside the tile. 0.3 matches the policy's "about a third of a person is visible" rule.
  - 9,443 boxes kept.
  - 837 partial boxes dropped (Person 301, vest 116, forklift 97, no_vest 84, …). Those become background in their tile: a known label-noise cost of tiling, mainly for large objects.
  - A first build with a 50 % visibility threshold dropped 1,612. It was discarded and rebuilt; it was never used.
- **Result:** the v2 training set has 640 originals (symlinks) + 962 tiles = **1,602 images**. Dev is unchanged; there is **no locked test in v2**.
- **Provenance:** `tiles_manifest.csv` (source image, window, kept and dropped boxes, label SHA-256); `build_summary.json`.

**Visual audit (`v2_train_tiles/sheet_1.jpg`, 16 tiles):** labels align with workers, PPE and forklifts; clipped boxes at tile edges cover the visible parts.

## 9. Files created or modified

| Path | Change |
|---|---|
| `src/training/train.py` | **Modified (minimal, backward-compatible):** `--seed` (default 42 from settings, as before) and `--hyp <yaml>` (extra Ultralytics arguments for a documented experiment). Protected keys (data, project, name, exist_ok, resume, model, pretrained) and unknown keys are rejected. With no `--hyp` and no `--seed`, the training parameters are identical to before. Pre-change copy: `manifests/train.py.before_phase3` (sha256 `98d8cd52…`); new sha256 `d50b77cf…` |
| `tests/test_training_overrides.py` | **New**, 12 tests |
| `scripts/accuracy/{phase3_augmentation_audit.py, phase3_inference_scale.py, phase3_tile_dataset.py, run_matrix.py}` | New |
| `experiments/accuracy_improvement/...` | New evidence (header) |
| `docs/IMPLEMENTATION_LOG.md` | One row appended |
| `experiments/training.log` | Lines appended by the three smoke runs (existing shared log of `train.py`; nothing overwritten) |

`scripts/accuracy/run_matrix.py` is the sequential, resumable experiment runner. For each run it:
- writes the plan (hypothesis, changed and fixed variables, expected trade-offs, success criteria) before training;
- always passes `--no-promote` and a versioned run folder;
- runs one job at a time;
- samples memory, swap and power every 30 s;
- stops gracefully on memory pressure or low battery;
- refuses runs whose arguments mention the locked test;
- evaluates every best checkpoint on dev.

## 10. Tests and integrity

| Item | Result |
|---|---|
| Application test suite | **136 passed**, 0 failed, 0 skipped (124 earlier + 12 new) |
| Integrity (`augmented_samples/verify_end_of_phase3.json`) | Dataset 0 changed, 0 missing, 0 new. Key checkpoints unchanged. Changed protected files are exactly the expected three: `src/training/train.py`, `docs/IMPLEMENTATION_LOG.md`, `experiments/training.log` |
| Locked test | 0 accesses |

## 11. Hardware state and blocker for training

- MacBook Air M5, 16 GB.
- **Battery power, 21 % → 17 % during this phase.**
- Swap grew from 3.7 GB (Phase 0) to 8.0 GB after the 1024 smoke run.
- Phase 4 consists of six ablation runs, then a combined run and extra seeds: on the order of **20 hours of MPS training** (E1 ≈ 80 min, E3 ≈ 150 min, E6 ≈ 200 min, E4 ≈ 80 min, E5 ≈ 80 min, E2 ≈ 160 min, then E7 and seeds).
- **This needs mains power.** The runner refuses to start a full run on battery below 40 %.

## 12. Limitations

- Inference-time comparisons use one checkpoint trained at 640. Training-time strategies are untested until Phase 4.
- Latencies are battery-power numbers.
- The resolvability check is a 24-box, AI-assisted visual sample.
- Blur and noise augmentation was not tested, because of the missing dependency (§3.4).

## 13. Decisions

1. No external data.
2. Augmentation candidates: P0 (default, baseline) and **P2** (scale 0.25 + mild colour) for E4.
3. Training resolution 896 at batch 4 for E3; 1024 excluded on memory.
4. Tiles (v2) for E6; `cls_pw` 0.5 for E5; longer schedule for E2.
5. Tiling is not a live candidate. Frame-level duplicate tests would be required before any tiled integration.

## 14. Acceptance criteria (spec §5)

| Criterion | Status |
|---|---|
| Source licences documented | **PASS** (`data_source_register.md`) |
| Original data unchanged | **PASS** (0 changed / 0 missing / 0 new) |
| Augmented samples visually audited | **PASS** (§3.3; tile audit §8) |
| Small-object strategies compared | **PASS for inference-time strategies** (§5) and for memory feasibility (§6). **Training-time strategies are prepared** and run as the Phase 4 matrix (spec §6.2 lists them there), with results in REPORT-022 |
| REPORT-021 written | **PASS** |

## 15. Next-phase readiness

**Phase 4 is ready to run:** matrix `training/matrix_phase4.yaml` (E1 → E3 → E6 → E4 → E5 → E2), runner tested on the smoke matrix.

**Blocked only by power.** Training starts automatically when mains power is detected (§16).

## 16. Hand-off to Phase 4

A watcher waits for **mains power** and then launches the runner under `caffeinate`. While on battery it performs no work and does not prevent sleep. Progress is visible in:
- `experiments/accuracy_improvement/training/matrix_status.json`;
- `training/logs/`.
