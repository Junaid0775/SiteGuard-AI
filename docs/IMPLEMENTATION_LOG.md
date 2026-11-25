# SiteGuard AI — Implementation Log

A chronological master summary. Details are in the linked reports under `docs/reports/`.

| # | Date | Milestone | Status | Report |
|---|---|---|---|---|
| 1 | 2026-11-19 | Workspace and dataset audit | Complete | [REPORT-001](reports/REPORT-001-workspace-audit.md) |
| 2 | 2026-11-19 | Python environment, dependencies, MPS, pretrained YOLO26n | Complete | [REPORT-002](reports/REPORT-002-environment-setup.md) |
| 3 | 2026-11-19 | Dataset configuration, mirror, validation, viewpoint labels | Complete | [REPORT-003](reports/REPORT-003-dataset-configuration.md) |
| 4 | 2026-11-19 | YOLO26n fine-tuning (30 epochs, MPS) | Complete | [REPORT-004](reports/REPORT-004-model-training.md) |
| 5 | 2026-11-19 | Detector, compliance analyzer, events, reports | Complete | [REPORT-005](reports/REPORT-005-detection-compliance-events.md) |
| 6 | 2026-11-19 | Streamlit dashboard and live camera | Complete (manual webcam check pending) | [REPORT-006](reports/REPORT-006-dashboard-live-camera.md) |
| 7 | 2026-11-19 | Model evaluation and viewpoint generalisation experiment | Complete | [REPORT-007](reports/REPORT-007-evaluation-viewpoint.md) |
| 8 | 2026-11-19 | Testing, documentation, final verification | Complete (manual webcam check pending) | [REPORT-008](reports/REPORT-008-final-verification.md) |
| 9 | 2026-11-19 | Live / video detection accuracy audit (no fixes applied) | Complete; awaiting approval of fixes | [REPORT-009](reports/REPORT-009-live-video-accuracy-audit.md) |
| 10 | 2026-11-19 | Engineering phase 0–1: discovery, preservation, YOLO26n baseline | Complete | [REPORT-010](reports/REPORT-010-phase0-project-discovery-and-baseline.md) |
| 11 | 2026-11-19 | Engineering phase 4: dataset quality and annotation audit | Complete | [REPORT-011](reports/REPORT-011-dataset-quality-and-annotation-audit.md) |
| 12 | 2026-11-19 | Engineering phases 2–3: R1 frame synchronisation, R2 imgsz 640 | Complete (browser-camera check pending) | [REPORT-012](reports/REPORT-012-live-pipeline-r1-r2-implementation.md) |
| 13 | 2026-11-19 | Engineering phase 5: YOLO26m readiness (batch 4 chosen on memory) | Complete | [REPORT-013](reports/REPORT-013-yolo26m-readiness-and-training-configuration.md) |
| 14 | 2026-11-19 | Engineering phase 6: YOLO26m training (30 epochs, 94.6 min) | Complete | [REPORT-014](reports/REPORT-014-yolo26m-training-and-validation.md) |
| 15 | 2026-11-19 | Engineering phase 7: YOLO26n vs YOLO26m comparison | Complete | [REPORT-015](reports/REPORT-015-yolo26n-vs-yolo26m-comparison.md) |
| 16 | 2026-11-19 | Engineering phase 8: real-time webcam and video evaluation | Complete (browser test pending) | [REPORT-016](reports/REPORT-016-real-time-webcam-and-video-evaluation.md) |
| 17 | 2026-11-19 | Engineering phases 9–12: compliance regression, tests (124 passed), final decision | Complete; production switch awaiting approval | [REPORT-017](reports/REPORT-017-siteguard-ai-engineering-phase-final-report.md) |
| 18 | 2026-11-20 | Accuracy programme Phase 0: discovery, environment, integrity manifests, model identity re-validation | Complete | [REPORT-018](../experiments/accuracy_improvement/reports/REPORT-018-discovery-and-integrity.md) |
| 19 | 2026-11-20 | Accuracy programme Phase 1: full dataset audit, 162 suspects reconciled + 16 new, review page, ANNOTATION_POLICY.md | Complete (human review pending) | [REPORT-019](../experiments/accuracy_improvement/reports/REPORT-019-dataset-quality-and-label-policy.md) |
| 20 | 2026-11-20 | Accuracy programme Phase 2: grouped train 640 / dev 200 / locked test 160 split, evaluation protocol v1, locked-test guard | Complete | [REPORT-020](../experiments/accuracy_improvement/reports/REPORT-020-evaluation-protocol-and-splits.md) |
| 21 | 2026-11-20 | Accuracy programme Phase 3: data-source register (no import), augmentation audit, inference-size/tiling comparison, 896/1024 memory smoke tests, training-only tile set, train.py --seed/--hyp (+12 tests) | Complete (training ablations = Phase 4) | [REPORT-021](../experiments/accuracy_improvement/reports/REPORT-021-data-expansion-and-augmentation.md) |
| 22 | 2026-11-23 | Accuracy programme Phase 4: guarded training matrix E1 (640 baseline), E3 (896), E5 (cls_pw 0.5), E4 (conservative augmentation); E2/E6/E7 and extra seeds not run (deadline, user decision) | Complete with documented reductions (1 seed) | [REPORT-022](../experiments/accuracy_improvement/reports/REPORT-022-training-experiment-matrix.md) |
| 23 | 2026-11-23 | Accuracy programme Phase 5: dev comparison with paired bootstrap, strata, error manifests and contact sheets, threshold sweep (thresholds unchanged), calibration; candidate E3_m896 selected and frozen (sha256 590d7d6e…) | Complete | [REPORT-023](../experiments/accuracy_improvement/reports/REPORT-023-model-comparison-and-error-analysis.md) |
| 24 | 2026-11-23 | Accuracy programme Phases 6–7: one locked-test session (E3 mAP50 0.847, P/R 0.885/0.862 at 0.25, missing-PPE recall 0.52–0.80) - promotion gates failed, **not promoted**; candidate stored with model card, YOLO26n stays active and fallback; real-time and regression tests | Complete (camera test awaits the user) | [REPORT-024](../experiments/accuracy_improvement/reports/REPORT-024-qualification-and-integration.md) |
| 25 | 2026-11-23 | Accuracy programme Phase 8: final research decision, README, handoff with frontend integration requirements | Complete | [REPORT-025](../experiments/accuracy_improvement/reports/REPORT-025-final-research-decision.md) |
| 26 | 2026-11-23 | Frontend completion: dark industrial Streamlit dashboard (in place), `src/ui/` components, read-only settings, research-results page, live status panel from `snapshot()`, 10 new UI tests (suite 166 passed); YOLO26n stays active, E3 not selectable | Complete (physical-camera validation pending) | [FRONTEND-REPORT-006](../experiments/frontend_completion/reports/FRONTEND-REPORT-006-final-handoff.md) |

## Milestone notes

### 1. Workspace audit
- **Completed:** inspected the workspace, dataset, licence and hardware, and recorded a SHA-256 baseline of the dataset.
- **Files:** `data/dataset_baseline.sha256`.
- **Outcome:** dataset valid (1,000 images, 14,863 boxes, 0 issues). Apple M5, 16 GB, MPS.

### 2. Environment
- **Completed:** `.venv` (Python 3.12.16, uv), pinned `requirements.txt`, YOLO26n downloaded, Ultralytics telemetry off.
- **Commands:** `uv venv`, `uv pip install …`, `curl … yolo26n.pt`.
- **Tests:** imports, MPS matmul, pretrained load and predict: PASS.
- **Issues:** intermittent TLS interception (Sophos) and timeouts, resolved by retrying.

### 3. Dataset configuration
- **Completed:** `configs/dataset.yaml`, `src/utils/{paths,dataset_tools}.py`, symlink mirror, resolved YAML, manual viewpoint labels for all 1,000 images, viewpoint splits.
- **Tests:** `tests/test_dataset.py`, 13 tests: PASS.

### 4. Model training
- **Completed:** `src/training/train.py`, a 1-epoch smoke run, and the main 30-epoch run (21.2 min, MPS). best.pt promoted to `models/trained/`.
- **Outcome:** val P 0.832 / R 0.681 / mAP50 0.734 / mAP50-95 0.523.
- **Tests:** model load and detection format: PASS.

### 5. Detection, compliance, events
- **Completed:** detector, annotate, image/video/camera processors, association, compliance, event manager and store, CSV reports, test clip.
- **Tests:** 37 unit and integration tests: PASS. One test assumption (≤10 events) was wrong and was replaced with a property check.
- **Manual:** two real val images inspected visually, and a full 270-frame clip run (16 events, 105 suppressed).

### 6. Dashboard
- **Completed:** `app.py` (8 pages), `.streamlit/config.toml`, AppTest suite (14 tests: PASS), local server on port 8502 (8501 belongs to another project).
- **Fix:** WebRTC wrapped in try/except. Tests now delete the evidence and video files they create.
- **Pending:** a manual browser webcam check.

### 7. Evaluation and viewpoint experiment
- **Completed:** standard validation (mAP50-95 0.523). Frontal-only model trained (527 images, 14.7 min). Evaluated on 13 groups, and the main model on the val-split groups.
- **Outcome:** frontal 0.639, side 0.678 (−0.040), overhead 0.185 (+0.454 drop). Training on all viewpoints lifts overhead val from 0.227 to 0.309.
- **Files:** `src/evaluation/*`, `scripts/run_viewpoint_experiment.sh`, `experiments/viewpoint_*`, `docs/EVALUATION.md`.

### 8. Final verification
- **Tests:** 64 passed. Interrupt-and-resume test passed (SIGTERM during epoch 2, resumed to epoch 4).
- **Dataset:** 2,004 checksums OK, no new files.
- **Server:** `streamlit run app.py --server.port 8502` → health `ok`.
- **Open:** manual browser webcam check; human spot-check of the viewpoint labels.

### 9. Live / video detection accuracy audit
- **Completed:**
  - `src/evaluation/live_audit.py`, a harness verified identical to the app detector (60/60);
  - 29 conditions on the 200 labelled val images;
  - a frame-skipping simulation (600 labelled frames);
  - latency, device, colour, object-scale and detection-to-compliance analyses;
  - 149 real webcam frames through both pipelines, 10 labelled manually (`scripts/capture_webcam_frames.py`).
- **Root causes (measured):**
  1. Stale boxes redrawn on skipped frames. Displayed precision falls from 0.79 to 0.51 (every 3rd frame) and 0.35 (every 5th) at 10 px/frame motion.
  2. Live imgsz 480 against 640 for images. mAP50-95 falls from 0.514 to 0.454, recall from 0.745 to 0.676, and violation recall from 0.542 to 0.489, for a speed gain under 1 ms.
  3. Close-range indoor webcam content is outside the training scale and shape range. The head at 640 is larger than any training no_helmet box, and the webcam errors are model localisation errors that occur in both pipelines.
  4. Blur and low light (−0.143 and −0.095 mAP50-95).
  5. Contradicting and duplicate boxes from per-class NMS.
  6. Low-bitrate WebRTC (−0.049 at 300 kbps).
- **Ruled out (measured):** colour/channel conversion, capture resolution, YUV 4:2:0, MPS vs CPU, box scaling, the compliance rules themselves.
- **Tests:** 13 new evaluator tests; full suite 77 passed.
- **Not changed:** the app, pipelines, configs, model checkpoint (`890dc61f…`) and dataset (checksums OK).
- **Privacy:** `experiments/live_audit/webcam/` holds images of a person. It is git-ignored; delete it after review.
- **Next:** with approval, implement R1 (no stale boxes / analyse every frame) and R2 (live imgsz 640), then re-run the same harness as a before/after A/B.

### Engineering phase (Master Engineering Specification)
The detailed log is in `experiments/engineering_phase/EXECUTION_LOG.md`. REPORT-010 covers the baseline (reproduced exactly: P 0.832, R 0.681, mAP50 0.734, mAP50-95 0.523). REPORT-012 covers R1/R2 (stale boxes eliminated, live at 640, 105 tests pass).

YOLO26m (`experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt`) reaches val mAP50-95 0.620 against 0.523 for YOLO26n, and is real-time capable on the M5 (about 27 ms per frame). It is recommended as the production candidate but **not switched** (needs approval). 124 tests pass.
