# FACTS — every number used in the deck

Columns: **Value** as printed on the slide · **Meaning** · **Split and size** (where a metric
applies) · **Source file** in the project.

## Project and data

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 1,000 | Labelled images in the dataset | whole dataset | `docs/DATASET.md` §4 |
| 800 | Training images | train split | `docs/DATASET.md` §4 |
| 200 | Validation images | validation split | `docs/DATASET.md` §4 |
| 2,961 | Labelled objects in validation | validation, 200 images | `docs/DATASET.md` §4 |
| 14,863 | Labelled boxes in the dataset | whole dataset | `docs/DATASET.md` §5 |
| 12 | Object classes | — | `configs/dataset.yaml` |
| 5 / 5 / 2 | PPE-present / PPE-missing / other classes | — | `configs/dataset.yaml` |
| 3 | Required PPE items (helmet, vest, gloves) | — | `configs/settings.yaml` `compliance.required_ppe` |
| CC BY 4.0 | Dataset licence | — | `docs/DATASET.md` §1 |
| 8 | Dashboard pages | — | `app.py` `PAGES` |

## Model and training

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 30 | Training epochs completed | train, 800 images | `docs/TRAINING.md` §5 |
| 1,273 s | Training duration | train, 800 images | `docs/TRAINING.md` §5 |
| 21 min | Training duration, rounded | train, 800 images | `docs/TRAINING.md` §5 (21.2 min) |
| 640 px | Input resolution | — | `configs/settings.yaml` `training.image_size` |
| 8 | Batch size | — | `configs/settings.yaml` `training.batch` |
| 2.57 M | YOLO26n parameters | — | `docs/TRAINING.md` §1 |
| 25 | Best epoch by fitness | validation | `docs/TRAINING.md` §5 |

## Accuracy — YOLO26n, validation split (200 images, 2,961 objects, 640 px)

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 0.832 | Precision at best-F1 confidence | val, 200 images | `experiments/evaluation/trained_best/metrics.json` |
| 0.681 | Recall at best-F1 confidence | val, 200 images | same |
| 0.734 | mAP50 | val, 200 images | same |
| 0.523 | mAP50-95 | val, 200 images | same |
| 0.884 | Precision at confidence 0.25 | val, 200 images | `experiments/accuracy_improvement/evaluation/dev_yolo26n_active_baseline/summary.json` |
| 0.745 | Recall at confidence 0.25 | val, 200 images | same |
| 0.940 | mAP50, Person | val, 481 objects | `metrics.json` |
| 0.924 | mAP50, goggles | val, 139 objects | same |
| 0.887 | mAP50, vest | val, 340 objects | same |
| 0.825 | mAP50, helmet | val, 294 objects | same |
| 0.807 | mAP50, forklift | val, 73 objects | same |
| 0.793 | mAP50, gloves | val, 381 objects | same |
| 0.771 | mAP50, boots | val, 481 objects | same |
| 0.748 | mAP50, no_boots | val, 178 objects | same |
| 0.692 | mAP50, no_vest | val, 130 objects | same |
| 0.652 | mAP50, no_helmet | val, 179 objects | same |
| 0.620 | mAP50, no_gloves | val, 203 objects | same |
| 0.148 | mAP50, no_goggle | val, 82 objects | same |

## Runtime — recorded webcam replay (149 frames, ~29.8 fps, MacBook Air M5)

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 149 | Frames in the replay | replay clip | `experiments/accuracy_improvement/qualification/realtime/realtime_webcam_replay.json` |
| 29.8 | Frames analysed per second, YOLO26n | 149 frames | same |
| 0 | Frames dropped, YOLO26n | 149 frames | same |
| 20.3 ms | Mean inference, YOLO26n | 149 frames | same (20.26 ms) |
| 24.8 ms | p95 inference, YOLO26n | 149 frames | same |
| 23.7 | Frames analysed per second, E3 | 149 frames | same |
| 31 | Frames dropped, E3 | 149 frames | same |
| 42.0 ms | Mean inference, E3 | 118 frames analysed | same (42.04 ms) |
| 30 fps | Camera frame rate assumed by the budget | — | `REPORT-025` §8 |
| 33.3 ms | Frame interval at 30 fps (1 ÷ 30 s); the same budget `REPORT-025` §8 uses | — | `REPORT-025` §8 (30 fps latency budget) |

## Bigger-model experiment (E3 = YOLO26m, 896 px)

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 0.854 | E3 mAP50 | dev, 200 images, 2,961 objects | `evaluation/dev_E3_m896/summary.json` |
| 0.628 | E3 mAP50-95 | dev, 200 images | same |
| 0.858 | E3 recall at 0.25 | dev, 200 images | same (0.8578) |
| 0.847 | E3 mAP50 | locked test, 160 images, 2,480 objects | `REPORT-025` §7 |
| 0.93 | Pre-registered mAP50 target — not met | locked test | `REPORT-025` §1 |
| 0.644 | E3 mAP50-95 | locked test, 160 images | `REPORT-025` §7 |
| 0.885 | E3 precision at 0.25 (95 % CI 0.863–0.906) | locked test, 2,480 objects | `REPORT-024` §A2 |
| 0.862 | E3 recall at 0.25 (95 % CI 0.832–0.890) | locked test, 2,480 objects | `REPORT-024` §A2 |
| 160 / 2,480 | Locked-test images / objects | locked test | `REPORT-024` §A1 |

## Limitations

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 0.615 | no_helmet recall at 0.25 | val, 179 objects | `dev_yolo26n_active_baseline/summary.json` |
| 0.567 | no_gloves recall at 0.25 | val, 203 objects | same |
| 0.171 | no_goggle recall at 0.25 | val, 82 objects | same |
| 0.674 | no_boots recall at 0.25 | val, 178 objects | same |
| 0.623 | no_vest recall at 0.25 | val, 130 objects | same |
| 0.90 | Recall target used by the programme | — | `REPORT-025` §1 |
| 0.592 | E3 mAP50 on real-site photos | locked test, 47 images | `REPORT-024` §A5 |
| 0.951 | E3 mAP50 on generated close-ups | locked test, 113 images | `REPORT-024` §A5 |
| 0.639 | mAP50-95, frontal | viewpoint val, 112 images | `docs/EVALUATION.md` §5.1 |
| 0.185 | mAP50-95, overhead | held-out, 219 images | `docs/EVALUATION.md` §5.1 |
| 178 | Possibly wrong labels, unreviewed | dataset audit | `REPORT-025` §9 |
| 205 | Tests in the automated suite | `pytest --collect-only` | collected 2026-11-24 |

## Rules quoted on slides

| Value | Meaning | Split and size | Source |
|---|---|---|---|
| 0.25 | Detection confidence threshold | — | `configs/settings.yaml` `inference.confidence_threshold` |
| 0.50 | NMS IoU threshold | — | `configs/settings.yaml` `inference.iou_threshold` |
| 0.40 | Worker (Person) confidence | — | `configs/settings.yaml` `compliance.person_confidence` |
| 0.50 | Missing-PPE confidence for a potential violation | — | `configs/settings.yaml` `compliance.violation_confidence` |
| 0.40 | PPE confidence for compliant evidence | — | `configs/settings.yaml` `compliance.evidence_confidence` |
| 3 | Consecutive analysed frames required | — | `configs/settings.yaml` `events.min_consecutive_hits` |
| 30 s | Repeat-suppression cooldown | — | `configs/settings.yaml` `events.cooldown_seconds` |

## Identity (not a metric)

JUNAID AHMAD · Reg. No. 12419395 · 471 Project · 26 November 2026 — supplied in the brief.
