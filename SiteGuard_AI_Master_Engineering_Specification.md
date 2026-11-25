# SITEGUARD AI — MASTER ENGINEERING EXECUTION SPECIFICATION

## Live Pipeline Engineering, Dataset Quality Assurance, YOLO26m Fine-Tuning, Comparative Evaluation, and Real-Time Validation

**Project:** SiteGuard AI  
**Project type:** Intelligent Real-Time Construction Site PPE Compliance Monitoring System  
**Workspace:** `~/Desktop/471 Project/SiteGuard-AI/`  
**Machine:** MacBook Air M5, 16 GB unified memory  
**Dashboard:** `http://localhost:8502`  
**Current production checkpoint:** `models/trained/best.pt` (existing YOLO26n)  
**Execution agent:** Claude Code in VS Code

---

# 0. MISSION AND RESPONSIBILITIES

Act as the lead computer-vision engineer, machine-learning engineer, Python application engineer, QA engineer, and technical documentation engineer for the next SiteGuard AI engineering phase.

Your responsibility is to inspect the real project, preserve existing work, diagnose the known problems, implement the required pipeline corrections, audit the dataset, prepare and train YOLO26m when prerequisites pass, compare it fairly with YOLO26n, validate real-time behaviour, and produce detailed evidence-backed reports.

This is an implementation and verification assignment, not a request for suggestions.

## 0.1 Non-negotiable rules

1. Inspect the actual repository before modifying anything. Existing source code and current execution results are authoritative; historical summaries are clues, not proof.
2. Preserve all existing user changes, working features, original data, checkpoints, logs, and reports.
3. Never overwrite `models/trained/best.pt`.
4. Never modify the original dataset in place.
5. Do not silently change class IDs, class names, compliance rules, thresholds, or model architecture.
6. Do not fabricate metrics, tests, screenshots, logs, training results, or conclusions.
7. Do not call precision, recall, or mAP “accuracy.”
8. Do not claim 93–95% performance unless a clearly defined and valid metric actually measures that result.
9. Do not optimize one model on the validation set and then present the result as an unbiased comparison.
10. Do not redesign the frontend. Make only the smallest UI changes necessary to expose correct pipeline status and measurements.
11. Do not push to GitHub, publish, deploy, or expose the project publicly.
12. Do not upload private webcam images or videos to external services.
13. Do not delete existing data or private webcam evidence without explicit authorization.
14. Use isolated directories for new experiments.
15. Record exact commands, configurations, dependency versions, hardware, hashes, logs, and outcomes.
16. If a prerequisite fails, stop the affected phase, document the blocker, and do not conceal it.
17. Do not run destructive Git commands or discard uncommitted changes.
18. Do not replace the production model automatically. A production checkpoint switch requires explicit user approval.

## 0.2 Required engineering sequence

Follow this order:

**Discover → Preserve → Baseline → Diagnose → Implement R1/R2 → Test → Audit dataset → Check YOLO26m readiness → Train → Evaluate → Compare → Real-time validate → Report.**

Do not jump directly to model training.

---

# 1. EXISTING PROJECT CONTEXT

SiteGuard AI detects people, PPE, and explicitly annotated missing-PPE conditions in construction-related images and video.

The existing application has these sections:

1. Overview
2. Live Monitoring
3. Image Inspection
4. Video Inspection
5. Safety Events
6. Analytics
7. Model Evaluation
8. Settings/About

Existing capabilities include YOLO object detection, image and video inspection, webcam monitoring, PPE compliance interpretation, event generation, evidence-image storage, review status, analytics, and CSV export.

The user has confirmed that the dashboard and webcam startup work. Detection quality and live visual reliability remain concerns.

Historical reports state that the project previously had 77 passing tests. This is not a current result: rerun the tests and report the actual result.

## 1.1 Existing YOLO26n model

The existing fine-tuned YOLO26n checkpoint is:

`models/trained/best.pt`

It was reportedly fine-tuned for 30 epochs. Historical training time was approximately 21.2 minutes on the M5 GPU, but do not assume that time will repeat.

Previously reported validation metrics on 200 validation images:

| Metric | Historical result |
|---|---:|
| Precision | 0.832 |
| Recall | 0.681 |
| mAP50 | 0.734 |
| mAP50-95 | 0.523 |

The previously weakest class was `no_goggle`, with historical mAP50 of 0.148.

These are historical reference values. Reproduce the metrics and record the exact evaluation configuration before treating them as the formal baseline.

Metric definitions:
- **Precision:** proportion of predicted detections that are correct.
- **Recall:** proportion of ground-truth objects successfully detected.
- **mAP50:** mean average precision at IoU 0.50.
- **mAP50-95:** mean average precision averaged over IoU thresholds 0.50 through 0.95.

Do not substitute one metric for another.

## 1.2 Original dataset

Original dataset path:

`/Users/junaidahmad/Desktop/471 Project/construction-ppe/`

Expected structure:

```text
construction-ppe/
├── images/
│   ├── train/
│   └── val/
├── labels/
│   ├── train/
│   └── val/
├── data.yaml
├── LICENSE.txt
├── manifest.jsonl
└── README.md
```

Previously verified counts:

| Property | Historical count |
|---|---:|
| Training images | 800 |
| Validation images | 200 |
| Training labels | 800 |
| Validation labels | 200 |
| Total annotations | 14,863 |
| Missing image-label pairs | 0 |
| Labels without matching images | 0 |
| Structurally invalid annotation rows | 0 |
| Classes | 12 |

Structural validity does not prove visual annotation correctness. Recalculate all counts.

### Authoritative class mapping

| ID | Class |
|---:|---|
| 0 | helmet |
| 1 | gloves |
| 2 | vest |
| 3 | boots |
| 4 | goggles |
| 5 | Person |
| 6 | no_helmet |
| 7 | no_goggle |
| 8 | no_gloves |
| 9 | no_boots |
| 10 | forklift |
| 11 | no_vest |

Do not reorder or rename classes casually. Verify the mapping across labels, YAML, checkpoints, inference output, compliance rules, event storage, and visualizations.

Never overwrite the original dataset. Any proposed corrected dataset must be a separate version with a change log and traceability to original files.

## 1.3 Previously reported live audit findings

A previous audit (REPORT-009) reported the following. Re-verify against the actual implementation and reproduce where feasible.

### R1: stale bounding boxes

The earlier live pipeline reportedly analysed every third frame, and video every fifth frame, but drew old detections on newer frames that had not been analysed. This caused boxes to lag behind moving subjects.

Historical simulated-motion displayed precision:
- Live: 0.79
- Video: 0.35

These are historical results, not guaranteed reproducible values.

### R2: inconsistent inference size

Historical settings:
- Live inference: `imgsz=480`
- Image inference: `imgsz=640`

A previous site-image test reported:
- mAP50-95 at 480: 0.454
- mAP50-95 at 640: 0.514
- Recall at 480: 0.676
- Recall at 640: 0.745

The reported speed saving at 480 was less than 1 ms/frame in that test. Reproduce or mark these figures unverified.

Target: standardize live inference to 640 for parity with image inspection, unless controlled measurements reveal a documented reason not to.

### Webcam distribution shift

A prior audit captured 149 webcam frames and manually reviewed 10. Reported errors included low-confidence missing-PPE false positives, flickering detections, oversized or misplaced boxes, and conflicting detections.

Examples included a `no_helmet` box covering much of a head, a `no_vest` box on unrelated furniture, and doubled detections around a head.

The sample was limited and does not represent all cameras or construction sites. Errors reportedly appeared in image inspection as well as live monitoring, suggesting model/domain-shift issues in addition to pipeline issues.

### Other historical findings

Motion blur, dim lighting, conflicting PPE classes, and low WebRTC startup bitrate reportedly affected results. These are hypotheses to investigate, not universal conclusions.

---

# 2. PHASE 0 — PROJECT DISCOVERY AND PRESERVATION

Begin here. Do not train YOLO26m yet.

## 2.1 Inspect repository structure

Inspect and map:
- Application entry point.
- Dashboard/frontend.
- Detection and inference pipeline.
- Model loading.
- Webcam capture.
- Video processing.
- Image processing.
- Compliance engine.
- Event generation and persistence.
- Evidence storage.
- Configuration files.
- Dataset YAML.
- Training and evaluation scripts.
- Tests.
- Reports.
- Experiment directories.
- Checkpoints.
- Dependency and lock files.

For each important module, document path, responsibility, key functions/classes, inputs, outputs, callers, dependencies, side effects, existing tests, and modification risks.

Do not infer architecture from old reports. Trace actual function calls and data flow.

## 2.2 Record Git state safely

Record:
- Current branch and commit.
- Uncommitted tracked changes.
- Untracked files.
- Ignored files.
- Existing tags and remotes.

Do not discard changes. Do not use `git reset --hard`, `git clean -fd`, or commands that revert the user's work. Do not push.

## 2.3 Hash protected assets

Calculate SHA-256 hashes and file sizes for:
- `models/trained/best.pt`
- Other existing checkpoints.
- Original dataset files or a complete dataset manifest.
- Important configurations.
- Existing experiment artifacts.

Store the manifest under:

`experiments/engineering_phase/baseline/`

Include path, size, hash, timestamp, and role.

## 2.4 Record environment

Record macOS version, Python, PyTorch, Ultralytics, OpenCV, Streamlit if used, NumPy, CPU architecture, MPS availability, CUDA availability, available disk space, and memory pressure.

Check both:

```python
torch.backends.mps.is_available()
torch.backends.mps.is_built()
```

Verify actual device execution. Do not claim MPS acceleration solely because the machine is Apple Silicon.

Do not upgrade the main environment casually. If compatibility changes are required, explain them and isolate the environment where practical.

## 2.5 Phase 0 report

Create:

`docs/reports/REPORT-010-phase0-project-discovery-and-baseline.md`

Include architecture, directory overview, environment, Git state, protected hashes, model inventory, dataset location, current tests, known issues, proposed file changes, and protected files.

Stop if the project is inconsistent or important assets are missing.

---

# 3. PHASE 1 — REPRODUCIBLE YOLO26n BASELINE

Use the existing checkpoint without overwriting it.

Record:
- Checkpoint path, size, SHA-256.
- Architecture and parameter count if available.
- Number of classes and class-name mapping.
- Input size.
- Confidence threshold.
- NMS IoU threshold.
- Maximum detections.
- Device and precision mode.
- Ultralytics/PyTorch versions.

Re-run validation on the existing validation split. Record the exact dataset YAML, image size, confidence threshold, IoU threshold, device, batch size, split, checkpoint hash, and timestamp.

Produce:
- Precision and recall.
- mAP50 and mAP50-95.
- Per-class precision, recall, AP50, AP50-95.
- Confusion matrix.
- False-positive and false-negative analysis.
- Inference latency and model load time.
- Validation instance count per class.

Investigate all 12 classes, particularly the paired PPE and missing-PPE classes. Do not assume that a poor class only needs more data. Inspect object scale, occlusion, labels, viewpoints, lighting, and class ambiguity.

Store outputs under:

`experiments/engineering_phase/baseline/yolo26n/`

Include configuration, logs, plots, examples, metrics, and hashes.

---

# 4. PHASE 2 — R1: CORRECT FRAME/DETECTION SYNCHRONIZATION

This is a critical correctness issue.

## 4.1 Trace the existing pipeline

Inspect actual frame acquisition, preprocessing, inference, result creation, rendering, display refresh, live callbacks, video playback, threads, queues, and session lifecycle.

Understand whether the app is synchronous, threaded, asynchronous, queue-based, Streamlit-driven, WebRTC-driven, or uses another architecture. Do not introduce a new concurrency design without understanding the existing one.

## 4.2 Frame identity

Every captured frame must have a unique frame identity and capture timestamp. Every inference result must retain the identity and timing of the exact source frame.

Conceptual structures:

```python
FramePacket(
    frame_id=...,
    captured_at=...,
    frame=...
)
```

```python
DetectionPacket(
    source_frame_id=...,
    inference_started_at=...,
    inference_completed_at=...,
    detections=...
)
```

Adapt to the existing codebase. The requirement is traceable source-frame identity, not these exact class names.

## 4.3 Correct rendering

A detection result must only be rendered on its source frame unless a separately implemented and validated tracking/association mechanism explicitly maps it to another frame.

Required sequence:
1. Capture frame N.
2. Assign frame ID N.
3. Run inference on frame N.
4. Tag result with source frame ID N.
5. Render the result on frame N.
6. Display the correctly annotated frame.

If frame N+1 arrives before inference for N completes, never silently draw N's boxes on N+1. Handle pending frames according to the actual architecture.

## 4.4 Backpressure and queue policy

Inspect for unbounded queues. Prevent unlimited frame accumulation.

For live monitoring, use an architecture-appropriate bounded/latest-frame strategy:
- Prefer fresh frames.
- Drop obsolete pending frames when required.
- Count and report dropped frames.
- Never apply stale boxes to a different frame.
- Avoid unbounded memory growth.

Live and offline video requirements differ. Live monitoring prioritizes freshness and latency. Offline video should process all frames or use an explicitly documented sampling policy. Do not silently skip offline frames.

## 4.5 Thread safety and session lifecycle

Ensure:
- A frame is not mutated while another thread reads it.
- Results cannot be partially updated while rendering.
- Frame IDs do not collide across sessions.
- Camera restart invalidates prior-session results.
- Inference exceptions do not deadlock the pipeline.
- Stop releases capture and worker resources.
- A prior session cannot leak boxes into a new session.
- Application shutdown is safe.

Use synchronization appropriate to the actual architecture; do not add unnecessary locks.

## 4.6 Measure frame age and latency

Use a monotonic clock for durations. Record capture, inference start, inference completion, and display timestamps.

Measure:
- Mean, median, P95, and maximum inference latency.
- Frame-to-display latency.
- Detection-result age at display.
- Captured, processed, displayed, and dropped frame counts.

Do not estimate FPS from the camera's nominal FPS. Measure actual capture, inference, and display rates separately.

## 4.7 R1 tests and acceptance

Test:
- Result for N completes after N+1 arrives.
- No result for N is rendered on N+1.
- Correct result is rendered on its source frame.
- IDs remain unique.
- Queue remains bounded.
- Drops are counted.
- Camera restart invalidates old results.
- Exceptions do not permanently block processing.
- Stop releases resources.
- No prior-session result appears in a new session.

Use deterministic frames and mocked inference for unit tests. Physical-camera tests are separate hardware integration tests.

Accept R1 only when source-frame association is correct, stale boxes are eliminated, queue behaviour is bounded, lifecycle is safe, latency is measurable, and compliance/event regressions pass.

If a safe correction requires a major redesign, stop and document the issue rather than implementing a fragile workaround.

---

# 5. PHASE 3 — R2: STANDARDIZE LIVE INFERENCE TO 640

Search the whole project for inference-size settings and hardcoded values. Distinguish:
- Model inference resolution.
- Original camera resolution.
- Display resolution.
- Evidence-image resolution.

Set live inference to `imgsz=640`, matching image inspection, unless controlled evidence demonstrates a material reason not to. Document video inference configuration explicitly.

Where practical, use one authoritative inference configuration rather than duplicated hardcoded values.

Verify coordinate transforms:
- Original dimensions.
- Resized input dimensions.
- Letterbox padding.
- Scale factors.
- Box conversion back to original coordinates.
- Display resizing.
- Evidence-image coordinates.

Test portrait and landscape images, different aspect ratios, and different camera resolutions. Ensure boxes remain aligned and within bounds.

Do not change unrelated display or evidence resolutions.

Acceptance:
- Live inference uses 640.
- Image inference uses 640.
- Video configuration is explicit.
- Coordinate conversion is correct.
- Tests pass.
- Latency impact is measured.

Do not lower resolution simply to claim higher FPS. Report measured trade-offs.

---

# 6. PHASE 4 — DATASET QUALITY AND ANNOTATION AUDIT

Create an isolated audit workspace:

`experiments/dataset_audit/`

Never modify original images or labels.

## 6.1 Inventory and structural validation

Recalculate:
- Train/validation images and labels.
- Total annotations.
- Missing image-label pairs.
- Labels without images.
- Empty labels.
- Duplicate filenames.
- Unsupported or unreadable images.
- Invalid rows and class IDs.
- Out-of-range normalized coordinates.
- Zero/negative box dimensions.

Record image dimensions, min/max/mean/median width and height, and aspect ratios.

## 6.2 Class distribution

For all 12 classes calculate:
- Training and validation instance counts.
- Percentage of annotations.
- Number of images containing the class.
- Mean, median, minimum, and maximum box area.
- Distribution of object sizes.

Generate readable CSVs and charts. Investigate imbalance rather than automatically duplicating or oversampling examples.

## 6.3 Bounding-box scale

Calculate normalized and pixel-space box dimensions and areas. Define the size thresholds used by the audit. One possible normalized-area grouping is:
- Small: area below 0.01.
- Medium: 0.01 to below 0.10.
- Large: 0.10 or greater.

These are project audit categories, not universal standards. Explain the thresholds and count examples per class and category. Pay particular attention to goggles, gloves, boots, and distant helmets.

## 6.4 Duplicate and leakage investigation

Use cryptographic hashes for exact duplicates and a documented perceptual-hash method for near-duplicates. Report:
- Duplicate group.
- Paths.
- Split membership.
- Hash/similarity score.
- Review status.

Investigate train/validation leakage. Do not automatically delete or move anything. If a corrected split is proposed, create a separate experiment with traceability and preserve the original split.

## 6.5 Visual annotation review

Generate review sheets with ground-truth boxes and class labels. Sample systematically across:
- Every class.
- Rare classes.
- Small and large boxes.
- Crowded scenes.
- Different viewpoints.
- Difficult lighting.
- Occlusion.

Inspect missing, misplaced, oversized, undersized, duplicate, or incorrectly classified boxes; ambiguous PPE; unsupported missing-PPE labels; and person/PPE association problems.

Document how many images were reviewed and how they were selected. Never claim all annotations were manually verified if only a sample was inspected.

## 6.6 Suspect annotation report

Create:

`experiments/dataset_audit/suspect_annotations.csv`

Suggested columns:
`image_path, split, class_id, class_name, bbox_x, bbox_y, bbox_width, bbox_height, issue_type, reason, review_priority, reviewer_status, notes`

This is a review list. Do not auto-correct labels.

## 6.7 Viewpoint metadata

Inspect `data/viewpoint_metadata.csv` if it exists. Historical viewpoint labels were AI-assisted thumbnail judgements and were not independently human-verified. Do not describe them as human-verified ground truth.

Report counts of frontal, side, overhead, and ambiguous images, split distribution, and label reliability. Mark uncertainty honestly. Do not silently change prior experiment labels.

## 6.8 Dataset report and artifacts

Create:

`docs/reports/REPORT-011-dataset-quality-and-annotation-audit.md`

Also save class distribution, box statistics, image dimensions, duplicate and leakage reports, suspect annotation CSV, review sheets, dataset hash manifest, audit scripts, and logs.

Clearly distinguish structural validity, visual annotation quality, class imbalance, diversity, split independence, viewpoint coverage, and uncertainty.

---

# 7. PHASE 5 — YOLO26m READINESS AND ISOLATED EXPERIMENT

The candidate is YOLO26m. The objective is to determine whether it improves detection quality enough to justify its compute and memory cost on an M5 MacBook Air with 16 GB unified memory. A larger model is not automatically better.

## 7.1 Preserve YOLO26n

Never overwrite `models/trained/best.pt`.

Keep YOLO26m configs, checkpoints, logs, training, validation, predictions, and benchmarks in a separate experiment directory. Adapt to existing conventions without moving old files.

## 7.2 Verify actual model support

Inspect installed Ultralytics version and verify YOLO26m is supported. Confirm exact pretrained checkpoint identifier/source, successful loading, architecture, parameter count, class count, and device compatibility.

Do not substitute another model family if YOLO26m is unsupported. Document the exact blocker.

## 7.3 Hardware smoke tests

Before full training:
1. Verify MPS availability and build support.
2. Load pretrained YOLO26m.
3. Run single-image inference.
4. Run small-batch inference.
5. Run a short training smoke test.
6. Measure latency and memory pressure.
7. Record warnings, CPU fallbacks, unsupported operations, and stability.

Do not claim GPU acceleration unless actual execution supports it.

If memory pressure is unacceptable, record the failure and test smaller batch sizes systematically in the isolated experiment. Do not change the dataset or architecture to hide a failure.

## 7.4 Initial training configuration

Initial controlled experiment:
- Model: verified YOLO26m.
- Pretrained weights: verified checkpoint.
- Dataset: original construction PPE dataset.
- Classes: 12, exact mapping preserved.
- Image size: 640.
- Initial epoch target: 30.
- Device: MPS if stable and supported.
- Batch size: selected through smoke testing.

Thirty epochs is an initial experiment, not a claim of optimal training duration.

Record exact batch size, seed, optimizer, learning rate, weight decay, augmentations, validation frequency, early stopping, and every other effective parameter. Save the complete config and command.

## 7.5 Training readiness report

Create:

`docs/reports/REPORT-013-yolo26m-readiness-and-training-configuration.md`

Do not start full training until the checkpoint loads, smoke tests pass, dataset configuration is verified, memory is manageable, and the experiment is reproducible.

---

# 8. PHASE 6 — YOLO26m TRAINING AND VALIDATION

Train only in the isolated YOLO26m directory.

Preserve:
- Best and last checkpoints.
- Training results.
- Logs.
- Learning curves.
- Precision/recall curves.
- mAP50 and mAP50-95 curves.
- Confusion matrix.
- Exact training config.
- Environment and hardware details.

Monitor training/validation loss and metrics, overfitting, class-level weakness, memory, device fallback, and stability. Do not choose a checkpoint based only on training loss.

After training:
- Verify checkpoint exists and loads.
- Verify class count and class-name mapping.
- Run inference.
- Calculate SHA-256.
- Confirm it is distinct from the YOLO26n checkpoint.
- Record exact path and configuration.

Create:

`docs/reports/REPORT-014-yolo26m-training-and-validation.md`

If training fails, preserve logs and report the actual blocker. Do not invent a completed run.

---

# 9. PHASE 7 — CONTROLLED YOLO26N VS YOLO26M COMPARISON

Use the same validation images and annotations, class mapping, image size, primary confidence/IoU settings, and evaluation methodology. Record any unavoidable environment differences.

Do not tune one model on the validation set and call the result an unbiased comparison. Keep primary controlled results separate from any secondary optimized-threshold experiment.

## 9.1 Overall metrics

Compare:

| Metric | YOLO26n | YOLO26m | Difference |
|---|---:|---:|---:|
| Precision | | | |
| Recall | | | |
| mAP50 | | | |
| mAP50-95 | | | |
| Inference latency | | | |
| Model size | | | |
| Parameter count | | | |
| Model loading time | | | |

Use actual measurements. Label units and distinguish absolute differences from percentage changes.

## 9.2 Per-class analysis

For every class compare precision, recall, AP50, AP50-95, false positives, and false negatives. Identify improvements, regressions, unchanged classes, and classes with too few examples for confident conclusions. Specifically investigate `no_goggle`.

## 9.3 Visual comparison

Run both models on identical images and produce side-by-side predictions covering easy, difficult, small-object, crowded, occluded, varied-viewpoint, low-light, false-positive, false-negative, and conflicting-box cases.

For each example record filename, model, predicted class, confidence, ground-truth class, correctness, and IoU information where available. Do not cherry-pick only successful examples.

## 9.4 Statistical caution

There are historically 200 validation images. Confirm the current count. Make limitations clear. A small metric difference does not establish broad real-world superiority. Where appropriate, use a documented bootstrap analysis to estimate uncertainty. Keep images and labels identical across models.

Create:

`docs/reports/REPORT-015-yolo26n-vs-yolo26m-comparison.md`

---

# 10. PHASE 8 — REAL-TIME WEBCAM AND VIDEO EVALUATION

Offline mAP is not equivalent to real-time application performance.

Separate evaluation categories:
1. Standard validation images.
2. Uploaded construction-site images.
3. Uploaded construction-site videos.
4. Webcam-style indoor scenes.
5. Motion scenarios.
6. Low-light scenarios where suitable material exists.

Do not combine results into one unexplained number.

## 10.1 Webcam methodology

Document environment, camera resolution, lighting, approximate subject distance, motion conditions, captured frame count, reviewed frame count, and selection method.

A webcam room test is not a construction-site test. Do not generalize beyond the sample.

## 10.2 Privacy

`experiments/live_audit/webcam/` may contain private images of the user. Keep these local and git-ignored. Do not upload, publish, commit, or delete them without explicit authorization. Avoid identifiable images in reports and public demonstration material.

## 10.3 Performance metrics

For YOLO26n and YOLO26m measure separately:
- Camera capture FPS.
- Inference FPS.
- Display FPS.
- Mean, median, P95 inference latency.
- Frame-to-display latency.
- Dropped frames.
- Detection-result age.
- Model loading time.
- Memory pressure.

Do not report camera FPS as inference FPS.

## 10.4 Stability and displayed quality

Investigate detection flicker, confidence variation, box movement/size variation, conflicting classes, and false detections on unrelated objects. Distinguish legitimate changes caused by motion or occlusion from model instability.

If tracking or temporal smoothing is introduced, treat it as a separate experimental variable; do not mix it invisibly into the model comparison.

For manually reviewed real-time samples, define and calculate displayed-frame precision/recall, stale-box occurrence rate, and incorrect frame-association rate where sufficient annotation exists. Explain matching methodology and sample limitations. Never call a small sample “overall real-world accuracy.”

## 10.5 Video integrity

Verify source frame order, timestamps, source frame IDs, rendered frame IDs, output dimensions/FPS, synchronization, event timestamps, and evidence-image timestamps.

Create:

`docs/reports/REPORT-016-real-time-webcam-and-video-evaluation.md`

---

# 11. PHASE 9 — PPE COMPLIANCE REGRESSION

The detector and compliance engine are separate. Do not change compliance rules to make the detector appear better.

Historical behaviours to inspect and preserve unless separately approved:
- Explicit missing-PPE classes.
- Person-to-PPE association.
- Potential violation, compliant evidence, and uncertain states.
- Three analysed-frame persistence requirement.
- 30-second repeat-event suppression.
- Frame-specific worker labels such as W1.

These are historical behaviours to verify against source code, not permission to assume they still exist.

Critical principle: failure to detect a helmet, gloves, goggles, boots, or vest does not itself prove the worker lacks that item. Distinguish explicit missing-PPE evidence, positive PPE evidence, and uncertainty.

Verify each PPE detection is associated with at most one appropriate person under existing rules. Test multiple people, overlap, small PPE boxes, partial visibility, false person detections, and missing-PPE boxes outside the relevant person region.

Do not claim persistent worker identity or unique worker counts if W1 labels are only frame-specific.

Test persistence, deduplication, suppression, timestamps, evidence creation, review status, database storage, CSV export, and restart behaviour. Do not alter thresholds without a separate controlled experiment and documented approval.

---

# 12. PHASE 10 — AUTOMATED AND INTEGRATION TESTS

Rerun the existing suite and add tests for the new failure modes.

## 12.1 Frame synchronization

Test:
- Result for N completes after N+1 arrives.
- N's result is not drawn on N+1.
- Result is rendered on source frame.
- Frame IDs are unique.
- Queue capacity is bounded.
- Drops are counted.
- Camera restart invalidates old results.
- Exceptions do not deadlock.
- Stop releases capture.
- Prior session cannot leak results into a new one.

Use deterministic frames and mocked inference for unit tests. Physical webcam checks are hardware integration tests.

## 12.2 Resolution and coordinates

Test live 640, image 640, documented video configuration, portrait/landscape, letterboxing, original-coordinate restoration, box bounds, and display resizing.

## 12.3 Model loading

Test YOLO26n and YOLO26m loading, missing/invalid checkpoints, class count and class-name mapping, and safe model switching without checkpoint overwrite.

## 12.4 Compliance

Test explicit missing-PPE, positive PPE, uncertain, no-person, multiple-person, conflicting boxes, association, persistence, suppression, evidence, database, and CSV export.

## 12.5 Application integration

Test dashboard startup, image, video, webcam start/stop, safety events, analytics, evaluation, settings, and error states.

Clearly label tests requiring physical hardware. Do not pretend mocked tests verify a physical camera.

Report totals, pass/fail/skip, duration, new tests, regressions, failure details, and resolution. Software tests do not establish model quality.

---

# 13. PHASE 11 — EXPERIMENT EVIDENCE AND REPRODUCIBILITY

Preserve a logical structure such as:

```text
experiments/
├── engineering_phase/
│   ├── baseline/
│   ├── pipeline_r1/
│   ├── resolution_r2/
│   └── final_validation/
├── dataset_audit/
└── yolo26m/
    ├── configs/
    ├── training/
    ├── validation/
    ├── predictions/
    ├── benchmarks/
    └── logs/
```

For every experiment preserve exact config, command, versions, hashes, start/end times, logs, metrics, plots, prediction examples, error examples, tests, interpretation, and limitations.

Every reported number must be traceable to an actual run. Never manually edit metrics to improve results or discard unsuccessful logs.

---

# 14. PHASE 12 — FINAL ENGINEERING COMPARISON AND DECISION

Compare YOLO26n and YOLO26m across:
- Overall and per-class validation metrics.
- Small PPE objects.
- Difficult viewpoints.
- Webcam-style scenes.
- Inference latency and real-time FPS.
- Frame-to-display latency.
- Model size and memory.
- Training duration.
- Operational stability.

Compare the application before and after R1/R2 across stale-box occurrence, incorrect frame association, latency, dropped frames, resolution parity, displayed detection quality, and event regressions.

Separate pipeline improvements from model improvements. For example, improved display quality caused by R1 must not be attributed to YOLO26m.

Do not choose YOLO26m merely because it is larger. Recommend a production candidate based on detection quality, missing-PPE recall, per-class performance, responsiveness, memory, reliability, and practical suitability for the Mac.

If YOLO26m improves offline metrics but is too slow for live use, report the trade-off. If neither model is adequate, say so. Do not switch the production checkpoint without explicit user approval.

---

# 15. REPORTING REQUIREMENTS

Create these reports, adapting numbering only if an existing report already uses an identifier. Never overwrite an existing report.

| Report | Filename |
|---|---|
| Phase 0 | `REPORT-010-phase0-project-discovery-and-baseline.md` |
| Dataset audit | `REPORT-011-dataset-quality-and-annotation-audit.md` |
| Pipeline corrections | `REPORT-012-live-pipeline-r1-r2-implementation.md` |
| YOLO26m readiness | `REPORT-013-yolo26m-readiness-and-training-configuration.md` |
| YOLO26m training | `REPORT-014-yolo26m-training-and-validation.md` |
| Model comparison | `REPORT-015-yolo26n-vs-yolo26m-comparison.md` |
| Real-time validation | `REPORT-016-real-time-webcam-and-video-evaluation.md` |
| Final report | `REPORT-017-siteguard-ai-engineering-phase-final-report.md` |

Every report must contain:
1. Executive summary.
2. Objective.
3. Initial project state.
4. Technical investigation.
5. Files inspected.
6. Files modified, exact paths, previous/new behaviour, reason.
7. Engineering decisions and alternatives.
8. Actual implementation details.
9. Testing methodology.
10. Actual measured results.
11. Before/after comparison.
12. Limitations and uncertainty.
13. Known unresolved issues.
14. Exact reproduction instructions.
15. Conclusion.
16. Recommended next step.

Reports must be detailed enough for independent technical review. Avoid vague claims such as “performance improved” or “everything works.” State measured values, sample size, settings, and evidence. Never fill missing values with guesses.

---

# 16. FRONTEND CONSTRAINTS

Do not redesign the existing dashboard in this phase. Make only necessary changes to display correct inference status, active model, inference resolution, actual FPS/latency, uncertainty, and errors.

Maintain the existing professional visual language. Avoid neon styling, decorative metrics, fake real-time values, misleading compliance percentages, and unsupported unique-worker tracking claims.

---

# 17. FAILURE HANDLING AND STOP CONDITIONS

Stop the affected phase and document the blocker if:
- Original data appears modified.
- Production checkpoint is at risk.
- User changes cannot be preserved.
- YOLO26m is unsupported.
- MPS execution is unstable.
- Training repeatedly fails.
- Memory pressure is unacceptable.
- Dataset configuration or class mapping is inconsistent.
- Validation leakage is discovered.
- Required evaluation cannot be reproduced.
- A change breaks an existing feature.
- A serious regression is introduced.
- Private webcam material would need external upload.
- A destructive action would be required.

For each failure report exact error/log, likely cause, attempts, what worked, unresolved issue, and recommended next step. A failed experiment accurately documented is preferable to an unsupported success claim.

---

# 18. FINAL ACCEPTANCE CHECKLIST

Evaluate and report each item honestly.

**Project integrity**
- Original dataset preserved.
- YOLO26n checkpoint preserved.
- User changes preserved.
- Git state and hashes recorded.
- No unauthorized public push/deployment.

**Baseline**
- YOLO26n baseline reproduced.
- Per-class metrics recorded.
- Configuration and evidence saved.

**Pipeline**
- R1 source-frame synchronization implemented.
- Stale boxes eliminated.
- Queue bounded and drops measured.
- Frame IDs and session lifecycle verified.
- R2 live resolution standardized at 640, or evidence-based exception documented.
- Coordinate transforms tested.
- Latency measured.

**Dataset**
- Inventory and class distribution completed.
- Box scale analyzed.
- Duplicate/leakage investigation completed.
- Visual annotation review performed with scope stated.
- Suspect annotations reported.
- Original dataset unchanged.

**YOLO26m**
- Architecture/checkpoint verified.
- MPS and hardware readiness checked.
- Smoke test completed.
- Full training completed or blocker documented.
- Separate checkpoint and config preserved.
- Validation completed.

**Comparison**
- Controlled YOLO26n/YOLO26m comparison.
- Overall and per-class metrics.
- Visual comparison.
- Latency and memory comparison.
- Limitations and production recommendation.

**Real-time**
- Webcam and video tested.
- Synchronization verified.
- Capture/inference/display FPS separated.
- Latency and dropped frames recorded.
- Privacy preserved.

**Software quality**
- Existing suite rerun.
- Regression tests added.
- Integration tests executed.
- Failures documented.

**Documentation**
- Required reports created.
- Configurations/logs/evidence saved.
- Metrics traceable to real runs.
- Final report completed.

---

# 19. FINAL ENGINEERING QUESTIONS

The final report must answer, with evidence:

1. Did R1 eliminate stale bounding-box rendering?
2. Did R2 standardize live inference to 640, and what was the measured impact?
3. What are the reproduced YOLO26n metrics?
4. What are the actual YOLO26m metrics?
5. Which classes improved or regressed?
6. What annotation or split-quality issues were found?
7. How do both models perform on small PPE objects?
8. How do both models perform on webcam-style scenes?
9. What are measured capture, inference, and display FPS on the M5?
10. What is the measured inference and frame-to-display latency?
11. What memory pressure was observed?
12. Is the application stable?
13. Did regression tests pass?
14. Which model is recommended and why?
15. What limitations remain?
16. What is the next engineering phase?

Distinguish clearly between:
- Academic prototype readiness.
- Controlled laboratory testing.
- Real construction-site validation.
- Production deployment readiness.

A laptop demonstration does not establish production readiness for an actual construction site.

---

# 20. EXECUTION DIRECTIVE — START NOW

Start with Phase 0. Inspect and preserve the actual project before editing code or training.

For every phase:
1. State the objective in the execution log.
2. Inspect relevant implementation.
3. Record initial state.
4. Make only required changes.
5. Run tests and experiments.
6. Collect evidence.
7. Write the detailed phase report.
8. Verify report statements against logs and artifacts.
9. Record unresolved issues.
10. Proceed only when prerequisites and acceptance criteria are satisfied.

Do not ask the user to manually edit code if you can safely inspect and implement it yourself. Ask for user participation only when physical hardware testing, authorization, or another genuinely user-controlled action is required. Explain exactly what is needed and why.

**Begin with actual project inspection. Preserve existing work. Execute sequentially. Document every meaningful change. Never fabricate a result.**
