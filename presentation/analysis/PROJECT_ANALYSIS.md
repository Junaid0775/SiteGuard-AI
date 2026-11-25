# SiteGuard AI — Project analysis

Every number below names the file it came from. The verified fact sheet supplied with the
brief was cross-checked; no disagreement was found except the test count, which the files
record at different points in time (see §8).

## 1. Problem and goal

Construction supervisors must confirm that workers wear PPE (personal protective
equipment: hard hat, hi-vis vest, gloves, boots, goggles). Manual checking of several
camera views is slow and misses moments. SiteGuard AI is an **academic computer-vision
prototype** that highlights *potential* PPE problems with annotated evidence so a person can
review them quickly. It is **decision support only**: detections are model observations, not
facts about the site (`README.md` §1, §14).

The project goals (`README.md` §2) are: detect 12 classes; associate PPE with individual
workers by box geometry; classify each worker as potential violation / compliant evidence /
uncertain; record deduplicated events with evidence and a human review status; provide a
dashboard for images, video and a live camera; and evaluate the model honestly, including a
viewpoint-generalisation experiment.

## 2. Architecture and data flow

Layers (`docs/ARCHITECTURE.md` §1–2):

1. **Input** — uploaded image, uploaded video, browser webcam over WebRTC
   (`streamlit-webrtc`), or an `OpenCVFrameSource` placeholder for RTSP.
2. **Preprocessing** — format/size validation, safe decode, video frame sampling.
3. **Detection** — fine-tuned YOLO26n `models/trained/best.pt` in `PPEDetector`, guarded by a
   lock because WebRTC calls back on a worker thread.
4. **Compliance** — `worker_association.py` links each PPE/missing-PPE box to one worker
   (10 % person-box margin, containment ≥ 0.60, body-region and centring factors, ambiguity
   margin 0.15, each box used once). `compliance_analyzer.py` decides a status per item.
5. **Events** — `EventManager` requires 3 consecutive analysed frames, then suppresses
   repeats for 30 s (IoU ≥ 0.30 to decide "same worker region"); `EventStore` writes SQLite
   and evidence JPGs.
6. **Presentation** — the Streamlit dashboard and CSV export.

Storage: `outputs/siteguard_events.db` with an `events` table (category, confidence, worker
box, media time, evidence path, review status, notes) and an `inspections` table (frames
analysed, Person count, per-class counts, settings). Raw uploads are deleted; only annotated
outputs and event evidence are kept (`docs/ARCHITECTURE.md` §5).

## 3. Dataset

- **Source:** Ultralytics Construction-PPE, November 2026, **CC BY 4.0**
  (`docs/DATASET.md` §1, `construction-ppe/LICENSE.txt`).
- **Size:** 1,000 labelled images, 800 train / 200 validation, 14,863 boxes; the validation
  split holds **2,961** boxes (`docs/DATASET.md` §4).
- **12 classes:** helmet, gloves, vest, boots, goggles, Person, no_helmet, no_goggle,
  no_gloves, no_boots, forklift, no_vest (`configs/dataset.yaml`).
- The original dataset is read-only: 2,004 files were SHA-256 hashed before work started and
  training reads a symlink mirror (`docs/DATASET.md` §2).
- Audit: 0 duplicate images, 0 undecodable images, 0 invalid label rows
  (`data/generated/dataset_validation.json`, summarised in `docs/DATASET.md` §5).
- Viewpoint labels (frontal 639, side 116, overhead 219, low-angle 13, unclear 13) were
  assigned by an AI assistant from thumbnails and are confounded with image style
  (`docs/DATASET.md` §6).

## 4. Model and training

Transfer learning from COCO-pretrained YOLO26n (2.57 M parameters), replacing the 80-class
head with a 12-class head (`docs/TRAINING.md` §1). Settings: 640 px input, 30 epochs, batch 8,
seed 42, patience 15, AdamW auto, Apple MPS (`configs/settings.yaml` `training:`).
Result: 30/30 epochs, best epoch 25, **1,273 s = 21.2 min** (~42 s/epoch, ~3.3 GB unified
memory) on a MacBook Air M5, 16 GB — `docs/TRAINING.md` §5. Software: Python 3.12.16,
torch 2.15.0, Ultralytics 8.4.215, macOS 27.0.1 (same table; `requirements.txt`).

## 5. Evaluation

**Standard validation** — `experiments/evaluation/trained_best/metrics.json`; split: official
validation, 200 images, 2,961 objects, 640 px, `model.val()` at conf 0.001.

| Metric | Value |
|---|---|
| Precision (max-F1 confidence) | 0.832 |
| Recall (max-F1 confidence) | 0.681 |
| mAP50 | 0.734 |
| mAP50-95 | 0.523 |

At the application's operating confidence of 0.25 on the same 200 images: precision 0.884,
recall 0.745 (`experiments/accuracy_improvement/evaluation/dev_yolo26n_active_baseline/summary.json`).

Per-class mAP50 (same file): Person 0.940, goggles 0.924, vest 0.887, helmet 0.825, forklift
0.807, gloves 0.793, boots 0.771, no_boots 0.748, no_vest 0.692, no_helmet 0.652,
no_gloves 0.620, no_goggle 0.148.

**Viewpoint experiment** — separate model trained only on 527 frontal training images
(`docs/EVALUATION.md` §5). mAP50-95: frontal 0.639 (112 val images), side 0.678 (116 held-out,
no drop), overhead **0.185** (219 held-out), low-angle 0.185 (13, too few). Overhead is
confounded with small objects and image style; training on all viewpoints raised overhead
val from 0.227 to 0.309 but did not close the gap.

**Runtime** — recorded webcam replay, 149 frames at ~29.8 fps, MacBook Air M5
(`experiments/accuracy_improvement/qualification/realtime/realtime_webcam_replay.json`):
YOLO26n analysed 29.8 fps, 0 frames dropped, inference mean 20.26 ms, p95 24.8 ms.

## 6. The bigger-model experiment (E3 = YOLO26m, 896 px)

**Development set (200 images, 2,961 objects)** — `evaluation/dev_E3_m896/summary.json`:
mAP50 0.854, mAP50-95 0.628, recall at 0.25 0.858, against YOLO26n's 0.734 / 0.523 / 0.745.
This set also selected the checkpoints, so it is optimistic (`REPORT-025` §2).

**Locked test, run once (160 images, 2,480 objects)** — `REPORT-025` §7,
`qualification/locked_test_analysis/comparison.json`: mAP50 **0.847** against a pre-registered
target of 0.93; mAP50-95 0.644; precision 0.885 (95 % CI 0.863–0.906); recall 0.862
(0.832–0.890). Missing-PPE recall 0.522–0.796 per class, target 0.90.

**Runtime:** E3 at 896 px analysed 23.7 fps with 31 of 149 replay frames dropped, inference
mean 42.0 ms — it cannot analyse every frame of a 30 fps camera (`REPORT-025` §8).

**Decision:** not promoted; YOLO26n stays the active and fallback model
(`REPORT-025` §1, `REPORT-024` Part B, `configs/settings.yaml` `model.active`).

## 7. Live camera pipeline and its engineering fixes

The browser sends 1280 × 720 frames over WebRTC; frames are processed in a worker thread and
drawn back into the video. Engineering work recorded in
`experiments/camera_quality_audit/reports/CAMERA-FIX-FINAL-REPORT.md`:

- **Start guard** — streamlit-webrtc 0.79.1 misread a jump in Streamlit's run count during
  START and stopped its own worker; a narrow guard fixed it (30/30 natural starts).
- **Return-video bitrate** raised from the library default (~1.5 Mbit/s) to 4 Mbit/s: shown fps
  29.8–29.9, encode p95 3.57 ms, CPU +1.8 points, PSNR 22.9 → 24.5 dB.
- **Uplink resolution hints** — received 1280 × 720 in 100 % of 3,024 frames, instead of
  640 × 360.
- **Video sizing** — the status panel stacks below 1200 px; on 1024 × 768 the stream grew from
  368 × 207 to 564 × 317, never upscaled, aspect ratio kept.
- **Fix 4/6** — overlays and evidence isolation (evidence images come from the source frame).
- **Still pending:** the physical-camera validation of the current build; all camera results
  are automated tests with Chrome's synthetic camera (`CAMERA-FIX-FINAL-REPORT.md` §1, §7).

`app.py` also states this on the Live Monitoring page (`CAMERA_VALIDATION` constant).

## 8. The dashboard (8 pages)

`app.py` `PAGES`: Overview, Live Monitoring, Image Inspection, Video Inspection, Safety Events,
Analytics, Model Evaluation, Settings / About.

- **Overview** — active model status, event/inspection totals, recent alerts, events by day.
- **Live Monitoring** — START/STOP webcam, every-frame analysis, fps/drop/latency panel,
  session saved on STOP.
- **Image Inspection** — multi-image upload, original vs annotated, per-worker compliance card,
  detection table, download, optional event recording.
- **Video Inspection** — upload, frame controls, real progress, annotated H.264 output,
  summary tables, events.
- **Safety Events** — filters, table, evidence preview, review status + notes, CSV export.
- **Analytics** — counts and Plotly charts from stored data only; no compliance percentage
  (no validated denominator).
- **Model Evaluation** — real validation metrics, per-class table, confusion matrix, training
  curves, viewpoint experiment, the E3 research results, limitations.
- **Settings / About** — read-only thresholds, model identity (registry key, SHA-256), class
  list, versions, disclaimer.

## 9. Testing

`pytest.ini` restricts discovery to `tests/`. `pytest --collect-only -q` reports **205 tests
collected** (2026-11-24). Historical counts in the reports: 166 passing (`README.md` §12,
2026-11-23 earlier), 189 passing (`CAMERA-FIX-FINAL-REPORT.md` §1), 204 passing, 0 skipped
(`FRONTEND-REDESIGN-FINAL-HANDOFF.md` gate table). The suite covers dataset parsing, model
loading and registry fallback, compliance and deduplication, SQLite review and CSV, real image
and video inference, live frame synchronisation and stale-box prevention, and all 8 pages via
Streamlit `AppTest`. Only collection was run for this deck, as instructed.

## 10. Limitations and future work

From `README.md` §14 and `REPORT-025` §9: missing-PPE recall is below 0.90 for every class
(no_helmet 0.615, no_gloves 0.567, no_goggle 0.171, no_boots 0.674, no_vest 0.623 at conf 0.25
— `dev_yolo26n_active_baseline/summary.json`); real-site photos reach mAP50 0.592 against 0.951
on generated close-ups (E3, locked test); overhead views collapse (0.185 vs 0.639 mAP50-95);
178 suspect labels are unreviewed; no identity tracking, so worker labels are per frame and no
compliance rate is claimed; the dataset is one public, partly generated source; physical-camera
validation is pending; detector confidence is not a calibrated probability (calibration error
0.107 for missing-PPE, `REPORT-025` §6).

Future work (`README.md` §15, `REPORT-025` §11): multi-object tracking for persistent worker
IDs, RTSP/CCTV input, site-specific fine-tuning on consented real footage, per-zone PPE rules,
label review, a faster 896 px path, and multiple seeds.
