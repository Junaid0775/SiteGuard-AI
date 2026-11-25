# SiteGuard AI — Project map

Inventory of the project folder, taken 2026-11-24. Private media (`outputs/evidence/`,
`outputs/videos/`, `experiments/live_audit/webcam/`), binary weights (`*.pt`, `*.onnx`,
`*.engine`), the events database (`*.db`), dataset image folders and environment/cache
folders (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ultralytics/`, `node_modules/`) are
deliberately excluded and were not opened.

## Top level (`~/Desktop/471 Project/`)

| Path | Contains |
|---|---|
| `SiteGuard-AI/` | The application, training, evaluation, tests and all reports (detailed below). |
| `construction-ppe/` | The read-only source dataset: `images/`, `labels/`, `data.yaml`, `manifest.jsonl`, `README.md`, `LICENSE.txt` (CC BY 4.0). 2,004 files. |

## `SiteGuard-AI/` — application root

| Path | Contains |
|---|---|
| `app.py` | The whole Streamlit dashboard: theme, sidebar navigation, 8 page functions (1,207 lines). |
| `README.md`, `requirements.txt`, `pytest.ini` | Purpose, pinned dependencies, test discovery config. |
| `SiteGuard_AI_Master_Engineering_Specification.md` | Original engineering specification: scope, rules, acceptance. |
| `SiteGuard_AI_Frontend_Completion_Master_Specification.md` | Specification for completing the dashboard. |
| `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` | Specification for the accuracy programme (93–95 % ambition, promotion gates). |
| `.streamlit/config.toml` | Dark theme, orange accent, telemetry off. |
| `assets/images/` | The cinematic construction background used by the dashboard and this deck. |
| `static/` | `siteguard_background.webp` — cached background served to the dashboard. |
| `configs/` | `settings.yaml` (model registry, thresholds, events, training) and `dataset.yaml` (12-class mapping). |
| `src/` | All application code (see below). |
| `scripts/` | Training/evaluation helper scripts plus `accuracy/` and `engineering/` experiment runners. |
| `tests/` | 21 pytest modules covering dataset, model, compliance, events, UI and camera. |
| `models/pretrained/` | `yolo26n.pt`, `yolo26m.pt` COCO checkpoints (weights not read). |
| `models/trained/` | `best.pt`, `last.pt`, `MODEL_SOURCE.json`, `yolo26m_accuracy_candidate/` (model card only read). |
| `data/` | Dataset mirror (symlinks), generated YAMLs, viewpoint metadata/sheets, test clip, baseline checksums. |
| `experiments/` | Every training run, evaluation, audit and report (see below). |
| `outputs/` | Events DB, evidence frames, annotated media, reports, logs (private media not opened). |
| `docs/` | Architecture, dataset, annotation policy, training, evaluation, implementation log, reports. |
| `presentation/` | This deck, its analysis, speaker script and QA sheet. |

## `SiteGuard-AI/src/`

| Path | Contains |
|---|---|
| `detection/` | `detector.py` (YOLO wrapper, thread lock), `model_registry.py` (validated loading, fallback), `image_processor.py`, `video_processor.py`, `camera_processor.py` (WebRTC/OpenCV sources), `annotate.py` (box drawing). |
| `compliance/` | `worker_association.py` (geometry scoring), `compliance_analyzer.py` (3 statuses, required PPE). |
| `events/` | `event_manager.py` (persistence, IoU matching, 30 s cooldown), `event_store.py` (SQLite, review status). |
| `evaluation/` | `evaluate.py` (Ultralytics val → metrics.json), `viewpoint_evaluation.py` (frontal-only experiment), `live_audit.py`. |
| `training/` | `train.py` (transfer learning, resume, checkpoint promotion, metadata). |
| `reporting/` | `report_generator.py` (CSV export with disclaimer). |
| `ui/` | `theme.py` (tokens, CSS), `components.py` (KPI cards, panels), `live_video.py` (camera, start guard, uplink hints), `evaluation_data.py`. |
| `utils/` | `paths.py`, `dataset_tools.py` (validation, mirror, YAML generation), `logging_config.py`, `diagnostics.py`. |

## `SiteGuard-AI/docs/`

| Path | Contains |
|---|---|
| `docs/*.md` | `ARCHITECTURE`, `DATASET`, `ANNOTATION_POLICY`, `TRAINING`, `EVALUATION`, `IMPLEMENTATION_LOG`. |
| `docs/reports/` | 17 phase reports (REPORT-001 … 017): audit, setup, dataset, training, pipeline, dashboard, evaluation, live audit, engineering phase. |
| `docs/frontend_redesign/` | Reference-locked frontend specification. |
| `docs/presentation/` | The master prompt used to build this deck. |

## `SiteGuard-AI/experiments/`

| Path | Contains |
|---|---|
| `siteguard_yolo26n/` | The production training run: `args.yaml`, `results.csv`, `training_metadata.json`. |
| `evaluation/trained_best/` | `metrics.json` — the standard validation numbers used in this deck. |
| `viewpoint_frontal_only/`, `viewpoint_results/` | Frontal-only model run and per-viewpoint metrics JSON. |
| `resume_test/`, `smoke_test/` | Interrupted-training resume test and a 1-epoch smoke run. |
| `dataset_audit/` | Box inventories, duplicates, class distribution, suspect annotations. |
| `engineering_phase/` | Baseline metrics, R1/R2 pipeline measurements, realtime validation. |
| `live_audit/` | Camera-condition audits (colour, latency, object scale, overlay staleness) — private webcam subfolder excluded. |
| `accuracy_improvement/` | The 2026-11-20 → 23 accuracy programme: `data_audit/`, `splits/`, `training/` (E1–E5), `evaluation/` (dev/test), `qualification/` (locked test, realtime), `reports/REPORT-018…025`. |
| `yolo26m/` | Early YOLO26m smoke runs, validation and visual comparisons. |
| `camera_quality_audit/` | Camera start diagnostics, fixes 1–6, bitrate/sizing benchmarks, reports. |
| `frontend_completion/` | Dashboard completion reports 001–006, backups, screenshot tool. |
| `frontend_redesign/` | Reference-locked redesign: backups per phase, `evidence/` screenshots, reference image, reports 001–008 and final handoff. |
| `detect/` | Ultralytics prediction output directory. |
| `*.log` | Console logs of training, evaluation and live audits. |

## `SiteGuard-AI/scripts/`

| Path | Contains |
|---|---|
| `scripts/*.py` | Contact sheets, viewpoint metadata builder, test-video builder, webcam capture. |
| `scripts/accuracy/` | Programme runners: integrity manifest, dataset audit, splits, tiling, evaluation, comparison, promotion, matrix. |
| `scripts/engineering/` | Code map, dataset audit, model comparison, realtime evaluation, R1/R2 measurement, YOLO26m smoke. |
