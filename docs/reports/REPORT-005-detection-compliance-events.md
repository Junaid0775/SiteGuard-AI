# REPORT-005 — Detection, Compliance Analysis and Event Management

**Date:** 2026-11-19 **Status:** Complete

## A. Task summary

- **Requested:** a detector using the custom checkpoint; an image, video and live preprocessing layer; a rule-based compliance analyzer with worker association and three statuses; event recording with deduplication; and CSV reporting.
- **Done:** all of these, each tested with synthetic cases *and* the real trained model.
- **Completion:** full.

## B. Technical implementation

- **`PPEDetector`** (`src/detection/detector.py`): loads `models/trained/best.pt` and checks that `task == "detect"`. Class names come from `model.names`, not a hard-coded list. `detect(img)` returns `Detection(class_id, class_name, confidence, x1, y1, x2, y2)`. Confidence, IoU, image size and device are configurable. A lock makes it safe across threads. `info()` returns the path, a sha256 prefix, the classes and the training source.
- **Preprocessing:** `decode_image_bytes` rejects bad files with clear errors: wrong extension, empty file, files over 25 MB, undecodable bytes, sides over 8,000 px. `process_video` validates the file, samples every Nth frame, reuses the last overlay on skipped frames, writes H.264 (`avc1`, falling back to `mp4v`), reports progress, and has a frame limit. `LiveFrameProcessor` analyses every Nth webcam frame at a smaller resolution.
- **Association and compliance:** implemented as specified in docs/ARCHITECTURE.md §3. The association score is containment × body-region factor × centring factor. When two workers score within 0.15, the box is ambiguous and goes to nobody. Statuses are potential violation, compliant evidence or uncertain. Only explicit `no_*` boxes ≥ 0.50 can raise a violation. A stronger overlapping PPE box turns the case into uncertain.
- **Events:** `EventManager` requires persistence (3 analysed frames for video and live, 1 for images) and applies a cooldown (30 s, same category with worker-box IoU ≥ 0.30). It saves an evidence JPG with the worker box outlined. `EventStore` is SQLite with an `events` and an `inspections` table, review statuses, filters and a per-call connection for thread safety.
- **Reports:** `report_generator.py` produces a CSV with the columns Date/time, Event category, Source, Source name, Confidence, Review status, Event ID, Worker, Video time, Evidence image and Reviewer notes, plus a summary dictionary.
- **Dependencies:** none added.

## C. Files created

| File | Purpose |
|---|---|
| `src/detection/detector.py` | Model wrapper and `Detection` dataclass |
| `src/detection/annotate.py` | Drawing of boxes and worker statuses |
| `src/detection/image_processor.py` | Image validation, decoding, single-image inspection |
| `src/detection/video_processor.py` | Video inspection and H.264 output |
| `src/detection/camera_processor.py` | `LiveFrameProcessor`, `OpenCVFrameSource` (future RTSP) |
| `src/compliance/worker_association.py` | Geometry and association |
| `src/compliance/compliance_analyzer.py` | Rules and statuses |
| `src/events/event_store.py` | SQLite storage |
| `src/events/event_manager.py` | Persistence, cooldown, evidence |
| `src/reporting/report_generator.py` | CSV reports |
| `scripts/make_test_video.py`, `data/test_media/test_site_clip.mp4`, `SOURCES.txt` | Test clip built from 6 val images (not real footage) |
| `tests/test_compliance.py`, `tests/test_events_and_reports.py`, `tests/test_image_and_model.py`, `tests/test_pipeline_integration.py`, `tests/conftest.py` | Tests |

## D. Files modified

| File | Change | Why |
|---|---|---|
| `src/events/event_store.py` | Added the `SITEGUARD_EVENTS_DB` environment override | Lets tests use a temporary database. Default behaviour is unchanged. |
| `src/detection/annotate.py` | Shorter worker labels ("W2 Potential: no helmet, no vest") at a smaller scale | Labels overlapped in crowded images (seen during visual inspection) |

## E. Commands executed

```bash
.venv/bin/python scripts/make_test_video.py
.venv/bin/python -m pytest tests/test_compliance.py tests/test_events_and_reports.py tests/test_image_and_model.py tests/test_pipeline_integration.py -q
.venv/bin/python - (real inference on val images 022 and source-00f1…, annotated output viewed)
.venv/bin/python - (full test-clip run: 270 frames)
```

## F. Testing and verification

| Test | What was tested | Result |
|---|---|---|
| `test_compliance.py` (15 tests) | IoU and containment, correct worker assignment, ambiguity between overlapping workers, unassigned items, never assigning one box twice, forklift ignored, negative gives violation, absence gives uncertain, all PPE gives compliant, low-confidence negative gives uncertain, conflict gives uncertain, low-confidence person ignored, ambiguous negative gives no violation, W-numbering, required-items config | PASS (15/15) |
| `test_events_and_reports.py` (10 tests) | Single image gives one event, 50-frame continuing violation gives one event, persistence, new event after cooldown, separate worker regions, compliant frames give no events, review update and filters, CSV columns and content, empty CSV headers, inspections and summary | PASS (10/10) |
| `test_image_and_model.py` (8 tests) | Unsupported, empty, corrupt and missing files; valid PNG; model loads with 12 dataset names; detection format and bounds on a real val image; bad input to `detect` | PASS (8/8) |
| `test_pipeline_integration.py` (4 tests) | Real image inspection; real video (90 frames, stride 5) with an output frame count and a dedup property check; invalid video; `LiveFrameProcessor` on real frames | PASS (4/4) after one test fix (see H) |
| Manual real-image check | `ultralytics-ppe-nov2026-022.jpg`: 8 Person boxes, 7 workers ≥ 0.40. W4 has helmet 0.89, vest 0.91 and gloves 0.91, giving compliant evidence. The others carry no_helmet/no_vest boxes, giving potential violations. 2 ambiguous and 1 unassigned item boxes created no event. Visually inspected: correct. `source-00f1…` (CCTV doorway): W1 has no_helmet 0.63, no_vest 0.90 and no_gloves 0.88, giving a potential violation. Visually correct. | PASS |
| Manual full-video check | Test clip, 270 frames at 15 fps, stride 5: 54 frames analysed in 2.7 s. 16 events, 105 repeats suppressed. Output is H.264 1280×720, 270 frames, and 16 evidence JPGs were written. | PASS |

## G. Model and dataset status

Uses `models/trained/best.pt` (REPORT-004). Default compliance thresholds: person 0.40, violation 0.50, evidence 0.40, containment 0.60, ambiguity 0.15, conflict IoU 0.50. Required PPE: helmet, vest, gloves. Goggles are excluded because `no_goggle` is unreliable (mAP50 0.148).

## H. Errors and resolutions

| Error | Root cause | Fix |
|---|---|---|
| `test_real_video_processing_with_dedup`: `assert 13 <= 10` | The test assumed at most 10 events. The second clip image actually shows about 8 workers, each with distinct categories (inspected: all 13 were distinct worker/category pairs, and 71 repeats were suppressed). The assumption was wrong; the code was correct. | Replaced the arbitrary bound with the real dedup property: no two events with the same category and an overlapping worker box within the cooldown, plus suppressed repeats > 0. |

## I. Acceptance criteria

| Criterion | Status |
|---|---|
| Detector processes a real image | PASS |
| Class names from the checkpoint, not hard-coded | PASS |
| Configurable confidence threshold | PASS |
| Rule-based association; one detection never linked to several workers | PASS |
| Three statuses; absence ≠ violation | PASS |
| Potential events from real detections | PASS |
| Event deduplication works | PASS |
| Event history, review, CSV export | PASS |
| Video processing works | PASS (on the generated test clip; no real footage available) |

## J. Remaining work and limitations

- No identity tracking: worker refs are per frame.
- The test clip is a slideshow of dataset images, not real CCTV footage.

## K. Next task

Dashboard and live camera (REPORT-006).
