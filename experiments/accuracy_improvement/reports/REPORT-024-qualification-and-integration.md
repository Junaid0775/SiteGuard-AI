# REPORT-024 — Phases 6 and 7: locked-test qualification and controlled application integration

**Written:** 2026-11-23, about 03:15–04:00 IST. **Specification:** §8 and §9. **Pre-registration:** `qualification/PREREGISTRATION-phase5-7.md` (sha256 `e0b3d97c4e640f24926f5ff628e6dd3bce4c0c7dd03e9dd1a68ae6c525cbec2c`, recorded before the first access in `qualification/preregistration_hashes.txt`).

**Result in one line:** the frozen candidate `E3_m896` (YOLO26m, 896 px) **does not pass the promotion gates**.
- Locked-test mAP50 is 0.847, against a target of 0.93.
- Precision and recall at the operating point are 0.885 and 0.862, against targets of 0.90.
- Missing-PPE recall is 0.52–0.80, against a target of 0.90 for each class.

**Decision: not promoted.**
- YOLO26n stays the active model and the automatic fallback.
- The candidate is stored as a separate, versioned, validated checkpoint with a model card. It is **not** registered in the application.

## Part A — Phase 6: locked-test qualification

### A1. Protocol actually followed

| Step | Evidence |
|---|---|
| Candidate selected on dev by a pre-registered rule | `PREREGISTRATION-phase5-7.md` §1; REPORT-023 |
| Candidate frozen before any test access | `qualification/frozen_candidate.json`: frozen at 02:47:31, checkpoint sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`, inference size 896, conf 0.25, NMS IoU 0.5 |
| Single session: candidate plus one pre-registered controlled reference (E1 at 640) | Ledger rows 3–4 |
| Contaminated checkpoints (YOLO26n, YOLO26m e30_b4) not evaluated on the locked test | Ledger contains only E3 and E1 |
| No revision after viewing | No model, threshold or post-processing change after 03:11. The candidate stored for Phase 7 is byte-identical (same sha256) |

**Ledger** (`qualification/locked_test_access_log.csv`, 8 rows):

| Row | Time | What | Data read? |
|---|---|---|---|
| 1 | 03:09:27 | E3 evaluation, **failed** (Ultralytics required a `train:` key in the YAML) | **No.** It failed before the dataloader was built; see `qualification/locked_test_access_notes.md` |
| 2 | 03:09:28 | E1 evaluation, **failed** (same cause) | No |
| 3 | 03:11:06 | E3 evaluation, completed | Yes |
| 4 | 03:11:32 | E1 evaluation, completed | Yes |
| 5–6 | 03:12:12 | Paired bootstrap and alert-threshold analysis of the saved predictions (`compare_candidates.py --split test`) | Labels and predictions only |
| 7 | 03:15:09 | False-negative cause counts for E3 (counts only, no images rendered) | Labels and predictions only |
| 8 | 03:15:27 | Repeat of row 7: row 7 had a size-scaling bug (sizes were in native pixels, not at 640). The counts are identical | Labels and predictions only |

**Fix for the failed attempts:** `evaluate.py` now writes a derived `_locked_test_eval.yaml` with an empty `train:` key. `locked_test.yaml` is unchanged (sha256 prefix `163374a94413e0a9`, as recorded in REPORT-020). A pre-change copy is in `manifests/evaluate.py.before_phase6_fix`.

**What the locked test is:**
- 160 images and 2,480 objects, held out as whole groups from the original training set (REPORT-020).
- 47 real-scene images (`source-*`, 1,154 objects) and 113 generated close-ups (`ultralytics-ppe-*`, 1,326 objects).
- **In-distribution:** the same dataset, generator and photographers. It is **not** independent site imagery. Results must be quoted as "on this limited, held-out, in-distribution test set (160 images)".

### A2. Headline results (locked test)

| Metric | Definition | **E3_m896 (candidate, 896)** | E1_m640_base (reference, 640) |
|---|---|---|---|
| mAP50 | Ultralytics val, conf 0.001, NMS 0.7 | **0.8473** | 0.8275 |
| mAP50-95 | same | **0.6443** | 0.6209 |
| Precision / recall | Ultralytics, at max-F1 confidence | 0.9135 / 0.7819 | 0.8907 / 0.7658 |
| mAP50 (audit evaluator, NMS 0.5), 95 % CI | image bootstrap, B = 1,000 | 0.832 [0.794, 0.868] | 0.812 [0.772, 0.851] |
| **Precision at the operating point** | conf 0.25, NMS 0.5, greedy same-class IoU ≥ 0.5; 95 % CI | **0.885 [0.863, 0.906]** | 0.898 [0.879, 0.916] |
| **Recall at the operating point** | same | **0.862 [0.832, 0.890]** | 0.835 [0.800, 0.868] |
| F1 at the operating point | | 0.873 | 0.866 |
| TP / FP / FN at the operating point | denominator 2,480 ground-truth objects | 2,137 / 278 / 343 | 2,072 / 235 / 408 |
| FP per image | 160 images | 1.74 | 1.47 |
| FP types | localisation / background / wrong class / duplicate | 142 / 73 / 60 / 3 | 126 / 53 / 52 / 4 |
| Contradiction pairs | present and missing box for the same item | 20 | 8 |
| Person recall at 0.25 | 401 Person boxes | 0.978 | 0.980 |

**Paired difference E3 − E1 on the locked test** (B = 1,000, seed 0, image resampling; `qualification/locked_test_analysis/bootstrap_vs_reference.json`):

| Measure | Difference | 95 % CI |
|---|---|---|
| mAP50 (audit) | +0.021 | [+0.003, +0.040] |
| Recall at 0.25 | +0.026 | [+0.016, +0.038] |
| Mean missing-PPE recall at 0.25 | +0.051 | [+0.022, +0.084] |

**Reading:**
- **The resolution gain holds on held-out data.** The improvement seen on dev reproduces, with intervals that exclude 0, though it is smaller than on dev (mAP50 +0.021 here, +0.034 on dev).
- **Dev and test agree.** Candidate dev mAP50 0.854 against test 0.847.
- **Precision cost.** E3 pays for its recall with lower precision: 278 FPs against 235, and 20 contradiction pairs against 8.

### A3. Missing-PPE recall (safety-critical target ≥ 0.90 per class)

| Class (locked-test GT) | E3 recall at 0.25 [95 % CI] | E1 recall at 0.25 | E3 precision at 0.25 | E3 recall at the **alert** threshold 0.50 | E3 alert precision at 0.50 |
|---|---|---|---|---|---|
| no_helmet (142) | **0.739** [0.639, 0.835] | 0.676 | 0.814 | 0.648 | 0.911 |
| no_gloves (183) | **0.650** [0.551, 0.752] | 0.650 | 0.856 | 0.585 | 0.947 |
| no_goggle (46) | **0.522** [0.375, 0.691] | 0.413 | 0.800 | 0.348 | 0.941 |
| no_boots (108) | **0.796** [0.680, 0.918] | 0.815 | 0.748 | 0.741 | 0.909 |
| no_vest (93) | **0.688** [0.554, 0.818] | 0.591 | 0.941 | 0.645 | 0.984 |
| Mean | 0.679 | 0.629 | | | |

**No class reaches 0.90**, at the detection threshold or at the alert threshold. The intervals are wide (46–183 instances per class).

### A4. Per-class results (locked test)

| Class (GT) | E1 AP50 / AP50-95 | **E3 AP50 / AP50-95** | E1 P / R at 0.25 | **E3 P / R at 0.25** | E3 TP / FP / FN |
|---|---|---|---|---|---|
| helmet (256) | 0.948 / 0.762 | 0.949 / 0.786 | 0.922 / 0.926 | 0.929 / 0.926 | 237 / 18 / 19 |
| gloves (326) | 0.873 / 0.709 | 0.877 / 0.728 | 0.886 / 0.831 | 0.871 / 0.868 | 283 / 42 / 43 |
| vest (303) | 0.909 / 0.766 | 0.962 / 0.798 | 0.941 / 0.894 | 0.945 / 0.957 | 290 / 17 / 13 |
| boots (440) | 0.848 / 0.692 | 0.873 / 0.727 | 0.845 / 0.807 | 0.810 / 0.841 | 370 / 87 / 70 |
| goggles (136) | 0.965 / 0.731 | 0.972 / 0.743 | 0.970 / 0.949 | 0.963 / 0.956 | 130 / 5 / 6 |
| Person (401) | 0.987 / 0.886 | 0.987 / 0.882 | 0.952 / 0.980 | 0.961 / 0.978 | 392 / 16 / 9 |
| no_helmet (142) | 0.753 / 0.436 | 0.792 / 0.514 | 0.787 / 0.676 | 0.814 / 0.739 | 105 / 24 / 37 |
| no_goggle (46) | 0.459 / 0.104 | 0.515 / 0.163 | 0.792 / 0.413 | 0.800 / 0.522 | 24 / 6 / 22 |
| no_gloves (183) | 0.708 / 0.462 | 0.740 / 0.485 | 0.838 / 0.650 | 0.856 / 0.650 | 119 / 20 / 64 |
| no_boots (108) | 0.868 / 0.706 | 0.861 / 0.723 | 0.854 / 0.815 | 0.748 / 0.796 | 86 / 29 / 22 |
| forklift (46) | 0.895 / 0.702 | 0.863 / 0.646 | 0.929 / 0.848 | 0.787 / 0.804 | 37 / 10 / 9 |
| no_vest (93) | 0.717 / 0.495 | 0.777 / 0.535 | 0.965 / 0.591 | 0.941 / 0.688 | 64 / 4 / 29 |

**Confusion matrices:**
- Operating point (class-agnostic greedy matching, with a background row and column): `evaluation/test_E3_m896/confusion_matrix_op.csv`.
- Ultralytics: `confusion_matrix_ultralytics.csv`.
- Most frequent E3 confusions on the test:

| Predicted | Ground truth | Count |
|---|---|---|
| boots | no_boots | 14 |
| helmet | no_helmet | 10 |
| vest | no_vest | 10 |
| no_boots | boots | 7 |
| gloves | no_gloves | 6 |
| no_helmet | helmet | 4 |

**E3 is worse than E1** on no_boots precision (0.748 against 0.854) and on forklift (AP50 0.863 against 0.895).

### A5. Strata (locked test)

**Image family:**

| Model | Real scenes `source-*` (47 images, 1,154 objects): mAP50 / P / R at 0.25 | Generated close-ups (113 images, 1,326 objects): mAP50 / P / R at 0.25 |
|---|---|---|
| E1 | 0.571 / 0.826 / 0.694 | 0.942 / 0.951 / 0.959 |
| **E3** | **0.592 / 0.792 / 0.740** | **0.951 / 0.960 / 0.968** |

**The weakness is the real-scene family.** mAP50 there is about 0.59, against 0.95 on close-ups. Overall numbers are pulled up by the easier generated images.

**Object size** (relative area; recall at 0.25; E1 → E3):

| Class | tiny (< 0.1 %) | small (0.1–1 %) | medium (1–10 %) |
|---|---|---|---|
| All | 675 GT: 0.49 → **0.57** | 1,057: 0.95 → 0.96 | 509: 0.99 → 0.98 |
| no_helmet | 80: 0.47 → 0.56 | 22: 0.82 → 0.91 | 40: 1.00 → 1.00 |
| no_gloves | 86: 0.31 → 0.36 | 95: 0.95 → 0.91 | — |
| no_goggle | 35: 0.34 → 0.40 | 11: 0.64 → 0.91 | — |
| no_boots | 29: 0.38 → 0.34 | 77: 0.97 → 0.96 | — |
| no_vest | 32: 0.12 → 0.31 | 13: 0.38 → 0.62 | 37: 0.95 → 0.95 |

**Missed safety-critical boxes, E3 on the locked test** (counts only; `qualification/locked_test_analysis/fn_causes_test_E3_m896.json`):

| Class | FN | < 8 px at 640 | Median size | Cause |
|---|---|---|---|---|
| no_helmet | 37 | 31 | 4.5 px | nothing 20, helmet 7, localisation 8 |
| no_gloves | 64 | 41 | 6.7 px | nothing 47, gloves 9, localisation 8 |
| no_goggle | 22 | 16 | 6.8 px | nothing 15, localisation 4, goggles 3 |
| no_boots | 22 | 13 | 6.8 px | **boots 13**, localisation 6, nothing 3 |
| no_vest | 29 | 12 | 9.4 px | **Person 13**, vest 8, nothing 6 |
| Person | 9 | 1 | 11.3 px | nothing 7, localisation 2 |

- **Same pattern as on dev (REPORT-023 §8).** Tiny objects are missed outright; boots are confused with no_boots; no_vest boxes are absorbed by Person.
- No locked-test example was rendered or used for any decision.

### A6. Runtime and memory recorded during the locked-test run

These were measured inside `evaluate.py`: synchronised wall clock of predict plus copy, on 60 full-resolution test images, on battery, thermal state nominal.

| Model | Mean | Median | p95 | Max | MPS driver memory |
|---|---|---|---|---|---|
| E3 at 896 | 49.7 ms | 48.7 ms | 56.8 ms | 71.7 ms | 4,466 MB |
| E1 at 640 | 30.9 ms | 30.3 ms | 33.7 ms | 41.6 ms | 2,318 MB |

Live-pipeline runtime is in Part B.

### A7. Gate evaluation (pre-registered, §4 of the pre-registration)

| Gate | Requirement | E3 result | Pass? |
|---|---|---|---|
| G1 | mAP50 ≥ 0.93 | 0.847 | **Fail** |
| G2 | P ≥ 0.90 and R ≥ 0.90 at the operating point | 0.885 / 0.862 | **Fail** |
| G3 | each missing-PPE recall ≥ 0.90 | 0.739 / 0.650 / 0.522 / 0.796 / 0.688 | **Fail (5 of 5)** |
| G4 | registry validation, fallback and rollback tests pass | 14 registry tests and 6 candidate tests passed (§B5) | Pass |
| G5 | full regression suite passes | 156 passed, 0 failed, 0 skipped (§B5) | Pass |
| G6 | live replay inference p95 ≤ 33 ms; 0 stale boxes; 0 processing errors | p95 43.1 ms; 23.7 analysed fps from a 29.9 fps stream (31 of 149 frames dropped); 0 errors; no stale boxes (§B6) | **Fail** (latency) |
| G7 | user data intact | dataset 0 changes; events database and evidence untouched since 2026-11-20 (§B8) | Pass |
| Stretch | mAP50-95 ≥ 0.80 | 0.644 | not met |

**Decision: NOT PROMOTED.** G1–G3 fail, G6 fails, and any failing gate blocks promotion.

**What the result supports:** the candidate is a measurable improvement over the controlled reference on held-out data, and over the production YOLO26n on dev (REPORT-023 §4.2). The evidence supports calling it "a better research candidate", **not** "production-qualified".

## Part B — Phase 7: controlled application integration

### B1. Resulting application state

| Item | State | Evidence |
|---|---|---|
| Active model | `yolo26n_baseline`: `models/trained/best.pt`, sha256 `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b`, 640 px | `configs/settings.yaml` (`model.active`) |
| Automatic fallback | `yolo26n_baseline` | `model.fallback` |
| `configs/settings.yaml` | **Not changed** in Phases 5–8. Last modified 2026-11-22 19:02 (Phase 7 preparation, registry introduced; pre-change copy `manifests/settings.yaml.before_phase7`). Thresholds and compliance values identical to the pre-programme file | `diff` against `settings.yaml.before_phase7`: only the `model:` block differs |
| Candidate | Stored, **not registered** | below |

**Stored candidate:**
- `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt`, 44,059,865 bytes, sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`. It is byte-identical to the frozen checkpoint.
- Its `model_card.json` records:
  - `status` "not promoted: locked test failed promotion gates G1 … G3 …", `registered_in_settings: false`, `active_default: false`;
  - architecture `yolo26m` and 21,791,392 parameters;
  - the training run and arguments, and the dataset version and split hashes;
  - the class mapping (12 classes), image size 896, and the unchanged thresholds and compliance settings;
  - the dev and locked-test evaluation summaries, the report paths, the Ultralytics version 8.4.215, and the rollback identity.
- Validation at storage time (`scripts/accuracy/promote_candidate.py --no-register`) confirmed the SHA-256 equal to the card, the class mapping equal to `configs/dataset.yaml`, and the architecture `yolo26m`. The production checkpoint was unchanged.

### B2. Integration mechanisms

These are in the code since the Phase 7 preparation of 2026-11-22 (CONTINUATION-001 §8) and are active for the YOLO26n entry.

| Spec §9 requirement | Implementation |
|---|---|
| Preserve YOLO26n as selectable rollback | Registry entry `yolo26n_baseline` is both `active` and `fallback`. The `SITEGUARD_MODEL=<key>` environment variable overrides `active` |
| Store YOLO26m as a separate versioned checkpoint | `models/trained/yolo26m_accuracy_candidate/<key>/` (refuses to overwrite) |
| Record model identity | Model card (above). `PPEDetector.info()` returns `model_key`, `status`, `architecture`, `image_size`, sha256, `model_card` and `load_errors` |
| Validate existence, class count and order, and metadata; never silently load an incompatible checkpoint | `src/detection/model_registry.py:load_validated`: file exists, SHA-256 equal to the card, YOLO task `detect`, class mapping equal to `configs/dataset.yaml`, architecture equal to the entry. Otherwise `IncompatibleModelError` or `ModelNotFoundError` |
| Log the active model identity in the dashboard and the logs | Sidebar shows the key, architecture, image size and short SHA, plus a warning when the fallback is used. The live caption shows the model key. The `siteguard.model` logger writes to `outputs/logs/siteguard_app.log` |
| Safe fallback if loading fails | `PPEDetector.load()` tries the active entry, then the fallback, and records `load_errors`. If neither loads, the dashboard stops with a clear error instead of loading anything |
| Preserve database and evidence | Model changes never touch `outputs/siteguard_events.db` or `outputs/evidence` (tested) |
| Do not alter compliance association, event persistence or alert rules | Not altered. `src/compliance/*` and `src/events/*` are unchanged; thresholds are unchanged |

### B3. Enabling the candidate later (needs the user's explicit approval; not done)

There are two ways to enable it.

**Option 1: provisional, selectable, not default (spec §9).**
1. Change `status` in the candidate's `model_card.json` to `"provisional: selectable for demonstration, not promoted (REPORT-024)"`.
2. Add this entry under `model.registry` in `configs/settings.yaml`:

   ```yaml
       yolo26m_e3_896_v1:
         weights: models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt
         architecture: yolo26m
         image_size: 896
         card: models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/model_card.json
         description: "PROVISIONAL - not promoted (REPORT-024); sha256 590d7d6e..."
   ```

3. Keep `active: yolo26n_baseline`. The model can then be chosen in Settings, or with `SITEGUARD_MODEL=yolo26m_e3_896_v1`.

The test `test_not_promoted_candidate_is_never_the_active_model` enforces step 1 before step 2.

**Option 2: promotion.** Only after a future candidate passes G1–G7. Use `promote_candidate.py --activate` with a new key.

### B4. Phase 6–7 code changes

| File | Change | Pre-change copy |
|---|---|---|
| `scripts/accuracy/evaluate.py` | Locked-test YAML fix (derived copy with an empty `train:`). The generic split YAML gained the same empty key | `manifests/evaluate.py.before_phase6_fix` |
| `scripts/accuracy/compare_candidates.py` | Absolute bootstrap intervals from the same resamples; locked-test guard and ledger rows | Programme script (REPORT-023 §11) |
| `scripts/accuracy/promote_candidate.py` | `--no-register` and `--status` options; the card records `status`, `registered_in_settings` and `active_default` | Programme script |
| `scripts/engineering/realtime_eval.py` | Bug fix: `paced_live_run` referenced an undefined `name` (introduced by the Phase 7 preparation). It now uses `det.image_size`. The first offline run failed on this and its partial outputs are kept in `qualification/realtime/video_runs_failed_attempt1/` | `manifests/realtime_eval.py.before_phase7` (before any programme change) |
| `tests/test_accuracy_candidate.py` | **New**, 6 tests (below) | — |
| `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/` | **New**: candidate checkpoint copy and model card | — |

### B5. Tests

**Full suite on 2026-11-23 at 03:56: 156 passed, 0 failed, 0 skipped**, in 14.8 s (`qualification/tests/pytest_full_20261123-0356.log`).
- 124 tests existed before the programme; 32 were added by it: 12 training-override tests, 14 registry tests and 6 candidate tests.
- No test was removed or weakened.

| Spec §9 test requirement | Tests (file: test) |
|---|---|
| YOLO26m loading and YOLO26n rollback | `test_model_registry.py`: `test_yolo26m_entry_loads_with_its_own_image_size`, `test_yolo26n_rollback_entry_loads_and_reports_identity`, `test_shipped_settings_keep_yolo26n_active_and_as_fallback`. `test_accuracy_candidate.py`: `test_candidate_passes_registry_validation`, `test_production_yolo26n_is_untouched_and_stays_the_fallback` |
| Missing or corrupt checkpoint | `test_missing_active_checkpoint_falls_back_to_yolo26n`, `test_corrupt_active_checkpoint_falls_back_and_is_left_untouched`, `test_no_usable_model_raises_instead_of_loading_anything` |
| Incorrect class mapping and metadata | `test_wrong_class_mapping_is_never_loaded`, `test_architecture_mismatch_is_rejected`, `test_model_card_hash_mismatch_is_rejected`, `test_card_identity_matches_the_stored_checkpoint` |
| Model switching and session restart | `test_switching_models_starts_a_new_live_session_and_writes_nothing`, `test_environment_variable_overrides_active_model`. `test_frame_sync.py`: `test_camera_restart_discards_old_session_results`, `test_frame_ids_unique_increasing_and_unique_across_sessions` |
| Image, video and live processing | `test_image_and_video_processing_with_the_yolo26m_entry`, `test_candidate_runs_image_and_live_pipelines_at_its_image_size` (candidate at 896). Also `test_pipeline_integration.py` (4) and `test_app.py` (15) |
| Stale-box prevention | `test_frame_sync.py`: `test_video_output_frames_only_carry_their_own_boxes` (parametrised over strides). `test_resolution_coordinates.py` (13) |
| Event generation and duplicate suppression | `test_events_and_reports.py`: `test_single_image_creates_one_event`, `test_continuing_violation_is_deduplicated`, `test_new_event_after_cooldown`, `test_different_worker_regions_are_separate_events`. `test_compliance_regression.py`: `test_three_analysed_frame_persistence_and_30s_suppression` |
| Evidence persistence | `test_evidence_review_status_database_restart_and_csv`, `test_evidence_image_uses_source_frame_coordinates` |
| No database reset | `test_model_changes_never_reset_the_events_database` |
| A not-promoted candidate is never active | `test_not_promoted_candidate_is_never_the_active_model` |
| Thresholds recorded unchanged | `test_card_records_the_unchanged_application_thresholds` |

### B6. Runtime on the M5

**Conditions:**
- Measured on 2026-11-23 from 03:17 to 03:38, by `scripts/engineering/realtime_eval.py offline`.
- On battery (82 → 80 %), thermal state nominal, no other heavy job running.
- Results are in `qualification/realtime/realtime_*.json`.

**Video pipeline** (project test clip: 270 frames at 15 fps; every frame analysed; `process_video`):

| Model (size) | Inference mean / p95 / max (ms) | Offline throughput | Frame order / boxes only from their own frame | Events | Evidence images |
|---|---|---|---|---|---|
| YOLO26n (640) | 9.3 / 14.1 / 18.0 | 94.3 fps | yes / yes | 16 | present |
| YOLO26m e30_b4 (640) | 25.7 / 27.1 / 31.8 | 37.1 fps | yes / yes | 19 | present |
| **E3 candidate (896)** | **42.7 / 45.1 / 52.9** | **22.8 fps** | yes / yes | 22 | present |

**Live replay.** The 149 webcam frames captured in the earlier live audit (29.8 fps) were replayed at their real timing through `LiveFrameProcessor`, using the latest-frame policy and analysing every delivered frame. The frames are private and were processed locally; none was displayed or saved.

| Model | Stream | Received / analysed / rendered fps | Dropped (queue) | Inference mean / p95 / max (ms) | Receive-to-render mean / p95 (ms) | Errors |
|---|---|---|---|---|---|---|
| YOLO26n | raw | 29.8 / 29.8 / 29.8 | 0 of 149 | 20.3 / 24.8 / 29.7 | 20.6 / 25.2 | 0 |
| YOLO26n | VP8 1 Mbps | 29.8 / 29.8 / 29.8 | 0 | 20.7 / 25.9 / 27.6 | 21.0 / 26.2 | 0 |
| YOLO26m e30_b4 | raw | 29.8 / 29.8 / 29.8 | 0 | 29.2 / 35.7 / 38.1 | 29.4 / 36.1 | 0 |
| YOLO26m e30_b4 | VP8 1 Mbps | 29.8 / 29.8 / 29.8 | 0 | 28.5 / 34.1 / 37.1 | 28.7 / 34.4 | 0 |
| **E3 candidate** | raw | 29.9 / **23.7** / 23.7 | **31 of 149** | **42.0 / 43.1 / 52.6** | 42.2 / 43.2 | 0 |
| **E3 candidate** | VP8 1 Mbps | 29.8 / **23.8** / 23.8 | **30 of 149** | 41.9 / 42.6 / 44.7 | 42.0 / 42.8 | 0 |

**Reading:**
- **Cost of 896 px:** about 42 ms per frame. A 30 fps camera delivers a frame every 33 ms, so the candidate **cannot analyse every frame**. About 1 frame in 5 is skipped by the latest-frame policy, and the display updates at about 24 fps.
- **No stale boxes:** this follows from the R1 invariant, which is tested by `test_frame_sync.py`. In the video check every output frame carries only its own boxes. The replay script does not measure stale boxes separately; it records 0 by construction.
- **Earlier YOLO26m at 640:** it keeps up, although its p95 is slightly above 33 ms on this run.
- **Comparison with history:** the spec quotes about 30.05 analysed fps and 26.9 ms mean for YOLO26m on the physical camera (REPORT-016). Today's replay gives 29.8 fps and 29.2 ms for the same checkpoint, which is consistent.
- **Browser FPS:** not measured, so not claimed.

**Displayed accuracy on the 10 labelled replay frames (30 objects):** this sample is too small to compare models.
- YOLO26n: TP 10, FP 15. YOLO26m e30: TP 10, FP 16. E3: TP 9, FP 0 on the 9 labelled frames it analysed.
- **All three models detect only a third of the objects:** recall 0.33. The real-webcam domain gap found in the live audit (REPORT-009) remains.

**Robustness on dev-derived images** (720p camera simulation; 200 dev images; mAP50 / recall):

| Condition | YOLO26n | YOLO26m e30 | **E3** |
|---|---|---|---|
| Clean | 0.735 / 0.746 | 0.821 / 0.827 | **0.845 / 0.849** |
| Dim (×0.5, noise) | 0.721 / 0.728 | 0.811 / 0.819 | **0.826 / 0.827** |
| Dark (×0.25, noise) | 0.651 / 0.632 | **0.684 / 0.663** | 0.626 / 0.592 |
| Motion blur (17 px) | 0.614 / 0.578 | **0.686 / 0.657** | 0.675 / 0.616 |

**Motion panning** (40 dev images × 15 frames; precision / recall at 0.25):

| Panning speed | YOLO26n | YOLO26m e30 | E3 |
|---|---|---|---|
| 0 px / frame | 0.795 / 0.532 | 0.830 / 0.668 | 0.856 / 0.720 |
| 20 px / frame | 0.804 / 0.597 | 0.836 / 0.720 | 0.854 / 0.730 |

**Regression to disclose:** **in synthetic darkness, E3 is worse than both 640-px models, including production YOLO26n** (mAP50 0.626 against 0.651). Under blur it is worse than the earlier YOLO26m. These are synthetic transforms, not real night footage, but they are a robustness risk for a 896-px model.

### B7. Physical-camera test

**Status: not run yet.** It needs the user present.
- The camera turns on.
- Frames are processed locally and **not saved** (`frames_saved: 0` in the script).
- The user's standing instruction is to be warned before any physical-camera test.

Command, run only after the user confirms:

```bash
.venv/bin/python scripts/engineering/realtime_eval.py camera --seconds 12 \
  --model yolo26n=models/trained/best.pt@640 \
  --model e3_candidate=models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt@896 \
  --out experiments/accuracy_improvement/qualification/realtime
```

**What to expect:** from the replay, YOLO26n analyses about 30 fps and E3 about 24 fps. The physical test adds capture timing and real camera exposure.

### B8. Integrity and user data

`scripts/accuracy/integrity_manifest.py verify manifests/20261120-005540_phase0` was run on 2026-11-23 at 03:57. Output: `qualification/tests/integrity_verify_20261123.{txt,json}`.

| Set | Result |
|---|---|
| Dataset (`../construction-ppe/`, 2,004 files) | **0 changed, 0 missing, 0 new** |
| Key checkpoints | **0 critical violations**: `models/trained/best.pt` `890dc61f…` and `yolo26m_e30_b4/weights/best.pt` `399c4e5b…` unchanged |
| Protected files changed (7) | `app.py`, `configs/settings.yaml`, `src/detection/detector.py` (Phase 7 integration); `src/training/train.py` (`--seed`/`--hyp`); `scripts/engineering/realtime_eval.py`; `docs/IMPLEMENTATION_LOG.md`; `experiments/training.log` (appended by training). All are intended programme changes with pre-change copies in `manifests/` |
| User data (313 files) | 1 changed: `outputs/siteguard_events.db`. Last modified **2026-11-20 21:19:11** (33 events; latest event 2026-11-20T21:19:07) by the user's own image inspection, recorded in CONTINUATION-001 before Phase 4. **Not modified by the programme.** Evidence images unchanged |

### B9. Known issues

1. **Real-time budget:** the candidate does not fit the 30 fps frame budget at 896 px (§B6).
2. **Low-light robustness:** E3 regresses under synthetic darkness (§B6).
3. **Test logging:** the tests that import `app.py` append to the real application log `outputs/logs/siteguard_app.log`. This is minor, but test runs should write to a temporary log.
4. **Replay accuracy sample:** only 10 labelled frames, too small to rank models.

### B10. Acceptance (spec §8, §9)

| Criterion | Result |
|---|---|
| Frozen candidate and configuration hashed | Pass (`frozen_candidate.json`, pre-registration hash) |
| Locked-test protocol followed; no test tuning | Pass. Two failed attempts read no data and are documented; no change after viewing |
| All metrics disclosed | Pass (§A2–§A6, including intervals, per class, strata, confusions, failure causes, latency and memory) |
| YOLO26m selection works | Pass: the registry loads and validates YOLO26m entries (tests). The candidate itself is not selectable, by decision |
| YOLO26n rollback works | Pass (tests; active and fallback) |
| Tests pass or failures documented | Pass: 156 of 156 |
| User data intact | Pass (§B8) |
| Runtime measured | Pass for video and replay. **Physical camera pending the user** (§B7) |
| REPORT-024 written | This report |


---

## Correction note — 2026-11-23 12:36 IST (appended; the original text above is unchanged)

**What was wrong:** this document says that the evidence images were not modified by the accuracy programme. **That statement was inaccurate.**

**What happened:**
- The Phase 7 offline real-time test (`scripts/engineering/realtime_eval.py offline`, 2026-11-23 03:17–03:38) replayed the private webcam frames from `experiments/live_audit/webcam/`.
- It processed them through `LiveFrameProcessor(..., store=None)`. `EventManager` still saves evidence when `store` is `None`.
- As a result, the test wrote **one** webcam-derived image into production evidence storage: `outputs/evidence/EVT-20261123-031826-215199.jpg` (78,413 bytes, sha256 `f9d2380ca37b803c3c3ff8ba0612c876ac2065eb666eab1dd35b9425c34bc3eb`, created 03:18:26).
- It was **not** linked to any event (0 database rows reference it).

**Why the integrity check missed it:** `integrity_manifest.py verify` reports changed or missing *listed* files. It does not report *new* evidence files.

**How it was found and resolved:**
- Found during the camera quality audit: `experiments/camera_quality_audit/reports/CAMERA-QUALITY-REPORT-001.md` §8.
- With the project owner's authorisation, that single file was deleted on 2026-11-23 at 12:35:48, after its name, size and hash were recorded. The other 131 evidence files were verified byte-identical before and after.
- Record: `experiments/camera_quality_audit/fixes/phase1/target_file_record.txt`.
- The cause in the test script is fixed in the camera-quality fix programme (Fix 6).

**Unaffected:** all experiment results, metrics and decisions in this document. The events database, which was opened read-only, was never modified by the programme.

