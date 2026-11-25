# REPORT-010 — Phase 0 Project Discovery and Preservation, and Phase 1 Reproducible YOLO26n Baseline

**Date:** 2026-11-19 (20:48–20:57 IST, from file timestamps) **Spec:** `SiteGuard_AI_Master_Engineering_Specification.md` §2 (Phase 0) and §3 (Phase 1)
**Status:** Phase 0 complete. Phase 1 complete. No application code, configuration, checkpoint or dataset was modified.

---

## 1. Executive summary

The project was inspected from the actual source code, which was traced with a static analysis (`scripts/engineering/code_map.py`). All protected assets were hashed and a pre-change source snapshot was taken.

| Check | Result |
|---|---|
| Git | **The project is not a Git repository**, so there is no branch, commit or diff to record. Preservation therefore relies on the snapshot and the hash manifests. |
| Original dataset | **Unchanged:** all 2,004 files are byte-identical to the checksum baseline taken before any work. |
| Production checkpoint | `models/trained/best.pt` is intact (sha256 `890dc61f…995b9b`). |
| Class mapping | Identical across labels, YAMLs, checkpoint, inference output, compliance rules, event categories, CSV labels and visualisation (10/10 checks). |
| Device | MPS execution verified (weights on `mps:0`). |
| Test suite (rerun now) | **77 passed**, 0 failed, 0 errors, 0 skipped, 5.77 s. |

**YOLO26n baseline reproduced exactly** with Ultralytics validation on 200 val images and 2,961 instances: **P 0.8322, R 0.6809, mAP50 0.7339, mAP50-95 0.5227**. The historical values were 0.832 / 0.681 / 0.734 / 0.523. At the app operating point (conf 0.25, NMS IoU 0.5) the model scores P 0.884, R 0.745 (TP 2206, FP 289, FN 755).

The class investigation shows that recall depends mainly on **object size** and **crowding**, not on lighting:
- Small objects (under 1 % of image area) have much lower recall than medium ones, e.g. no_vest 0.20 against 0.98.
- Images with 6 or more people have much lower recall than images with 1–2, e.g. gloves 0.31 against 0.92.
- The dominant class errors are **item vs its own missing class** (e.g. boots predicted on true no_boots 21 times).
- `no_goggle` (AP50 0.148) is limited by tiny eye-band boxes, eyeglasses-vs-goggles ambiguity and incomplete labelling: 53.6 % of val persons have neither a goggles nor a no_goggle label.

## 2. Objective

- **Phase 0:** discover the real architecture, preserve existing work, record Git state, hashes, environment and current tests, and list known issues and proposed changes.
- **Phase 1:** reproduce the YOLO26n metrics with a fully recorded configuration, then analyse all 12 classes.

## 3. Initial project state

| Item | State found |
|---|---|
| Workspace | `/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI/` (`.venv` 1.4 GB, `data` 33 MB, `experiments` 212 MB, `models` 16 MB, `outputs` 4.0 MB, `src` 500 KB, `tests` 248 KB, `docs` 144 KB) |
| Version control | Not a Git repository: `git rev-parse` → `fatal: not a git repository` (project and parent folder) |
| Changes since REPORT-009 | The spec file (added by the user), `docs/.DS_Store` (Finder), `docs/IMPLEMENTATION_LOG.md`. **No source change.** |
| Running services | SiteGuard Streamlit on `localhost:8502` (PID 31804). Port 8501 is another project (`472 Project`) and was left untouched. |
| User data | `outputs/siteguard_events.db`: 22 events (21 `live_camera`, 1 `image`), 3 inspections, 23 evidence JPGs from the user's live session on 19:33–19:38. **Private, preserved, hashed, not viewed.** |
| Private webcam audit frames | `experiments/live_audit/webcam/` (149 frames, git-ignored). Preserved. |

## 4. Technical investigation — architecture traced from the source

### 4.1 Directory overview

| Path | Contents |
|---|---|
| `app.py` | Streamlit dashboard, 743 lines: 8 pages and the sidebar |
| `src/detection/` | `detector.py` (model wrapper), `image_processor.py`, `video_processor.py`, `camera_processor.py`, `annotate.py` |
| `src/compliance/` | `worker_association.py`, `compliance_analyzer.py` |
| `src/events/` | `event_manager.py` (persistence/cooldown), `event_store.py` (SQLite) |
| `src/evaluation/` | `evaluate.py`, `viewpoint_evaluation.py`, `live_audit.py` |
| `src/reporting/report_generator.py` | CSV reports |
| `src/training/train.py` | Fine-tuning |
| `src/utils/` | `paths.py`, `dataset_tools.py`, `logging_config.py` |
| `configs/` | `dataset.yaml` (12 classes, relative dataset path), `settings.yaml` (all thresholds) |
| `scripts/` | Contact sheets, viewpoint CSV builder, test-video builder, webcam capture, viewpoint experiment runner, `engineering/` (new: hash manifest, code map, evaluation) |
| `tests/` | 7 test files, 77 tests |
| `models/` | `pretrained/yolo26n.pt`, `trained/{best,last}.pt`, `MODEL_SOURCE.json` |
| `experiments/` | Training runs (`siteguard_yolo26n`, `viewpoint_frontal_only`, `smoke_test`, `resume_test`), `evaluation/`, `viewpoint_results/`, `live_audit/`, `engineering_phase/` (new) |
| `data/` | `dataset_mirror/` (symlinks), `generated/` (resolved YAMLs), `viewpoint_metadata.csv`, `test_media/`, `dataset_baseline.sha256` |
| `outputs/` | Events DB, evidence, annotated videos and images (**user data**) |
| `docs/` | README-level docs and `reports/REPORT-001…009` |
| Dependency files | `requirements.txt` (pinned). There is no lock file; the full `uv pip freeze` is in `baseline/environment.txt`. |

### 4.2 Module map

Definitions and callers come from `experiments/engineering_phase/baseline/code_map.json`.

| Module | Responsibility | Key classes / functions | Inputs → outputs | Called by | Side effects | Tests | Modification risk |
|---|---|---|---|---|---|---|---|
| `src/detection/detector.py` | Load the checkpoint and run YOLO | `PPEDetector.load/detect/info`, `Detection`, `resolve_device` | BGR ndarray → `list[Detection]` (class name from `model.names`) | app, all processors, compliance, live_audit | Loads weights; a lock serialises `predict` | test_image_and_model, integration | **High**: every path depends on it |
| `src/detection/image_processor.py` | Validate, decode and inspect one image | `decode_image_bytes`, `load_image`, `inspect_image`, `ImageInspection` | bytes/path → BGR; image → detections + compliance + annotated | app (Image page), live_audit | None | test_image_and_model, test_app | Medium |
| `src/detection/video_processor.py` | Offline video: read, detect every Nth frame, write H.264 | `process_video`, `open_writer`, `VideoSummary` | video path → annotated MP4 + summary + events | app (Video page) | Writes the output video; events via EventManager | integration, test_app | **High (R1)**: skipped frames reuse old boxes (line 116) |
| `src/detection/camera_processor.py` | Live frame processing for the WebRTC callback | `LiveFrameProcessor.process/snapshot`, `LiveStats`, `OpenCVFrameSource` | BGR frame → annotated frame; stats | app (Live page), live_audit | Events via EventManager (DB + evidence) | integration, test_app | **High (R1/R2)**: every 3rd frame (line 74); stale boxes on skipped frames (line 96); imgsz from `live.image_size` (line 61) |
| `src/detection/annotate.py` | Draw boxes and worker statuses | `draw_detections`, `draw_compliance`, `class_color` | image + result → new image | all processors | None (copies the image) | indirect | Low |
| `src/compliance/worker_association.py` | Geometry; link items to at most one worker | `associate_items`, `association_score`, `iou`, `containment` | workers + items → assignment | compliance_analyzer, annotate, event_manager | None | test_compliance | Medium (rules must not change) |
| `src/compliance/compliance_analyzer.py` | Three-status rules | `ComplianceAnalyzer.analyze/assess_item`, `ComplianceRules.from_settings` | detections → `ComplianceResult` | app, processors, event_manager, live_audit | None | test_compliance | Medium (rules frozen by spec) |
| `src/events/event_manager.py` | Persistence (3 hits), cooldown (30 s), evidence JPG | `EventManager.process` | result + time → new `SafetyEvent`s | app, video and camera processors | Writes the DB and evidence files | test_events_and_reports | Medium |
| `src/events/event_store.py` | SQLite events and inspections | `EventStore.add_event/list_events/update_review_status/add_inspection` | rows ↔ DataFrame | app, processors, event_manager | DB writes (`SITEGUARD_EVENTS_DB` overrides the path) | test_events_and_reports, test_app | Low |
| `src/reporting/report_generator.py` | CSV export | `events_to_csv_bytes`, `summary_report` | DataFrame → CSV | app | None | test_events_and_reports | Low |
| `app.py` | UI: 8 pages; WebRTC callback (`frame.to_ndarray("bgr24")` → `processor.process` → `from_ndarray`) | `page_*`, `get_detector`, `get_store`, `get_analyzer`, `default_cfg` | user actions → pipeline calls | Streamlit | Session state, DB via store | test_app (AppTest) | Medium (UI must not be redesigned) |
| `src/training/train.py`, `src/evaluation/*`, `src/utils/*` | Training, evaluation, paths/dataset | see code map | — | CLI, tests | Write only under `experiments/`, `data/generated`, `models/trained` (with backup) | test_dataset, test_live_audit | Low |

### 4.3 Data flow (traced)

- **Image page:** `decode_image_bytes` → `inspect_image` → `PPEDetector.detect(conf 0.25, imgsz cfg["image_size"]=640)` → `ComplianceAnalyzer.analyze` → `draw_compliance` → `EventManager(image).process` → `EventStore`.
- **Video page:** the upload goes to a temp file → `process_video(frame_stride=5)`. Frame *k*: if `k % 5 == 0`, detect + analyse + draw, plus events using video time; **otherwise `draw_compliance(frame_k, last_result)`**, i.e. boxes from frame *k − (k mod 5)* drawn on frame *k*. The output is H.264 and the temp upload is deleted.
- **Live page:** browser → WebRTC (aiortc) → streamlit-webrtc `AsyncVideoProcessTrack`. Its worker thread takes **all queued frames and processes only the newest** (`_fallback_recv_queued: frames[-1]`, `process.py:126`). If no new output frame is ready, the last output frame is re-sent (`process.py:237`). The callback calls `LiveFrameProcessor.process`, which analyses frames `n % 3 == 1` at `live.image_size = 480`, and **otherwise draws the last result on the new frame (`camera_processor.py:96`)**.
  - There are no frame IDs, no capture timestamps and no per-result source identity.
  - The library's input queue (`queue.Queue()`) is unbounded, but it is drained on every worker iteration.
  - The processor is discarded when the camera stops, which creates a new session.

### 4.4 Environment (`baseline/environment.json`, `environment.txt`)

| Item | Value |
|---|---|
| Machine | MacBook Air, Apple M5, arm64, 16 GB (17,179,869,184 bytes), macOS 27.0.1 (build 26A434) |
| Python / packages | Python 3.12.16 (uv venv); torch 2.15.0, torchvision 0.29.2, ultralytics 8.4.215, opencv-python 5.1.0.95, numpy 2.5.5, streamlit 1.67.0, streamlit-webrtc 0.79.1, av 19.0.2, aiortc 1.16.0, pandas 3.1.1, plotly 7.1.0 |
| MPS | `is_available()` True, `is_built()` True. **Actual execution verified:** the matmul result is on `mps:0`, identical to CPU (max diff 0.0); YOLO predict backend device `mps`, weight tensors on `mps:0`, fp16 False (fp32) |
| CUDA | not available |
| Disk | 690 GiB free of 926 GiB |
| Memory pressure | System-wide memory free 62–63 % (`memory_pressure`); 12,388 cumulative pageouts since boot |

### 4.5 Protected assets and hashes

Stored in `experiments/engineering_phase/baseline/`.

| Manifest | Files | Content |
|---|---:|---|
| `protected_assets_manifest.csv` | 604 | Checkpoints, configs, generated YAMLs, metadata, reports and docs, all experiment artefacts (241 MB) |
| `dataset_manifest.csv` | 2,004 | Every original dataset file. **All 2,004 hashes equal the pre-project baseline `data/dataset_baseline.sha256`; 0 new files.** |
| `user_outputs_manifest.csv` | 30 | Events DB, evidence images, annotated outputs (user data) |
| `source_snapshot_20261119-204914.tar.gz` | 81 entries | Pre-change copy of app, src, tests, scripts, configs, docs, README, requirements, Streamlit config, viewpoint metadata, spec. sha256 `09cba933…99b` |

Verification command: `.venv/bin/python scripts/engineering/hash_manifest.py verify <manifest.csv>`.

### 4.6 Model inventory (`baseline/model_inventory.json`)

| Checkpoint | sha256 (16) | Architecture | nc | Params (unfused) | Trained | Role |
|---|---|---|---:|---:|---|---|
| `models/trained/best.pt` | `890dc61fd024b247` | yolo26n.yaml | 12 | 2,539,232 | 30 epochs, imgsz 640, batch 8, 8.4.215 | **PRODUCTION — never overwrite** |
| `models/trained/last.pt` | `c32a10ec685b9e71` | yolo26n | 12 | 2,539,232 | same run | artefact |
| `models/pretrained/yolo26n.pt` | `9b09cc8bf347f0fc` | yolo26n | 80 (COCO) | 2,572,280 | Ultralytics release (8.3.222) | starting weights |
| `experiments/siteguard_yolo26n/weights/best.pt` | `890dc61fd024b247` | identical to production | 12 | — | source run | artefact |
| `experiments/viewpoint_frontal_only/weights/best.pt` | `36770b90284b1e8d` | yolo26n | 12 | — | frontal-only, 30 epochs | experiment |
| `experiments/smoke_test/…`, `experiments/resume_test/…` | — | yolo26n | 12 | — | 1 and 4 epochs | test artefacts |

Fused parameter count reported by Ultralytics: 2,392,408 (5.4 GFLOPs). Model load time: 0.012–0.03 s.

### 4.7 Class mapping verification (`baseline/class_mapping_verification.json`)

All PASS:
- original `data.yaml` = `configs/dataset.yaml` = generated YAML = checkpoint `model.names`;
- label files contain IDs 0–11 only, all present;
- inference output names ⊆ checkpoint names;
- compliance item classes and `Person` ⊆ names;
- event categories (`no_*`) ⊆ names and = CSV category labels;
- visualisation colours (negatives red, positives green, Person blue).

`Person` and `forklift` are intentionally not PPE items.

### 4.8 Current tests

`baseline/pytest_baseline.txt` and `pytest_baseline.xml`: **77 tests, 77 passed, 0 failures, 0 errors, 0 skipped, 5.77 s.** The slowest are the AppTest image-upload flow (1.14 s) and the video-upload flow (0.68 s). This is a *current* result, not the historical one.

### 4.9 Known issues entering the engineering phase

| # | Issue | Source | Evidence |
|---|---|---|---|
| K1 | Stale boxes on skipped frames (live and video) | code `camera_processor.py:96`, `video_processor.py:116` | REPORT-009 §5.2 simulation |
| K2 | Live imgsz 480 vs image 640 | `settings.yaml:42`, `app.py:283` | REPORT-009 §5.1 |
| K3 | No frame identity, capture timestamp or result-to-source link; latency not measured in the app | code | §4.3 |
| K4 | `settings.yaml:13` comment wrongly says NMS IoU is ignored (it is used: `nms=None` gives the one-to-many head + NMS) | code probe | REPORT-009 §C |
| K5 | Missing-PPE classes have low recall at small scale and in crowds; item ↔ missing-item confusion | this report §10 | measured |
| K6 | Webcam distribution shift | REPORT-009 §5.6 | 1 scene |
| K7 | The user's live session (480 px, every 3rd frame) recorded 2,403 no_helmet boxes against 2,187 Person boxes, plus helmet 943, goggles 486, vest 437, gloves 347 in an indoor session | `outputs/siteguard_events.db` inspections (counts only) | **Unverified:** no ground truth; images not viewed |

## 5. Files inspected

All of `app.py`, `src/**`, `tests/**`, `configs/**`, `scripts/**`, `requirements.txt` and `.streamlit/config.toml`. Also `.venv/…/streamlit_webrtc/process.py` (async queue and frame handling) and `.venv/…/ultralytics/{utils/nms.py, engine/predictor.py, nn/autobackend.py, utils/metrics.py (ConfusionMatrix), models/yolo/detect/val.py}`. The DB was read with SELECT only.

## 6. Files modified / created

**No existing file was modified.** Created:

| Path | Purpose |
|---|---|
| `experiments/engineering_phase/EXECUTION_LOG.md` | Phase-by-phase execution log |
| `experiments/engineering_phase/baseline/*` | Snapshot, manifests, environment, code map, model inventory, class-mapping check, pytest evidence |
| `experiments/engineering_phase/baseline/yolo26n/*` | Phase 1 evidence (see §10) |
| `scripts/engineering/hash_manifest.py` | Create/verify SHA-256 manifests (read-only on inputs) |
| `scripts/engineering/code_map.py` | AST code map |
| `scripts/engineering/evaluate_model.py` | Identical evaluation procedure for any checkpoint, to be reused for YOLO26m |
| `docs/reports/REPORT-010-…md` | This report |

## 7. Engineering decisions and alternatives

| Decision | Alternative considered | Reason |
|---|---|---|
| Preserve with a source tarball + SHA-256 manifests | `git init` + commit | Initialising Git changes the project's structure without being asked. Recommended to the user as an option instead. |
| Primary baseline = Ultralytics `val` defaults (conf 0.001, IoU 0.7) | The app's operating point only | Reproduces the historical numbers exactly. The operating point (conf 0.25, IoU 0.5) is reported separately and labelled as such. |
| Own confusion matrix at conf 0.25 | The Ultralytics matrix only | Ultralytics calls `process_batch(conf=self.args.conf)`, i.e. conf 0.001 during val, which inflates background counts and doesn't reflect the app |
| One evaluation script parameterised by weights | Separate scripts per model | Guarantees an identical procedure for YOLO26n and YOLO26m (spec §9) |

## 8. Implementation details (Phase 1 procedure)

`scripts/engineering/evaluate_model.py --weights models/trained/best.pt --name yolo26n --out experiments/engineering_phase/baseline/yolo26n`:
1. `YOLO.val(data=data/generated/dataset_resolved.yaml, split=val, imgsz=640, batch=8, device=mps, conf=0.001 (default), iou=0.7 (default), max_det=300)`.
2. Predictions for all 200 images at conf 0.001 / NMS IoU 0.5, saved to npz. These are scored at conf 0.25 with the audit evaluator, which was verified 60/60 identical to the app detector in REPORT-009.
3. Stratified recall by size, viewpoint, brightness tercile and image group.
4. Latency over 100 predicts.
5. Error examples.

Checkpoint sha256 `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b`, 5,443,013 bytes. Run started 20:52:40 and finished 20:52:53 (`run_config.json`). fp32.

## 9. Testing methodology

- Static verification: code map, class-mapping checks, hash verification against the pre-project baseline.
- Dynamic: the full pytest suite, MPS execution probe, model load and inference.
- Evaluator correctness is covered by 13 unit tests (`tests/test_live_audit.py`) and by the harness-equivalence check.

## 10. Actual measured results (Phase 1)

### 10.1 Overall (Ultralytics val defaults, 200 images, 2,961 instances)

| Metric | Reproduced | Historical | Match |
|---|---:|---:|---|
| Precision | **0.8322** | 0.832 | yes |
| Recall | **0.6809** | 0.681 | yes |
| mAP50 | **0.7339** | 0.734 | yes |
| mAP50-95 | **0.5227** | 0.523 | yes |

Ultralytics speed: preprocess 0.19 ms, inference 9.98 ms, postprocess 3.53 ms per image (batch 8). Validation wall time: 6.6 s.

At the **operating point** (conf 0.25, NMS IoU 0.5): P 0.884, R 0.745, TP 2206, FP 289, FN 755. The false positives break down as localization 137, wrong class 93, background 53, duplicate 6.

### 10.2 Per class

| Class | Val inst. | P | R | AP50 | AP50-95 | Op TP | Op FP | Op FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| helmet | 294 | 0.901 | 0.775 | 0.825 | 0.627 | 232 | 29 | 62 |
| gloves | 381 | 0.842 | 0.735 | 0.793 | 0.601 | 282 | 48 | 99 |
| vest | 340 | 0.936 | 0.829 | 0.887 | 0.685 | 285 | 13 | 55 |
| boots | 481 | 0.812 | 0.682 | 0.771 | 0.572 | 344 | 80 | 137 |
| goggles | 139 | 0.829 | 0.921 | 0.924 | 0.561 | 130 | 13 | 9 |
| Person | 481 | 0.933 | 0.896 | 0.940 | 0.781 | 434 | 23 | 47 |
| no_helmet | 179 | 0.894 | 0.553 | 0.652 | 0.383 | 110 | 17 | 69 |
| no_goggle | 82 | 0.382 | 0.128 | **0.148** | 0.045 | 14 | 16 | 68 |
| no_gloves | 203 | 0.898 | 0.564 | 0.620 | 0.384 | 115 | 19 | 88 |
| no_boots | 178 | 0.839 | 0.673 | 0.748 | 0.574 | 120 | 15 | 58 |
| forklift | 73 | 0.801 | 0.794 | 0.807 | 0.585 | 59 | 10 | 14 |
| no_vest | 130 | 0.920 | 0.619 | 0.692 | 0.475 | 81 | 6 | 49 |

### 10.3 Confusion at the operating point (`confusion_matrix_conf0.25.csv`)

- **Cross-class errors are almost all item ↔ own missing class:** boots on true no_boots 21; helmet on true no_helmet 13; vest on true no_vest 9; gloves on true no_gloves 5; no_vest on true vest 5; goggles on true no_goggle 4; no_helmet on true helmet 4; no_boots on true boots 4.
- **False boxes on background:** boots 61, gloves 43, Person 24, no_gloves 20, no_goggle 17, helmet 15, no_helmet 14, no_boots 13, forklift 10, goggles 9, vest 4, no_vest 1.
- **Missed:** boots 136, gloves 96, no_gloves 86, no_goggle 65, helmet 58, no_helmet 58, vest 49, Person 46, no_vest 41, no_boots 39, forklift 14, goggles 9.

### 10.4 Class investigation (recall at the operating point, `stratified_recall.csv`, `recall_by_crowding.json`)

| Class | Small / medium / large (area < 0.01 / 0.01–0.10 / ≥ 0.10) | Frontal / side / overhead* | Dark / mid / bright | 1–2 / 3–5 / 6+ persons |
|---|---|---|---|---|
| helmet | 0.69 (202) / 1.00 (92) / – | 0.96 / 0.95 / 0.60 | 0.71 / 0.83 / 0.83 | 0.98 / 0.76 / 0.45 |
| no_helmet | 0.47 (130) / 1.00 (49) / – | 0.92 / 0.93 / 0.31 | 0.79 / 0.56 / 0.44 | 0.92 / 0.41 / 0.48 |
| vest | 0.71 (178) / 0.99 (119) / 0.95 (43) | 0.97 / 1.00 / 0.70 | 0.84 / 0.82 / 0.85 | 0.98 / 0.85 / 0.58 |
| no_vest | **0.20 (59)** / 0.98 (46) / 0.96 (25) | 0.85 / 1.00 / 0.38 | 0.64 / 0.64 / 0.59 | 0.95 / 0.39 / 0.39 |
| gloves | 0.71 (340) / 1.00 (41) / – | 0.85 / 0.91 / 0.29 | 0.74 / 0.71 / 0.77 | 0.92 / 0.49 / 0.31 |
| no_gloves | 0.56 (200) / 0.67 (3) / – | 0.71 / 0.96 / 0.31 | 0.68 / 0.49 / 0.53 | 0.88 / 0.19 / 0.19 |
| boots | 0.61 (340) / 0.97 (141) / – | 0.92 / 0.98 / 0.39 | 0.70 / 0.71 / 0.73 | 0.97 / 0.53 / 0.21 |
| no_boots | 0.64 (149) / 0.83 (29) / – | 0.80 / 0.95 / 0.28 | 0.81 / 0.70 / 0.45 | 0.85 / 0.27 / 0.41 |
| goggles | 0.94 (128) / 0.91 (11) / – | 0.93 / 0.96 / 1.00 (2) | 0.97 / 0.98 / 0.80 | — |
| no_goggle | **0.17 (82)** / – / – | 0.18 / 0.09 / 0.20 | 0.14 / 0.10 / 0.25 | — |
| Person | 0.76 (186) / 0.98 (102) / 1.00 (193) | 0.94 / 0.97 / 0.85 | 0.93 / 0.87 / 0.91 | 0.98 / 0.89 / 0.81 |
| forklift | 0.50 (10) / 0.70 (27) / 0.97 (36) | 0.84 / 0.89 / 0.76 | 0.95 / 0.71 / 0.83 | — |

\*Viewpoint labels are AI-assisted thumbnail judgements (REPORT-003). They are not human-verified.

**Interpretation (measured patterns, with the causal reading kept separate):**
- **Scale.** Every PPE and missing-PPE class drops sharply below 1 % of image area.
- **Crowding.** Recall falls steeply with the number of people. This is the closest available proxy for occlusion: occlusion is **not annotated**, so it cannot be measured directly. Crowded images are also wide scenes with small objects, so crowding and scale overlap.
- **Viewpoint.** The overhead collapse coincides with wide scenes (the confound documented in REPORT-007).
- **Lighting.** By mean-brightness tercile there is no consistent effect; dark images are often *better*. The val set contains no truly dark imagery, so this does not contradict REPORT-009's synthetic darkening result.
- **Class ambiguity.** The item ↔ missing-item confusions are consistent with fine-grained ambiguity on small regions.

**no_goggle specifics:**
- All 82 val boxes are small eye-band boxes.
- A visual sample of 24 GT crops (`examples/no_goggle_gt_crops.jpg`) shows **ordinary eyeglasses labelled no_goggle** and at least one box on a face turned away from the camera.
- **Label coverage** (`label_coverage_per_person.json`): 53.6 % of 481 val persons have *neither* a goggles nor a no_goggle label. For comparison, helmet 5.0 %, vest 2.7 %, gloves 31.6 %, boots 29.5 % (hands and feet are often not visible).
- The weakness therefore comes from tiny objects, eyeglasses-vs-goggles ambiguity and inconsistent eye-region labelling, not only from too little data. Detailed label review is Phase 4.

### 10.5 Latency and loading (MPS, 640, 100 predicts on full-resolution val images; `latency.json`)

- Model load: 0.012 s.
- First predict, including backend setup and warm-up: 0.104 s.
- Wall time per image: mean 9.16 ms, median 9.41 ms, p95 11.02 ms, max 11.86 ms.
- Ultralytics components: inference mean 6.05 / median 7.79 / p95 9.05 ms; preprocess 0.73 ms; postprocess mean 2.32 ms.

## 11. Before/after comparison

There is nothing before/after for this phase: no change was made. Historical against reproduced metrics are in §10.1, and they are identical to 3 decimals.

## 12. Limitations and uncertainty

- 200 val images from the same distribution as training, so these are in-distribution figures.
- Viewpoint labels are AI-assisted.
- Occlusion is not annotated (crowding is a proxy).
- Brightness terciles are a coarse proxy for lighting.
- The no_goggle label review is a 24-crop sample.
- The latency figures include preprocessing of 1.5–2.0 MP images and are single-image (batch 1), so they are not the batch-8 val speed.

## 13. Known unresolved issues

K1–K7 (§4.9) remain open. K1–K4 are scheduled for Phase 2/3. K5 and K6 are model/data issues (Phases 4–8). K7 needs a physical-camera session with ground truth (Phase 8).

## 14. Exact reproduction

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
.venv/bin/python scripts/engineering/hash_manifest.py create experiments/engineering_phase/baseline
.venv/bin/python scripts/engineering/hash_manifest.py verify experiments/engineering_phase/baseline/dataset_manifest.csv
.venv/bin/python scripts/engineering/code_map.py experiments/engineering_phase/baseline/code_map.json
.venv/bin/python -m pytest -q --junitxml=experiments/engineering_phase/baseline/pytest_baseline.xml
.venv/bin/python scripts/engineering/evaluate_model.py --weights models/trained/best.pt --name yolo26n \
    --out experiments/engineering_phase/baseline/yolo26n
```

## 15. Conclusion

- The project is consistent and all protected assets are present and intact. Phase 0 stop conditions: none triggered.
- The YOLO26n baseline is reproduced exactly, with the configuration recorded.
- Weaknesses are concentrated in small objects, crowded scenes and the missing-PPE classes. no_goggle is also affected by label ambiguity.

## 16. Recommended next step

Phase 2/3: implement R1 (source-frame identity, no stale rendering, bounded/latest-frame policy, lifecycle, latency instrumentation) and R2 (single authoritative inference size, 640). Add the required tests. Report in REPORT-012.

**Proposed file changes for R1/R2:**
- `src/detection/camera_processor.py`
- `src/detection/video_processor.py`
- `app.py` (Live page status/latency display, live resolution control, minimal)
- `configs/settings.yaml` (live image size → use the main inference size; correct the NMS comment)
- new tests

**Protected files (will not be modified):** `models/trained/best.pt`, everything under `../construction-ppe/`, `outputs/` (user data), `experiments/live_audit/webcam/`, and all prior experiment artefacts.
