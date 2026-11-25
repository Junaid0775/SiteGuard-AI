# SiteGuard AI — Engineering Phase Execution Log

Authority: `SiteGuard_AI_Master_Engineering_Specification.md` (in the project root; 1,063 lines, 40,104 bytes, read in full on 2026-11-19 20:48).
Sequence: Discover → Preserve → Baseline → Diagnose → Implement R1/R2 → Test → Audit dataset → Check YOLO26m readiness → Train → Evaluate → Compare → Real-time validate → Report.

Each entry records the objective, the actions taken, the evidence produced and the outcome.

---

## Phase 0 — Project discovery and preservation

- **Started:** 2026-11-19 20:48 IST.
- **Objective:** inspect the real project, preserve existing work, record the Git state, hash protected assets, record the environment and rerun the tests. No code edits and no training.
- **Initial observations:**
  - Neither `SiteGuard-AI/` nor its parent is a Git repository (`fatal: not a git repository`), so there is no branch, commit or diff to record.
  - Files changed since REPORT-009: `SiteGuard_AI_Master_Engineering_Specification.md` (added by the user), `docs/.DS_Store` (Finder) and `docs/IMPLEMENTATION_LOG.md` (REPORT-009 update). No source code had changed.
  - The SiteGuard dashboard is running on `localhost:8502` (PID 31804). Port 8501 belongs to an unrelated project (`472 Project`), which was not touched.
- **Preservation:** because there is no Git, a pre-change source snapshot was taken: `experiments/engineering_phase/baseline/source_snapshot_20261119-204914.tar.gz`, 81 entries, sha256 `09cba933…99b`. It contains app, src, tests, scripts, configs, docs, the Streamlit config, requirements, README, viewpoint metadata and the spec.
- **Hashes:** see `baseline/protected_assets_manifest.csv` (604 files), `baseline/dataset_manifest.csv` (2,004 files, all equal to the pre-project baseline) and `baseline/user_outputs_manifest.csv` (30 files of user data).
- **Environment:** `baseline/environment.{json,txt}`. MPS execution verified: weights on `mps:0`, fp32.
- **Code map:** `baseline/code_map.json` (24 modules, traced with AST).
- **Model inventory:** `baseline/model_inventory.json`. **Class mapping:** `baseline/class_mapping_verification.json` (10/10 PASS).
- **Tests (rerun):** 77 passed, 0 failed, 0 skipped, 5.77 s (`baseline/pytest_baseline.{txt,xml}`).
- **Outcome:** Phase 0 complete. No stop condition triggered. Report: `docs/reports/REPORT-010-phase0-project-discovery-and-baseline.md`.

## Phase 1 — Reproducible YOLO26n baseline

- **Objective:** reproduce the metrics with the configuration recorded, then analyse all 12 classes.
- **Command:** `.venv/bin/python scripts/engineering/evaluate_model.py --weights models/trained/best.pt --name yolo26n --out experiments/engineering_phase/baseline/yolo26n` (20:52:40–20:52:53).
- **Result:** P 0.8322, R 0.6809, mAP50 0.7339, mAP50-95 0.5227, identical to the historical values. Operating point (conf 0.25 / IoU 0.5): P 0.884, R 0.745.
- **Class analysis:** recall is limited mainly by object size and crowding; item ↔ missing-item confusion; no_goggle limited by label ambiguity and coverage (53.6 % of persons unlabelled for the eye region).
- **Outcome:** Phase 1 complete. Reported in REPORT-010 §10.

## Phases 2 and 3 — R1 frame synchronisation and R2 inference size 640

- **Started:** about 20:58 (artefacts 21:07–21:10). **Objective:** source-frame identity, no stale rendering, latest-frame policy with counted drops, safe lifecycle, latency instrumentation; live imgsz 640 from one authoritative setting.
- **Changed files:** `src/detection/camera_processor.py` (rewritten), `src/detection/video_processor.py`, `app.py` (Live, Video and Settings pages, minimal), `configs/settings.yaml`, `tests/test_app.py` (one expectation). New files: `tests/test_frame_sync.py`, `tests/test_resolution_coordinates.py`, `scripts/engineering/measure_r1_r2.py`.
- **Tests:** 105 passed. The mutation check fails on the pre-change code (2 failed) and passes on the new code.
- **Measured:** stale frames 400 → 0 per 600; displayed P at 20 px/f 0.362 → 0.804; live at 30.0 fps with 0 drops (paced); +0.76 ms median for 640; video 216 → 0 reused-box frames; events 16/16 by count, 15/16 matched, fire about 0.54 s earlier.
- **Protected assets:** dataset 0 changed; 14 model/checkpoint files unchanged; `best.pt` `890dc61f…`.
- **Dashboard** restarted on 8502 (PID 34056) with the new pipeline.
- **Pending:** physical browser-camera check (user); decision on event timing (persistence window).
- **Outcome:** R1 and R2 accepted. Report: `docs/reports/REPORT-012-live-pipeline-r1-r2-implementation.md`.

## Phase 4 — Dataset quality and annotation audit

- **Objective:** structural, distribution, scale, duplicate/leakage, visual-review, suspect-list and viewpoint audit, read-only on the original data.
- **Commands:** `.venv/bin/python scripts/engineering/dataset_audit.py`. Then inline steps (code in the session transcript; outputs in `experiments/dataset_audit/`): a near-duplicate pair sheet; masked background correlation (`background_leakage.json`); a systematic review sample (`review_selection.csv`, seed 0) and sheets; findings (`review_findings.csv`) appended to `suspect_annotations.csv`.
- **Results:**
  - Structure clean (14,863 boxes, 0 invalid).
  - Strong scale imbalance of the missing-PPE classes.
  - 0 exact duplicates; 1 background-level cross-split overlap (1 val image, r = 0.991); no material leakage.
  - 29 images visually reviewed (15 ok).
  - 162 suspect rows (51 high, rule-based).
- **Dataset after the audit:** 0 changed, 0 missing, 0 new files.
- **Outcome:** complete; no stop condition. Report: `docs/reports/REPORT-011-dataset-quality-and-annotation-audit.md`.

## Phase 5 — YOLO26m readiness

- **Objective:** verify support, checkpoint and MPS stability; choose the batch size from smoke tests; freeze the configuration.
- **Results:**
  - `yolo26m` is supported by Ultralytics 8.4.215.
  - Weights `models/pretrained/yolo26m.pt` (sha256 `401cea9a…`): 21.9 M params, MPS fp32; 36.1 ms wall time per image.
  - Smoke training: b8 9.7 GB with 10 % free and swap +3.7 GB (rejected); b6 7.66 GB / 26 %; b4 5.5 GB / 41 % (selected). Same throughput, about 12.8 img/s.
- **Change:** `src/training/train.py` gains a `--project` option (default unchanged).
- **Outcome:** ready. Report: `docs/reports/REPORT-013-yolo26m-readiness-and-training-configuration.md`. Config: `experiments/yolo26m/configs/train_config.json`.

## Phase 6 — YOLO26m training (started)
- **Training:** 21:22:30 → 22:57:30; exit 0; 30 epochs in 94.6 min; best epoch 30; memory min free 18 %; swap did not grow; no warnings. `caffeinate -dims -w <pid>` was used at the user's request.
- **Checkpoint:** `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt`, sha256 `399c4e5b…`; 12 classes verified; distinct from YOLO26n; not promoted.
- **Validation:** P 0.8909, R 0.7773, mAP50 0.8311, mAP50-95 0.6195. Report: REPORT-014.

## Phase 7 — Controlled comparison

- **Commands:** `evaluate_model.py` for YOLO26m (same procedure as the baseline), then `compare_models.py`.
- **Results:**
  - mAP50-95 +0.097 (bootstrap +0.093, CI [0.081, 0.103]); all 12 classes improved.
  - Recall at conf 0.25: 0.745 → 0.828; FP 289 → 319.
  - Latency at 720p: 8.0 → 25.0 ms; MPS memory 0.1 → 1.2 GB.
  - Visual examples: 11 better, 2 worse, 3 equal.
  - Real webcam scene at 640 not improved.
- **Outcome:** report REPORT-015.

## Phase 8 — Real-time webcam and video

- **Commands:** `realtime_eval.py offline`; `realtime_eval.py camera --seconds 12` (camera on for about 30 s, no frames saved; the user was warned first).
- **Results:**
  - Physical camera: n 29.94 fps analysed, 0/359 dropped, 18.7 ms; m 30.05 fps, 1/361 dropped, 26.9 ms.
  - Video integrity: all PASS (the event-time check was corrected for 0.01 s rounding).
  - Webcam replay: 0 drops; m less stable on the indoor scene.
  - Motion and degradation: m better.
  - Power state was battery (33 %); paced latency depends on it (probe JSON).
- **Report:** REPORT-016.

## Phases 9–12 — Compliance regression, tests, evidence, final report

- **Compliance:** rules and thresholds verified unchanged in source and settings; 15 regression tests.
- **Tests:** 124 passed, 0 failed, 0 skipped (11.63 s). `pytest.ini` restricts collection to `tests/` (the earlier 105 included 2 mutation-check tests; REPORT-012 corrected).
- **Integrity at the end:** dataset 0 changed; `best.pt` unchanged. Expected changes: `settings.yaml` (R1/R2), `IMPLEMENTATION_LOG.md`, the appended `experiments/training.log`, and my own `outputs/streamlit_server.log` (overwritten on restart). Events DB and evidence unchanged.
- **Final report:** REPORT-017. **Production not switched** (approval required).
