# SiteGuard AI — ML handoff to the frontend work

**Date:** 2026-11-23. **From:** the YOLO26m accuracy programme (REPORT-018 to REPORT-025). **For:** whoever builds the professional frontend. The frontend redesign itself was out of scope for the ML programme and has not been started.

## 1. What the frontend gets

| | |
|---|---|
| **Production model (default and fallback)** | **YOLO26n**, registry key `yolo26n_baseline`, `models/trained/best.pt`, sha256 `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b`, image size 640 |
| **Research candidate (not in the app)** | YOLO26m `E3_m896`, key `yolo26m_e3_896_v1`, `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt`, sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`, image size 896, card `model_card.json` (status "not promoted") |
| **Promotion decision** | **Not promoted.** The candidate failed the pre-registered gates for accuracy (mAP50 0.847 < 0.93; P / R 0.885 / 0.862 < 0.90; missing-PPE recall 0.52–0.80 < 0.90) and for real time (p95 43 ms > 33 ms). YOLO26n stays active. The candidate can be added later as a labelled, non-default provisional option with the user's approval (REPORT-024 §B3) |
| **Tests** | 156 passed, 0 failed, 0 skipped (`pytest -q`, 2026-11-23 03:56) |
| **Data integrity** | Dataset unchanged (2,004 files). Events database and evidence not modified by the programme. Checkpoints unchanged |

## 2. Final metrics to show (and how to word them)

**Wording rules.** Never display a single "accuracy %". Always name the metric, the split, and its size and nature. Approved strings:

- **Candidate, locked test:** "YOLO26m candidate: mAP50 0.847, mAP50-95 0.644 on a 160-image held-out, in-distribution test set (not real-site validation)."
- **Candidate at the operating point:** "Precision 0.885 / recall 0.862 at detection confidence 0.25 (same test set)."
- **Production model:** "YOLO26n (active): mAP50 0.734, mAP50-95 0.523 on the 200-image development set."
  - Mark this number as development data. YOLO26n cannot be scored on the locked test, because it was trained on those images.
- **Not allowed:** "production-qualified", "93 % accurate", "real-world accuracy", "probability of violation".

**Per-class recall for missing PPE.** If a model-information page shows class results, show these (candidate, locked test, conf 0.25):

| Class | no_helmet | no_gloves | no_goggle | no_boots | no_vest |
|---|---|---|---|---|---|
| Recall | 0.739 | 0.650 | 0.522 | 0.796 | 0.688 |
| At the alert threshold 0.50 | 0.648 | 0.585 | 0.348 | 0.741 | 0.645 |

**Source of the numbers.** Read them from the model card (`ModelEntry.card_data()`) or from the evaluation JSON files (`experiments/accuracy_improvement/evaluation/<split>_<run>/summary.json`). Do not hard-code them.

## 3. Exact integration requirements

The backend is Python. The present Streamlit dashboard (`app.py`, 8 pages: Overview, Live Monitoring, Image Inspection, Video Inspection, Safety Events, Analytics, Model Evaluation, Settings / About) is the reference implementation of every contract below. A new frontend must keep these behaviours whatever technology it uses.

### 3.1 Model loading and identity

- **Loading.** Load the model only through `PPEDetector()` (`src/detection/detector.py`) with no `weights=` argument. It reads the registry in `configs/settings.yaml` (`model.active`, `model.fallback`, `model.registry`).
  - **Never** build a model from a raw file path in the UI.
  - Load it once per process and cache it, as `get_detector()` does with `st.cache_resource`.
- **What to display:** `PPEDetector.info()` returns:
  - `model_key`, `status` (`active` / `fallback` / `explicit weights`), `weights`, `exists`, `device`, `confidence`, `image_size`;
  - `load_errors` (if any);
  - when the weights file exists: `size_mb`, `sha256` (first 16 hex characters), `architecture` and `class_names`;
  - `model_card` when the registry entry has a card.

  Display the model key, architecture, image size and short SHA-256 permanently, for example in the sidebar.
- **Fallback state.** If `status == "fallback"`, show a visible warning containing `load_errors`. The active checkpoint was missing or incompatible, and YOLO26n is running instead.
- **Error state.** `ModelNotFoundError` or `IncompatibleModelError` (importable from `src.detection.detector`) means that no usable model exists. Show a blocking error state and **do not run inference**. Do not fall back to any other file.
- **Logs.** Model identity is logged by the `siteguard.model` logger to `outputs/logs/siteguard_app.log`.

### 3.2 Model selection and switching

- **Listing models.** `ModelRegistry.from_settings(load_settings())` (`src/detection/model_registry.py`) gives `.entries` (key → `ModelEntry` with `weights`, `architecture`, `image_size`, `card`, `description`, `card_data()`), `.active` and `.fallback`.
- **Switching.** To switch, write the chosen key to `model.active` in `configs/settings.yaml`, as the Settings page does. Then:
  1. Clear the cached settings (`load_settings.cache_clear()`) and the cached detector.
  2. Close the running live session and start a new one (`LiveFrameProcessor.close()`, then a new processor or `reset_session()`). Results from the previous model must never appear in the new session.
  3. **Do not** clear or recreate the events database.
- **Environment override.** The variable `SITEGUARD_MODEL=<key>` overrides `model.active` for one process. It is the emergency rollback switch, and the frontend must not unset it.
- **Settings file.** Only the `model.active` line may be changed from the UI. Thresholds and compliance settings are **read-only** in the UI (§3.4).

### 3.3 Image size per model

- Every model has its own inference size: 640 for YOLO26n, 896 for the candidate.
- Use `detector.image_size`. The pipelines take it from the detector or the registry when `image_size=None` is passed. **Never hard-code 640.**
- Returned boxes are always in the **source-frame pixel coordinates**, whatever the inference size (tested in `tests/test_resolution_coordinates.py`). Draw them on the original frame without rescaling.

### 3.4 Thresholds and compliance (read-only in the UI)

**Current values** (`configs/settings.yaml`):

| Section | Setting | Value |
|---|---|---|
| inference | `confidence_threshold` | 0.25 |
| inference | `iou_threshold` | 0.5 |
| compliance | `required_ppe` | helmet, vest, gloves |
| compliance | `person_confidence` | 0.40 |
| compliance | `violation_confidence` (alert threshold) | 0.50 |
| compliance | `evidence_confidence` | 0.40 |
| compliance | `min_containment` | 0.60 |
| compliance | `ambiguity_margin` | 0.15 |
| compliance | `person_box_margin` | 0.10 |
| compliance | `conflict_iou` | 0.50 |
| events | `cooldown_seconds` | 30 |
| events | `match_iou` | 0.30 |
| events | `min_consecutive_hits` | 3 |
| events | `candidate_timeout_seconds` | 3 |

**Rules:**
- Display these values; do not offer controls that change them. Changing them is a compliance-policy change that needs approval and re-qualification.
- Label any confidence number as **"detector confidence"**. Scores between 0.45 and 0.75 are under-confident (REPORT-023 §7.3), so they are not probabilities.
- Colour or label missing-PPE detections below 0.50 differently from alerts. They are drawn (≥ 0.25) but do **not** raise a violation.

### 3.5 Pipelines and their contracts

**Image:** `inspect_image(image_bgr, detector, analyzer, confidence=None, image_size=None) -> ImageInspection`, in `src/detection/image_processor.py`.
- Decode uploads with `decode_image_bytes(data, filename)`. It raises `InvalidImageError`, which must be shown as a user-facing error state.

**Video:** `process_video(input_path, output_path, detector, analyzer, event_manager=None, frame_stride=None, max_frames=None, confidence=None, image_size=None, progress=None, should_stop=None, write_frame_log=True) -> VideoSummary`, in `src/detection/video_processor.py`.
- Use `progress(fraction, message)` for a progress bar and `should_stop()` for a Cancel button.
- `InvalidVideoError` is a user-facing error state.
- With `frame_stride > 1`, frames that were not analysed are written **without boxes** and tagged "not analysed". Keep that tag visible.

**Live:** `LiveFrameProcessor(detector, analyzer, store, process_every_n=None, image_size=None, confidence=None, cooldown_seconds=None, source_name="browser webcam", min_consecutive_hits=None)`, in `src/detection/camera_processor.py`.
- **Feeding frames:** call `process_latest(frame_bgr, dropped=0, media_time_s=None)` (latest-frame policy) or `process(frame_bgr)` per delivered frame. The return value is the annotated frame **for that same frame**.
- **R1 invariant:** never draw boxes from an earlier frame on a later frame.
- **Status panel:** read `snapshot()` and show at least the fields below.

  | Field group | Fields |
  |---|---|
  | Session | `session_id`, `inference_imgsz` |
  | Frame rates | `received_fps`, `analysed_fps`, `rendered_fps` |
  | Frame counts | `frames_received`, `frames_dropped_queue`, `frames_analysed` |
  | Timing (`mean`/`median`/`p95`/`max`) | `inference_ms`, `receive_to_render_ms` |
  | Errors | `errors`, `error` |
  | Detections and events | `class_counts`, `last_detections`, `last_worker_rows`, `recent_events` |

  - **When `analysed_fps` < `received_fps`**, say so, for example "analysing 24 of 30 fps". The candidate at 896 px would do exactly that on the M5.
  - Do not claim a browser frame rate unless the frontend measures it.
- **Restarting the camera:** `reset_session()` gives a new session ID, so late results from the old session are discarded (tested).

**Compliance:** `ComplianceAnalyzer(ComplianceRules.from_settings(...))`, in `src/compliance/compliance_analyzer.py`. It returns per-worker assessments (`WorkerAssessment`, `ItemAssessment`).
- Each item status is one of three values:

  | Status value | Display label (`STATUS_LABELS`) |
  |---|---|
  | `potential_violation` | "Potential violation" |
  | `compliant_evidence` | "Compliant evidence" |
  | `uncertain` | "Uncertain / insufficient visual evidence" |

- Show the status as returned, using the labels from `STATUS_LABELS`. Do not recompute it in the UI.
- Never turn `uncertain` into "compliant".

### 3.6 Events, evidence and reports

- **Store.** `EventStore()` (`src/events/event_store.py`; database `outputs/siteguard_events.db`) provides:
  - `list_events(categories, sources, statuses, start, end, limit) -> DataFrame`;
  - `update_review_status(event_id, status, notes)`;
  - `count_events()`, `add_inspection(InspectionRecord)` and `list_inspections()`.
- **Event creation** is handled by `EventManager`:
  - an event persists only after 3 consecutive analysed frames;
  - it then has a 30 s cooldown per worker region and category;
  - the frontend **must not** create, merge or deduplicate events itself.
- **Evidence images** are in `outputs/evidence/`. Show them, but do not modify or delete them.
- **Database safety.** Never reset, migrate or delete the database from the UI. A model change must not touch it (tested).
- **Exports.** Use the existing events-CSV path (tested) for exports.

### 3.7 Classes

- Twelve classes, in fixed order, from `configs/dataset.yaml` (`class_names()` in `src/utils/paths.py`):

  | ID | Class | ID | Class |
  |---|---|---|---|
  | 0 | helmet | 6 | no_helmet |
  | 1 | gloves | 7 | no_goggle |
  | 2 | vest | 8 | no_gloves |
  | 3 | boots | 9 | no_boots |
  | 4 | goggles | 10 | forklift |
  | 5 | Person | 11 | no_vest |

- **Colours.** Use one fixed colour per class across all pages, with missing-PPE classes in a warning colour.
- **Hard-coding.** Do not hard-code the mapping; read it. The registry already refuses checkpoints with a different mapping.

### 3.8 Performance budget on the MacBook Air M5 (measured, REPORT-024 §B6)

| Model | Live inference mean / p95 (720p frames) | Analysed fps from a 30 fps camera |
|---|---|---|
| YOLO26n (active) | 20 / 25 ms | about 30 |
| YOLO26m candidate (896, not active) | 42 / 43 ms | about 24 (1 in 5 frames skipped) |

- The UI thread must never wait for inference. Keep the existing worker and latest-frame design.
- Heavy UI work (charts, tables) competes with the model for the same machine. Keep the live page light.

### 3.9 Privacy

- Camera frames are processed in memory. Only event evidence images are saved.
- `experiments/live_audit/webcam/` contains private frames. Never load it in the UI, upload it or commit it.
- No image, video or frame may be sent to an external service.

## 4. Remaining issues

The frontend should be aware of these.

1. **Missed violations.** The model misses many missing-PPE cases, especially tiny ones and no_goggle (recall 0.52). The UI must not imply complete coverage. Wording such as "potential violations detected" plus a model-limitations note is appropriate.
2. **Real scenes.** Real-site imagery performs much worse than close-ups (locked-test mAP50 0.59 against 0.95). Expect weaker results on wide site cameras.
3. **Unreviewed labels.** 178 suspect labels remain unreviewed (`annotation_review/review.html`). This is a human task, not a frontend task.
4. **Physical-camera test.** It is still pending: it needs the user present, and the camera turns on, with no frames saved.
5. **Test logging.** The test suite appends to the real `outputs/logs/siteguard_app.log`. This is minor; a test-only log path would be cleaner.
6. **Candidate in low light.** The candidate is weaker than YOLO26n in synthetic darkness, which is one more reason it is not the default.

## 5. Where everything is

- **Reports:** `experiments/accuracy_improvement/reports/` (REPORT-018 to REPORT-025). The decision is in REPORT-025, the gates and integration in REPORT-024, and the errors and thresholds in REPORT-023.
- **Programme overview and reproduction:** `experiments/accuracy_improvement/README.md`.
- **Model card:** `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/model_card.json`.
- **Registry code:** `src/detection/model_registry.py`. Detector: `src/detection/detector.py`. Reference UI: `app.py`.
- **Tests:** `tests/` (156). Model-related tests: `test_model_registry.py`, `test_accuracy_candidate.py`, `test_frame_sync.py`, `test_resolution_coordinates.py`.


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

